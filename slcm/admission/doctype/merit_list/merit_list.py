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

    # Build lookup maps so we can accept either Admission Result name (row.applicant)
    # or Admission Result applicant_id (row.applicant_id)
    merit_by_applicant = {row.applicant: row for row in merit.merit_applicants}
    merit_by_applicant_id = {row.applicant_id: row for row in merit.merit_applicants if row.applicant_id}

    # Create Seat Allocation
    alloc = frappe.new_doc("Seat Allocation")
    alloc.admission_cycle = merit.admission_cycle
    alloc.campus = merit.campus
    alloc.merit_list = merit_list_name
    alloc.status = "Draft"

    for identifier in selected_applicants:
        row = merit_by_applicant.get(identifier) or merit_by_applicant_id.get(identifier)

        identifier_str = str(identifier) if identifier is not None else ""
        identifier_candidates = [identifier_str]
        if identifier_str.isdigit():
            stripped = identifier_str.lstrip("0")
            if stripped and stripped not in identifier_candidates:
                identifier_candidates.append(stripped)

        admission_result_name = None
        if frappe.db.exists("Admission Result", identifier):
            admission_result_name = identifier
        elif row and row.applicant and frappe.db.exists("Admission Result", row.applicant):
            admission_result_name = row.applicant
        else:
            # If identifier is applicant_id (0007) resolve Admission Result by applicant_id.
            # Try both exact and stripped-zero forms because some sites store applicant_id as integer-like strings.
            admission_result_name = frappe.db.get_value(
                "Admission Result",
                {"applicant_id": ["in", identifier_candidates]},
                "name",
            )

            # Some legacy data may have stored applicant_id in the Merit List 'applicant' field.
            if not admission_result_name and row and row.applicant:
                row_identifier = str(row.applicant)
                row_candidates = [row_identifier]
                if row_identifier.isdigit():
                    row_stripped = row_identifier.lstrip("0")
                    if row_stripped and row_stripped not in row_candidates:
                        row_candidates.append(row_stripped)
                admission_result_name = frappe.db.get_value(
                    "Admission Result",
                    {"applicant_id": ["in", row_candidates]},
                    "name",
                )

        if not admission_result_name:
            frappe.throw(
                f"Admission Result not found for Applicant Id / identifier: {identifier}. "
                "Please ensure the Admission Result records have applicant_id populated and are part of this Merit List."
            )

        alloc.append("selection_applicant", {
            "applicant": admission_result_name,
            "applicant_id": (row.applicant_id if row else None) or identifier,
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
