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
    Fetches merit data (score, ranks) from the Merit List child table.
    Returns the name of the created Seat Allocation.
    """
    if isinstance(selected_applicants, str):
        selected_applicants = json.loads(selected_applicants)

    if not selected_applicants:
        frappe.throw("No applicants selected.", title="Empty Selection")

    merit = frappe.get_doc("Merit List", merit_list_name)

    # Build a lookup map: applicant ID -> merit row data
    merit_data = {
        row.applicant_id: row
        for row in merit.merit_applicants
    }

    # Create Seat Allocation
    alloc = frappe.new_doc("Seat Allocation")
    alloc.admission_cycle = merit.admission_cycle
    alloc.campus = merit.campus
    alloc.merit_list = merit_list_name
    alloc.status = "Draft"

    for applicant_id in selected_applicants:
        row = merit_data.get(applicant_id)
        alloc.append("selection_applicant", {
            "applicant_id": row.applicant_id if row else applicant_id,
            "candidate_name": row.candidate_name if row else None,
            "program": row.program if row else None,
            "total_score": row.total_score if row else 0,
            "overall_rank": row.overall_rank if row else None,
            "selection_status": "Draft"
        })

    alloc.total_selected = len(selected_applicants)
    alloc.insert()
    frappe.db.commit()

    return alloc.name


@frappe.whitelist()
def publish_merit_list(merit_list_name):
    """
    Publishes the Merit List so students can view their scores
    on the applicant results portal page.
    Sets status to 'Published' and records an audit log.
    Also updates the Application Status of all applicants in the list to 'Merit Published'.
    """
    doc = frappe.get_doc("Merit List", merit_list_name)

    if doc.status == "Published":
        frappe.throw("Merit List is already published.")

    if doc.docstatus != 1:
        frappe.throw("Merit List must be submitted before publishing.")

    doc.db_set("status", "Published")

    # Update Applicant status
    for row in doc.merit_applicants:
        if row.applicant_id:
            frappe.db.set_value("Applicant", row.applicant_id, "application_status", "Merit Published")

    # Audit log
    frappe.get_doc({
        "doctype": "Admission Audit Log",
        "action": "Modified",
        "reference_doctype": "Merit List",
        "reference_name": merit_list_name,
        "performed_by": frappe.session.user,
        "reason": f"Merit List {merit_list_name} published by {frappe.session.user}"
    }).insert(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "Published"}


@frappe.whitelist()
def unpublish_merit_list(merit_list_name):
    """
    Reverts the Merit List status to 'Generated', hiding scores from students.
    Also reverts the Application Status of all applicants in the list to 'Submitted'.
    """
    doc = frappe.get_doc("Merit List", merit_list_name)

    if doc.status != "Published":
        frappe.throw("Merit List is not currently published.")

    doc.db_set("status", "Generated")

    # Revert Applicant status
    for row in doc.merit_applicants:
        if row.applicant_id:
            # Revert to Submitted if it was Merit Published
            current_status = frappe.db.get_value("Applicant", row.applicant_id, "application_status")
            if current_status == "Merit Published":
                frappe.db.set_value("Applicant", row.applicant_id, "application_status", "Submitted")

    # Audit log
    frappe.get_doc({
        "doctype": "Admission Audit Log",
        "action": "Modified",
        "reference_doctype": "Merit List",
        "reference_name": merit_list_name,
        "performed_by": frappe.session.user,
        "reason": f"Merit List {merit_list_name} unpublished by {frappe.session.user}"
    }).insert(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "Generated"}
