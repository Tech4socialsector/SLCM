import frappe
from frappe import _

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Fetch specific PACE Application if 'app' param is provided
    app_id = frappe.form_dict.get('app')
    filters = {"email_address": user}
    if app_id:
        filters["name"] = app_id
        
    application = frappe.get_all("PACE Application", 
        filters=filters, 
        fields=[
            "name", "status", "programme", "first_name", "last_name", 
            "application_form", "submission_date", "creation", "modified", 
            "academic_year", "ug_degree_certificate", "govt_id", 
            "student_signature", "upload_student_photo"
        ],
        order_by="creation desc",
        limit=1
    )
    
    # Initialize variables to avoid UndefinedError in template
    context.app = None
    context.programme = None
    context.verification = None
    context.verification_items = []
    context.assignment = None
    context.fee_breakdown = []
    context.receipt = None
    context.steps = []
    context.no_application = False

    if not application:
        context.no_application = True
        return context
    
    app = application[0]
    context.app = app
    
    # Programme details
    context.programme = frappe.db.get_value("PACE Programme", app.programme, ["programme_name", "duration", "duration_type"], as_dict=True)
    
    # Admission details
    context.admission_closed = False
    context.admission_details = None
    
    # Get active academic year if not already in app (fallback)
    active_year = app.academic_year
    if not active_year:
        active_year_doc = frappe.get_all("Academic Year", filters={"is_active": 1}, fields=["name"], limit=1)
        if active_year_doc:
            active_year = active_year_doc[0].name
    
    if active_year:
        admission = frappe.get_all("PACE Admission",
            filters={"academic_year": active_year, "status": "Active"},
            fields=["admission_open_date", "admission_close_date"],
            limit=1
        )
        if admission:
            context.admission_details = admission[0]
            if context.admission_details.admission_close_date:
                today = frappe.utils.today()
                if str(context.admission_details.admission_close_date) < str(today):
                    context.admission_closed = True

    # Verification details
    verification = frappe.get_all("PACE Document Verification",
        filters={"application": app.name},
        fields=["name", "status", "verified_on"],
        limit=1
    )
    
    context.verification = verification[0] if verification else None
    context.has_reuploaded_items = False
    # 1. Collection Phase Logic (Draft/Provisionally Submitted)
    if app.status in ["Provisionally Submitted", "Draft"]:
        missing_docs = []
        doc_fields = {
            "ug_degree_certificate": "UG Degree Certificate",
            "govt_id": "Govt. ID",
            "student_signature": "Student Signature",
        }
        for field, label in doc_fields.items():
            file_url = app.get(field)
            missing_docs.append({
                "document_name": label,
                "fieldname": field,
                "file": file_url,
                "status": app.status,
                "remarks": f"Please upload your {label}." if not file_url else "Draft uploaded. Please verify and submit.",
                "is_reuploaded": 0
            })
        context.verification_items = missing_docs
        context.all_documents_uploaded = all(item.get("file") for item in context.verification_items)
        context.has_reuploaded_items = any(item.get("file") for item in context.verification_items)

    # 2. Verification/Correction Phase Logic
    elif context.verification:
        context.verification_items = frappe.get_all("PACE Verification Item",
            filters={"parent": context.verification.name},
            fields=["document_name", "fieldname", "file", "status", "remarks", "is_reuploaded"]
        )
        has_pending_corrections = any(
            item.get("status") == "Returned for Correction" and not item.get("is_reuploaded") 
            for item in context.verification_items
        )
        has_any_reuploaded = any(item.get("is_reuploaded") for item in context.verification_items)
        context.has_reuploaded_items = has_any_reuploaded and not has_pending_corrections
    
    # Fee Assignment details
    assignments = frappe.get_all("PACE Applicant Fee Assignment",
        filters={
            "applicant": app.name,
            "fee_type": "Admission Fee",
            "docstatus": ["!=", 2]
        },
        fields=["name", "fee_structure", "currency", "final_payable_amount", "status", "academic_year"],
        limit=1
    )
    context.assignment = assignments[0] if assignments else None
    context.fee_breakdown = []
    
    if context.assignment:
        context.fee_breakdown = frappe.get_all("PACE Fee Component",
            filters={"parent": context.assignment.name, "parenttype": "PACE Applicant Fee Assignment"},
            fields=["fee_component", "amount", "tax_amount", "total_amount"]
        )
    
    # Receipt details
    receipt = frappe.get_all("PACE Receipt",
        filters={"pace_application": app.name, "fee_type": "Admission Fee"},
        fields=["name", "transaction_id", "payment_date"],
        limit=1
    )
    context.receipt = receipt[0] if receipt else None
    
    # Fetch receipt template from Fee Structure
    context.receipt_template = "Standard"
    if context.assignment and context.assignment.get("fee_structure"):
        template = frappe.db.get_value("PACE Fee Structure", context.assignment.fee_structure, "payment_reciept_template")
        if template:
            context.receipt_template = template
    
    # Fetch institution settings
    context.institution_code = frappe.db.get_single_value("Institution Settings", "institution_code")

    # PACE Application Status: one row per application status_name (links stage + UI state)
    context.pace_status_config = None
    context.next_step_note = ""
    if app.status:
        context.pace_status_config = frappe.db.get_value(
            "PACE Application Status",
            {"status_name": app.status},
            ["next_step_note", "stage_type", "status_type"],
            as_dict=True,
        )
        if context.pace_status_config and context.pace_status_config.get("next_step_note"):
            context.next_step_note = context.pace_status_config["next_step_note"]

    context.steps = get_step_statuses(
        app,
        context.verification,
        context.assignment,
        context.receipt,
        context.pace_status_config,
    )

    return context


# Canonical pipeline (must match PACE Application Status → Stage Type options)
STAGE_TYPE_TO_INDEX = {
    "Application Submitted": 0,
    "Document Verification": 1,
    "Fee Payment": 2,
    "Enrolled": 3,
}

# Tracker step ids must stay aligned with pace_progress_tracker/index.html icons
STAGE_DEFINITIONS = [
    ("submitted", "Application submitted"),
    ("verified", "Document verification"),
    ("fee_payment", "Fee payment"),
    ("enrolled", "Enrolled"),
]


def get_step_statuses(app, verification, assignment, receipt, pace_status_config=None):
    """
    Build the four tracker steps from ``PACE Application Status`` (stage_type + status_type).

    Rules (see fixtures in pace_application_status.json):
    - Stages before ``stage_type`` index: completed.
    - Stage at ``stage_type``: Active / Completed / Closed from ``status_type``.
    - If ``status_type`` is Completed, the *next* stage (index + 1) is shown as **active**
      (e.g. Submitted → Application Submitted completed, Document verification active).
    - Otherwise stages after the current index are pending.
    """
    cfg = pace_status_config
    if not cfg or not cfg.get("stage_type"):
        cfg = frappe.db.get_value(
            "PACE Application Status",
            {"status_name": (app.get("status") or "").strip()},
            ["stage_type", "status_type", "next_step_note"],
            as_dict=True,
        )
    if not cfg or not cfg.get("stage_type"):
        return _pace_tracker_steps_fallback(app, verification, assignment, receipt)

    idx = STAGE_TYPE_TO_INDEX.get((cfg.get("stage_type") or "").strip())
    if idx is None:
        idx = 0
    status_type = (cfg.get("status_type") or "Active").strip() or "Active"

    steps = []
    n = len(STAGE_DEFINITIONS)
    for i, (sid, label) in enumerate(STAGE_DEFINITIONS):
        date_sub = ""
        if i < idx:
            state = "completed"
            date_sub = _pace_tracker_step_date(i, app, verification, receipt, state)
        elif i == idx:
            if status_type == "Active":
                state = "active"
            elif status_type == "Completed":
                state = "completed"
            else:
                state = "closed"
            date_sub = _pace_tracker_step_date(i, app, verification, receipt, state)
        else:
            # i > idx
            if status_type == "Completed" and i == idx + 1:
                state = "active"
                date_sub = _pace_tracker_step_date(i, app, verification, receipt, state)
            else:
                state = "pending"
                date_sub = ""

        steps.append({"id": sid, "label": label, "status": state, "date": date_sub})

    return steps


def _pace_tracker_step_date(step_index, app, verification, receipt, state):
    """Short hint line under each tracker node when we have real dates."""
    try:
        if step_index == 0 and state == "completed":
            if app.get("submission_date"):
                return frappe.utils.format_date(app.submission_date)
            return frappe.utils.format_date(app.get("creation"))
        if step_index == 1 and verification and state == "completed":
            if verification.get("verified_on"):
                return frappe.utils.format_date(verification["verified_on"])
            return _("Completed")
        if step_index == 2 and state == "completed":
            if receipt and receipt.get("payment_date"):
                return frappe.utils.format_date(receipt["payment_date"])
            return _("Paid")
        if step_index == 3 and state == "completed":
            return frappe.utils.format_date(app.get("modified"))
        if state == "closed":
            return app.get("status") or _("Closed")
        if state == "active":
            if step_index == 1 and verification:
                ov = verification.get("status") or ""
                if ov == "Returned for Correction":
                    return _("Re-upload required")
            return ""
    except Exception:
        pass
    return ""


def _pace_tracker_steps_fallback(app, verification, assignment, receipt):
    """If no PACE Application Status row exists for this application status."""
    submitted_date = (
        frappe.utils.format_date(app.submission_date)
        if app.get("submission_date")
        else frappe.utils.format_date(app.creation)
    )
    steps = [
        {"id": "submitted", "label": "Application submitted", "status": "pending", "date": submitted_date},
        {"id": "verified", "label": "Document verification", "status": "pending", "date": ""},
        {"id": "fee_payment", "label": "Fee payment", "status": "pending", "date": ""},
        {"id": "enrolled", "label": "Enrolled", "status": "pending", "date": ""},
    ]
    st = (app.get("status") or "").strip()
    if st == "Draft":
        steps[0]["status"] = "active"
        steps[0]["date"] = ""
        return steps
    # Unknown status: show all pending except keep first date
    return steps
