import frappe

def validate_all_steps():
    """
    Validates all wizard steps before allowing onboarding_complete = 1.
    Returns list of error strings. Empty list means all steps pass.
    """
    errors = []
    settings = frappe.get_single("Institution Settings")

    # Step 1 — Institution Profile
    if not settings.institution_name:
        errors.append("Step 1: Institution name is required.")
    if not settings.institution_code:
        errors.append("Step 1: Institution code is required.")
    if not settings.compliance_mode:
        errors.append("Step 1: Compliance mode must be set (India / International / Both).")
    if not settings.support_email:
        errors.append("Step 1: Support email is required.")

    # Step 3 — Exam Types
    exam_count = frappe.db.count("Exam Type Config")
    if exam_count == 0:
        errors.append("Step 3: At least one Exam Type must be configured.")

    # Step 4 — Quota Policy
    quota_count = frappe.db.count("Quota Policy")
    if quota_count == 0:
        errors.append("Step 4: At least one Quota Policy must be configured.")

    # Step 5 — Admission Stages
    stage_count = frappe.db.count("Admission Stage Template")
    if stage_count == 0:
        errors.append("Step 5: At least one Admission Stage Template must be created.")

    # Step 6 — Document Requirements
    doc_count = frappe.db.count("Document Requirement Config")
    if doc_count == 0:
        errors.append("Step 6: At least one Document Requirement Config must be created.")

    # Step 7 — Email Templates
    email_count = frappe.db.count("Email Template Config", {"is_active": 1})
    if email_count == 0:
        errors.append("Step 7: At least one active Email Template must be configured.")

    # Step 8 — Application Form
    form_count = frappe.db.count("Application Form Config")
    if form_count == 0:
        errors.append("Step 8: At least one Application Form Config must be created.")

    # Step 9 — Fee Structure (external — skip, degrade gracefully)
    # Not validated here. External module responsibility.

    return errors


def get_step_status(step_number):
    """
    Returns status of a single wizard step.
    Returns: "complete" / "pending" / "external"
    """
    settings = frappe.get_single("Institution Settings")
    step_map = {
        1: lambda: bool(settings.institution_name and settings.institution_code and settings.compliance_mode),
        2: lambda: True,
        3: lambda: frappe.db.count("Exam Type Config") > 0,
        4: lambda: frappe.db.count("Quota Policy") > 0,
        5: lambda: frappe.db.count("Admission Stage Template") > 0,
        6: lambda: frappe.db.count("Document Requirement Config") > 0,
        7: lambda: frappe.db.count("Email Template Config", {"is_active": 1}) > 0,
        8: lambda: frappe.db.count("Application Form Config") > 0,
        9: lambda: None,
        10: lambda: bool(settings.onboarding_complete)
    }
    check = step_map.get(step_number)
    if check is None:
        return "pending"
    result = check()
    if result is None:
        return "external"
    return "complete" if result else "pending"


def get_wizard_summary():
    """
    Returns full wizard summary for progress display.
    """
    steps = range(1, 11)
    summary = {}
    complete_count = 0
    for s in steps:
        status = get_step_status(s)
        summary[f"step_{s}"] = status
        if status == "complete":
            complete_count += 1
    summary["total_complete"] = complete_count
    summary["total_steps"] = 9
    summary["ready_to_activate"] = complete_count >= 8
    return summary
