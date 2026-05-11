import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level


class MeritGeneration(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        # Use codes instead of names to keep it short
        cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code") or self.admission_cycle
        campus_code = frappe.db.get_value("Campus", self.campus, "campus_code") or self.campus
        
        cycle = cycle_code.replace(" ", "").upper()
        campus = campus_code.replace(" ", "").upper()
        level = (self.generation_type or "ALL").replace(" ", "").upper()
        
        if self.program:
            program_code = frappe.db.get_value("Program", self.program, "program_code") or self.program
            prog = program_code.replace(" ", "").upper()
            self.name = make_autoname(f"MG-{cycle}-{campus}-{prog}-.####")
        else:
            # Use a sequence so multiple attempts are recorded separately
            self.name = make_autoname(f"MG-{cycle}-{campus}-{level}-.####")

    @frappe.whitelist()
    def trigger_generation(self):
        """
        Triggers merit list generation for the selected Program Level.
        """
        program_level = self.generation_type
        if not program_level:
            frappe.throw("Please select a Program Level (UG / PG / PhD) before generating.")

        # 1. Check if an active Merit Rule Mapping exists for this program level/program
        mapping_filters = {
            "admission_cycle": self.admission_cycle,
            "campus": self.campus,
            "program_level": program_level,
            "is_active": 1
        }
        
        mapping = None
        if self.program:
            f = mapping_filters.copy()
            f["program"] = self.program
            mapping = frappe.db.get_value("Merit Rule Mapping", f, "merit_rule")
            
        if not mapping:
            mapping = frappe.db.get_value("Merit Rule Mapping", mapping_filters, "merit_rule")

        if not mapping:
            prog_msg = f" for Program '{self.program}'" if self.program else ""
            frappe.throw(
                f"No active Merit Rule Mapping found{prog_msg} for Program Level '{program_level}', "
                f"Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'. "
                f"Please create a Merit Rule Mapping first.",
                title="Missing Merit Rule Mapping"
            )

        # 2. Check if applicants exist for this program level/program
        check_filters = {
            "cycle": self.admission_cycle,
            "campus": self.campus,
            "level": program_level
        }
        
        program_cond = ""
        if self.program:
            program_cond = " AND er.program = %(program)s "
            check_filters["program"] = self.program

        applicants = frappe.db.sql(f"""
            SELECT er.name 
            FROM `tabEligibility Result` er
            WHERE er.admission_cycle = %(cycle)s
              AND er.program_level = %(level)s
              AND er.campus = %(campus)s
              {program_cond}
            LIMIT 1
        """, check_filters, as_dict=True)

        if not applicants:
            prog_msg = f" and Program '{self.program}'" if self.program else ""
            frappe.throw(
                f"No applicants found for Program Level '{program_level}'{prog_msg}, "
                f"Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'.",
                title="No Applicants Found"
            )

        # 3. Check if ANY Published Merit List already exists
        existing_published_filters = {
            "admission_cycle": self.admission_cycle,
            "campus": self.campus,
            "program_level": program_level,
            "status": "Published"
        }
        if self.program:
            existing_published_filters["program"] = self.program

        existing_published = frappe.db.get_value(
            "Merit List",
            existing_published_filters,
            ["name", "generated_on"],
            as_dict=True
        )
        if existing_published:
            self.status = "Completed"
            self.generated_on = existing_published.generated_on
            self.save()
            prog_msg = f" for {self.program}" if self.program else ""
            frappe.msgprint(
                f"The Merit List '{existing_published.name}'{prog_msg} is already published. "
                f"Generation skipped. "
                f"To make changes or regenerate the list, you must first unpublish it. "
                f"<a href='/app/merit-list/{existing_published.name}'><b>View Merit List</b></a>.",
                title="Merit List Published",
                indicator="orange"
            )
            return

        # 4. All validations passed — enqueue background job
        self.status = "In Progress"
        self.save()
        frappe.db.commit()

        mode = (frappe.conf.get("slcm_merit_generation_mode") or "sync").lower()

        # In production, background workers/redis may be misconfigured. To avoid a stuck
        # 'In Progress' state, allow a synchronous fallback via site_config.
        if mode == "sync":
            try:
                run_generation_main(self.name)
                frappe.msgprint(
                    f"Merit generation for {program_level} completed. "
                    f"Please refresh the Merit List."
                )
            except Exception as e:
                frappe.msgprint(
                    f"Merit generation for {program_level} failed: {str(e)}",
                    indicator="red"
                )
            return

        try:
            frappe.enqueue(
                "slcm.admission.doctype.merit_generation.merit_generation.run_generation",
                docname=self.name,
                now=frappe.flags.in_test,
                queue="short",
                enqueue_after_commit=True
            )

            frappe.msgprint(
                f"Merit generation for {program_level} started in the background. "
                f"Please check back in a few moments."
            )
        except Exception:
            # If enqueue fails (redis/worker issues), run inline so hosted setups still work.
            try:
                run_generation_main(self.name)
            except Exception as e:
                frappe.msgprint(
                    f"Merit generation for {program_level} failed: {str(e)}",
                    indicator="red"
                )

def run_generation(docname):
    """
    Background worker function (wrapper for run_generation_main).
    """
    try:
        run_generation_main(docname)
    except Exception:
        # Traceback is already logged in run_generation_main
        pass


def run_generation_main(docname):
    """
    Core generation logic. Phase 1 (Part A Ranking) is triggered here
    and the results are pushed to the Shortlisting Merit List doctype.
    """
    doc = frappe.get_doc("Merit Generation", docname)
    program_level = doc.generation_type

    try:
        # Phase 1 is ALWAYS the first step in this workflow
        # We don't save the Merit List record here, it's just a data container for Phase 1.
        merit_list_doc = generate_merit_for_level(
            doc.admission_cycle, 
            doc.campus, 
            program_level, 
            program=doc.program,
            processing_stage="Part A Ranking",
            save=False
        )

        # Create or Update Shortlisting Merit List
        sp_filters = {
            "admission_cycle": doc.admission_cycle,
            "campus": doc.campus,
            "program_level": program_level
        }
        if doc.program:
            sp_filters["program"] = doc.program
            
        sp_name = frappe.db.get_value("Shortlisting Merit List", sp_filters, "name")
        
        if sp_name:
            sp_doc = frappe.get_doc("Shortlisting Merit List", sp_name)
        else:
            sp_doc = frappe.new_doc("Shortlisting Merit List")
            sp_doc.update(sp_filters)
        
        sp_doc.generated_on = merit_list_doc.generated_on
        sp_doc.pull_from_merit_list(merit_list_doc)
        sp_doc.save(ignore_permissions=True)

        doc.status = "Completed"
        doc.generated_on = merit_list_doc.generated_on
        doc.save()
        frappe.db.commit()

        # Link the created process in the message
        frappe.msgprint(
            f"Phase 1 Shortlisting Merit List generated. Results pushed to "
            f"<a href='/app/shortlisting-merit-list/{sp_doc.name}'><b>{sp_doc.name}</b></a>."
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Merit Generation Failed")
        doc.status = "Failed"
        doc.save()
        frappe.db.commit()
        raise e
    
