import frappe
import json
from frappe.model.document import Document


class MeritList(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        # Use codes instead of names to keep it short
        cycle_code = frappe.db.get_value("Admission Cycle", self.admission_cycle, "cycle_code") or self.admission_cycle
        campus_code = frappe.db.get_value("Campus", self.campus, "campus_code") or self.campus
        
        cycle = cycle_code.replace(" ", "").upper()
        campus = campus_code.replace(" ", "").upper()
        level = (self.program_level or "ALL").upper()

        self.name = make_autoname(f"ML-{cycle}-{campus}-{level}-.#####")

    def validate(self):
        self.validate_uniqueness()

    def validate_uniqueness(self):
        """
        Ensures only one PUBLISHED Merit List exists per Campus, Admission Cycle, and Program Level.
        """
        if self.status != "Published":
            return

        filters = {
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level,
            "status": "Published",
            "name": ["!=", self.name]
        }

        existing = frappe.db.exists("Merit List", filters)
        if existing:
            from frappe.utils import get_link_to_form
            link = get_link_to_form("Merit List", existing)
            frappe.throw(
                f"A Merit List is already PUBLISHED for Campus '{self.campus}', "
                f"Admission Cycle '{self.admission_cycle}' and Program Level '{self.program_level or 'All'}'. "
                f"Unpublish it first if you need to publish this one. "
                f"<br><br>Existing Published Merit List: {link}",
                title="Duplicate Published Merit List"
            )


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
    alloc.program_level = merit.program_level
    alloc.merit_list = merit_list_name
    alloc.status = "Draft"

    for applicant_id in selected_applicants:
        row = merit_data.get(applicant_id)
        # Skip Rejected applicants — they must not receive a seat allocation
        if row and row.status == "Rejected":
            continue
        alloc.append("selection_applicant", {
            "applicant_id": row.applicant_id if row else applicant_id,
            "candidate_name": row.candidate_name if row else None,
            "program": row.program if row else None,
            "total_score": row.total_score if row else 0,
            "overall_rank": row.overall_rank if row else None,
            "selection_status": "Draft"
        })

    if not alloc.selection_applicant:
        frappe.throw("No eligible applicants to allocate. Rejected applicants cannot be added to a Seat Allocation.", title="No Eligible Applicants")

    alloc.total_selected = len(alloc.selection_applicant)
    alloc.insert()
    
    # Run automatic allocation logic immediately
    alloc.allocate_seats()
    
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
        frappe.throw(f"Merit List '{merit_list_name}' is already published.")

    if doc.docstatus != 1:
        frappe.throw("Merit List must be submitted before publishing.")

    doc.status = "Published"
    doc.save()

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

    doc.status = "Generated"
    doc.save()

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
        "action": "Unpublished",
        "reference_doctype": "Merit List",
        "reference_name": merit_list_name,
        "performed_by": frappe.session.user,
        "reason": f"Merit List {merit_list_name} unpublished by {frappe.session.user}. It is now open for corrections or regeneration."
    }).insert(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "Generated"}
