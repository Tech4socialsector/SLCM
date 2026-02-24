
import frappe
from frappe.utils import now

def log_merit_action(
    reference_doctype,
    reference_name,
    applicant=None,
    program=None,
    action_type=None,
    old_value=None,
    new_value=None,
    remarks=None,
    snapshot=None
):
    """
    Logging function for all merit-related actions.
    """
    _log_action(
        doctype="Merit Audit Log",
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        applicant=applicant,
        program=program,
        action_type=action_type,
        old_value=old_value,
        new_value=new_value,
        remarks=remarks,
        snapshot=snapshot
    )

def log_seat_allocation_action(
    reference_doctype,
    reference_name,
    applicant=None,
    program=None,
    action_type=None,
    old_value=None,
    new_value=None,
    remarks=None,
    snapshot=None
):
    """
    Logging function for all seat allocation related actions.
    """
    _log_action(
        doctype="Seat Allocation Audit Log",
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        applicant=applicant,
        program=program,
        action_type=action_type,
        old_value=old_value,
        new_value=new_value,
        remarks=remarks,
        snapshot=snapshot
    )

def _log_action(
    doctype,
    reference_doctype,
    reference_name,
    applicant=None,
    program=None,
    action_type=None,
    old_value=None,
    new_value=None,
    remarks=None,
    snapshot=None
):
    log_data = {
        "doctype": doctype,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "applicant": applicant,
        "program": program,
        "action_type": action_type,
        "old_value": str(old_value) if old_value is not None else None,
        "new_value": str(new_value) if new_value is not None else None,
        "remarks": remarks,
        "performed_by": frappe.session.user,
        "performed_on": now()
    }
    
    if snapshot:
        import json
        log_data["snapshot_json"] = json.dumps(snapshot, indent=2, default=str)

    frappe.get_doc(log_data).insert(ignore_permissions=True)
