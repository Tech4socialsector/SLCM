import frappe
import json
from frappe.model.document import Document


class MeritList(Document):

    def autoname(self):
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        cycle = self.admission_cycle.replace(" ", "").upper()
        campus = self.campus.replace(" ", "").upper()

        if self.program_level:
            level = self.program_level.upper()
            self.name = f"ML-{cycle}-{campus}-{level}"
        else:
            self.name = f"ML-{cycle}-{campus}"


@frappe.whitelist()
def create_seat_allocation(merit_list_name, selected_applicants):
    """
    Creates a Seat Allocation from selected applicant names.
    Fetches merit data (score, ranks, reservation_category) from the Merit List child table.
    Returns the name of the created Seat Allocation.
    """
    if isinstance(selected_applicants, str):
        selected_applicants = json.loads(selected_applicants)

    if not selected_applicants:
        frappe.throw("No applicants selected.", title="Empty Selection")

    merit = frappe.get_doc("Merit List", merit_list_name)

    # Build a lookup map: applicant name → merit row data
    merit_data = {
        row.applicant: row
        for row in merit.merit_applicants
    }

    # Create Seat Allocation
    alloc = frappe.new_doc("Seat Allocation")
    alloc.admission_cycle = merit.admission_cycle
    alloc.campus = merit.campus
    alloc.merit_list = merit_list_name
    alloc.status = "Draft"

    for applicant_name in selected_applicants:
        row = merit_data.get(applicant_name)
        alloc.append("selection_applicant", {
            "applicant": applicant_name,
            "applicant_id": row.applicant_id if row else None,
            "program": row.program if row else None,
            "reservation_category": row.reservation_category if row else None,
            "total_score": row.total_score if row else 0,
            "overall_rank": row.overall_rank if row else None,
            "category_rank": row.category_rank if row else None,
            "selection_status": "Draft"
        })

    alloc.total_selected = len(selected_applicants)
    alloc.insert()
    frappe.db.commit()

    return alloc.name
