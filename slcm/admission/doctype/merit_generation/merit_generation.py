import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level


class MeritGeneration(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        cycle = self.admission_cycle.replace(" ", "").upper()
        campus = self.campus.replace(" ", "").upper()
        level = (self.generation_type or "ALL").replace(" ", "").upper()

        # Use a sequence so multiple attempts are recorded separately
        self.name = make_autoname(f"MG-{cycle}-{campus}-{level}-.#####")

    @frappe.whitelist()
    def trigger_generation(self):
        """
        Triggers merit list generation for the selected Program Level.
        """
        program_level = self.generation_type
        if not program_level:
            frappe.throw("Please select a Program Level (UG / PG / PhD) before generating.")

        # 1. Check if an active Merit Rule Mapping exists for this program level
        mapping = frappe.db.get_value(
            "Merit Rule Mapping",
            {
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "program_level": program_level,
                "is_active": 1
            },
            "merit_rule"
        )
        if not mapping:
            frappe.throw(
                f"No active Merit Rule Mapping found for Program Level '{program_level}', "
                f"Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'. "
                f"Please create a Merit Rule Mapping first.",
                title="Missing Merit Rule Mapping"
            )

        # 2. Check if applicants exist for this program level
        applicants = frappe.db.sql("""
            SELECT er.name 
            FROM `tabEligibility Result` er
            WHERE er.admission_cycle = %(cycle)s
              AND er.program_level = %(level)s
              AND er.campus = %(campus)s
            LIMIT 1
        """, {
            "cycle": self.admission_cycle,
            "campus": self.campus,
            "level": program_level
        }, as_dict=True)
        if not applicants:
            frappe.throw(
                f"No applicants found for Program Level '{program_level}', "
                f"Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'.",
                title="No Applicants Found"
            )

        # 3. Check if a Published Merit List already exists
        existing = frappe.db.get_value(
            "Merit List",
            {
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "program_level": program_level
            },
            ["name", "status", "docstatus"],
            as_dict=True
        )
        if existing:
            if existing.get("status") == "Published":
                merit = frappe.get_doc("Merit List", existing.get("name"))
                self.status = "Completed"
                self.generated_on = merit.generated_on
                self.save()
                frappe.msgprint(
                    f"Merit List '{merit.name}' is already PUBLISHED. "
                    f"Unpublish it first if you need to fix or regenerate. "
                    f"<a href='/app/merit-list/{merit.name}'>View List</a>.",
                    title="Merit List Published",
                    indicator="orange"
                )
                return
            else:
                # If existing list is Generated/Draft, let it fall through to enqueue/sync generation
                # which will now handle the cancellation/re-creation in merit_service.py
                pass

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
                frappe.msgprint(
                    f"Merit generation for {program_level} completed. "
                    f"Please refresh the Merit List."
                )
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
    Core generation logic.
    """
    doc = frappe.get_doc("Merit Generation", docname)
    program_level = doc.generation_type

    try:
        merit_list = generate_merit_for_level(doc.admission_cycle, doc.campus, program_level)

        doc.status = "Completed"
        doc.generated_on = merit_list.generated_on if merit_list.docstatus == 1 else now_datetime()
        doc.save()
        frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Merit Generation Failed")
        doc.status = "Failed"
        doc.save()
        frappe.db.commit()
        raise e
    
