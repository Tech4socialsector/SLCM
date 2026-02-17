import frappe
from frappe.model.document import Document
from slcm.admission.doctype.merit_rule.merit_service import generate_merit


class MeritGeneration(Document):

    def autoname(self):
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        cycle = self.admission_cycle.replace(" ", "").upper()
        campus = self.campus.replace(" ", "").upper()

        self.name = f"MG-{cycle}-{campus}"
    
    @frappe.whitelist()
    def trigger_generation(self):
        """
        Triggers the background generation process.
        """
        # 1. Check if merit rule mappings exist for this cycle and campus
        mappings = frappe.get_all(
            "Merit Rule Mapping",
            filters={
                "admission_cycle": self.admission_cycle,
                "campus": self.campus,
                "is_active": 1
            },
            limit=1
        )
        
        if not mappings:
            frappe.throw(
                f"No active Merit Rule Mappings found for Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'. "
                f"Please create Merit Rule Mappings before generating the merit list.",
                title="Missing Merit Rule Mappings"
            )
        
        # 2. Check if applicants exist for this cycle and campus
        applicants = frappe.get_all(
            "test Applicant",
            filters={
                "admission_cycle": self.admission_cycle,
                "campus": self.campus
            },
            limit=1
        )
        
        if not applicants:
            frappe.throw(
                f"No applicants found for Campus '{self.campus}' and Admission Cycle '{self.admission_cycle}'. "
                f"Please add applicants before generating the merit list.",
                title="No Applicants Found"
            )
        
        # 3. Check if merit list already exists
        existing_merit = frappe.db.get_value(
            "Merit List",
            {"admission_cycle": self.admission_cycle, "campus": self.campus},
            ["name", "docstatus"],
            as_dict=True
        )
        
        if existing_merit:
            # Merit list already exists - show message and mark as completed
            self.status = "Completed"
            self.generated_on = frappe.db.get_value("Merit List", existing_merit.name, "generated_on")
            self.save()
            
            frappe.msgprint(
                f"Merit List '{existing_merit.name}' has already been generated for Campus '{self.campus}' and Cycle '{self.admission_cycle}'. "
                f"<a href='/app/merit-list/{existing_merit.name}'>Click here to view it</a>.",
                title="Merit List Already Exists",
                indicator="blue"
            )
            return
        
        # 4. All validations passed - proceed with generation
        self.status = "In Progress"
        self.save()
        frappe.db.commit()

        # Enqueue the background job
        frappe.enqueue(
            "slcm.admission.doctype.merit_generation.merit_generation.run_generation",
            docname=self.name,
            now=frappe.flags.in_test
        )

        frappe.msgprint("Merit generation started in the background. Please check back in a few moments.")


def run_generation(docname):
    """
    Background worker function.
    """
    doc = frappe.get_doc("Merit Generation", docname)
    try:
        # Calculate scores, assign ranks, create ONE Merit List
        merit_list = generate_merit(doc.admission_cycle, doc.campus)

        # Update status to Completed (whether new or existing)
        doc.status = "Completed"
        doc.generated_on = merit_list.generated_on if merit_list.docstatus == 1 else frappe.utils.now_datetime()
        doc.save()
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Merit Generation Failed")
        doc.status = "Failed"
        doc.save()
        frappe.db.commit()

