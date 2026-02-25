import frappe
from frappe.utils import now_datetime, get_datetime

DEADLINE_ACTION_MAP = {
    "Apply":             "Application",
    "Edit Application":  "Application",
    "Evaluate":          "Evaluation",
    "Interview":         "Interview",
    "Offer":             "Offer",
    "Accept":            "Acceptance",
    "Payment":           "Payment"
}

def validate_cycle_deadline(action, cycle_name):
    """
    Central deadline enforcement utility.
    Call from every DocType hook, portal API, and background job.

    Usage:
        from slcm.admission.utils.deadline import validate_cycle_deadline
        validate_cycle_deadline("Apply", "ADM-CYCLE-2025-001")

    Raises frappe.PermissionError if action is outside allowed window.
    Returns True if action is allowed.
    """
    deadline_type = DEADLINE_ACTION_MAP.get(action)
    if not deadline_type:
        frappe.throw(f"Unknown action '{action}'. Cannot validate deadline.")

    deadline = frappe.db.get_value(
        "Admission Cycle Deadline",
        {
            "admission_cycle": cycle_name,
            "deadline_type": deadline_type,
            "is_active": 1
        },
        ["start_datetime", "end_datetime"],
        as_dict=True
    )

    if not deadline:
        frappe.log_error(
            f"No active deadline configured for '{deadline_type}' in cycle '{cycle_name}'.",
            "Deadline Config Missing"
        )
        return True

    now = now_datetime()
    start = get_datetime(deadline.start_datetime)
    end = get_datetime(deadline.end_datetime)

    if now < start:
        frappe.throw(
            f"The {deadline_type} window has not opened yet. "
            f"It opens on {frappe.utils.formatdate(str(start), 'dd MMM yyyy, hh:mm a')}.",
            title="Window Not Open"
        )

    if now > end:
        frappe.throw(
            f"The {deadline_type} window is closed. "
            f"It closed on {frappe.utils.formatdate(str(end), 'dd MMM yyyy, hh:mm a')}.",
            title="Deadline Passed"
        )

    return True


def get_active_deadline(cycle_name, deadline_type):
    """
    Returns active deadline record for a cycle and type.
    Returns None if not configured.
    """
    return frappe.db.get_value(
        "Admission Cycle Deadline",
        {"admission_cycle": cycle_name, "deadline_type": deadline_type, "is_active": 1},
        ["start_datetime", "end_datetime", "name"],
        as_dict=True
    )


def is_within_deadline(cycle_name, deadline_type):
    """
    Returns True if current time is within the deadline window.
    Returns False if outside window or not configured.
    """
    deadline = get_active_deadline(cycle_name, deadline_type)
    if not deadline:
        return False
    now = now_datetime()
    return get_datetime(deadline.start_datetime) <= now <= get_datetime(deadline.end_datetime)


def get_deadline_status(cycle_name):
    """
    Returns status of all deadlines for a cycle.
    Used by applicant dashboard and admin cycle view.
    """
    deadlines = frappe.get_all(
        "Admission Cycle Deadline",
        filters={"admission_cycle": cycle_name, "is_active": 1},
        fields=["deadline_type", "start_datetime", "end_datetime"]
    )
    now = now_datetime()
    result = {}
    for d in deadlines:
        start = get_datetime(d.start_datetime)
        end = get_datetime(d.end_datetime)
        if now < start:
            status = "upcoming"
        elif now > end:
            status = "closed"
        else:
            status = "active"
        result[d.deadline_type] = {
            "status": status,
            "start": str(d.start_datetime),
            "end": str(d.end_datetime)
        }
    return result
