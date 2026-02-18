import frappe
from frappe.model.document import Document
from slcm.admission.doctype.merit_rule.merit_service import generate_merit_for_level


class MeritGeneration(Document):

    def autoname(self):
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        cycle = self.admission_cycle.replace(" ", "").upper()
        campus = self.campus.replace(" ", "").upper()
        level = (self.generation_type or "ALL").replace(" ", "").upper()

        self.name = f"MG-{cycle}-{campus}-{level}"

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
        applicants = frappe.get_all(
            "test Applicant",
            filters={
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "program_level": program_level
            },
            limit=1
        )
        if not applicants:
            frappe.throw(
                f"No applicants found for Program Level '{program_level}', "
                f"Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'.",
                title="No Applicants Found"
            )

        # 3. Check if a Merit List already exists for this program level
        existing = frappe.db.get_value(
            "Merit List",
            {
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "program_level": program_level
            },
            ["name", "docstatus"],
            as_dict=True
        )
        if existing:
            self.status = "Completed"
            self.generated_on = frappe.db.get_value("Merit List", existing.name, "generated_on")
            self.save()
            frappe.msgprint(
                f"Merit List '{existing.name}' already exists for {program_level}. "
                f"<a href='/app/merit-list/{existing.name}'>Click here to view it</a>.",
                title="Merit List Already Exists",
                indicator="blue"
            )
            return

        # 4. All validations passed — enqueue background job
        self.status = "In Progress"
        self.save()
        frappe.db.commit()

        frappe.enqueue(
            "slcm.admission.doctype.merit_generation.merit_generation.run_generation",
            docname=self.name,
            now=frappe.flags.in_test
        )

        frappe.msgprint(
            f"Merit generation for {program_level} started in the background. "
            f"Please check back in a few moments."
        )


def run_generation(docname):
    """
    Background worker function.
    """
    doc = frappe.get_doc("Merit Generation", docname)
    program_level = doc.generation_type

    try:
        merit_list = generate_merit_for_level(doc.admission_cycle, doc.campus, program_level)

        doc.status = "Completed"
        doc.generated_on = merit_list.generated_on if merit_list.docstatus == 1 else frappe.utils.now_datetime()
        doc.save()
        frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Merit Generation Failed")
        doc.status = "Failed"
        doc.save()
        frappe.db.commit()
