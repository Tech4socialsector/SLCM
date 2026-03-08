import frappe
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.doctype.eligibility_result.eligibility_result import get_applicant_data

login_required = True

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/my-applications"
        raise frappe.Redirect

    # Portal config
    try:
        cfg = get_portal_config()
        context.portal_config = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
    except Exception:
        context.portal_config = {}

    # Status styling
    STATUS_STYLE = {
        "Draft":          {"color": "#6b7280", "bg": "#f3f4f6"},
        "Submitted":      {"color": "#1d4ed8", "bg": "#dbeafe"},
        "Under Review":   {"color": "#d97706", "bg": "#fef3c7"},
        "Shortlisted":    {"color": "#059669", "bg": "#d1fae5"},
        "Waitlisted":     {"color": "#7c3aed", "bg": "#ede9fe"},
        "Offer Issued":   {"color": "#0369a1", "bg": "#e0f2fe"},
        "Offer Accepted": {"color": "#065f46", "bg": "#d1fae5"},
        "Offer Declined": {"color": "#991b1b", "bg": "#fee2e2"},
        "Rejected":       {"color": "#991b1b", "bg": "#fee2e2"},
        "Selected":       {"color": "#065f46", "bg": "#d1fae5"},
        "Fee Paid":       {"color": "#065f46", "bg": "#d1fae5"},
    }

    # 1. Fetch all applicant data using the API
    data_list = get_applicant_data()
    if isinstance(data_list, dict) and "error" in data_list:
        context.error = data_list["error"]
        context.applications = []
        return context

    # 2. Determine which application to show
    target_app_id = frappe.form_dict.get('app')
    
    applications = []
    active_app_summary = None
    
    for entry in data_list:
        prof = entry.get("profile", {})
        app_id = prof.get("applicant_id")
        if not app_id: continue
        
        # Load the full doc for detail sections
        app_doc = frappe.get_doc("Applicant", app_id)
        
        status = app_doc.application_status or "Draft"
        style = STATUS_STYLE.get(status, STATUS_STYLE["Draft"])
        
        program_name = frappe.db.get_value("Program", app_doc.program, "program_name") or app_doc.program or "Application"
        program_slug = frappe.db.get_value("Program", app_doc.program, "program_slug") or ""

        summary = {
            "name": app_doc.name,
            "header": {
                "name": app_doc.name,
                "program_name": program_name,
                "program_slug": program_slug,
                "cycle": app_doc.admission_cycle or "—",
                "status": status,
                "status_color": style["color"],
                "status_bg": style["bg"],
                "submitted_on": frappe.utils.formatdate(app_doc.creation, "dd MMM yyyy"),
                "current_stage": app_doc.current_stage or "Pending",
                "applicant_id": app_doc.applicant_id or app_doc.name,
                "merit_score": prof.get("merit_score") or (entry.get("merit")[0].get("total_score") if entry.get("merit") else None)
            },
            "personal": [
                {"label": "Full Name", "value": app_doc.candidate_name},
                {"label": "Date of Birth", "value": frappe.utils.formatdate(app_doc.date_of_birth, "dd MMM yyyy") if app_doc.date_of_birth else None},
                {"label": "Gender", "value": app_doc.gender},
                {"label": "Nationality", "value": app_doc.nationality},
                {"label": "Email", "value": app_doc.email},
                {"label": "Mobile", "value": app_doc.mobile_number},
                {"label": "Religion", "value": app_doc.religion},
                {"label": "Annual Income", "value": app_doc.annual_house_hold_income},
            ],
            "academic": [
                {"label": "10th Percentage", "value": app_doc.class_x_percentage},
                {"label": "10th Board", "value": app_doc.class_x_board},
                {"label": "10th Year", "value": app_doc.class_x_year_of_completion},
                {"label": "12th Percentage", "value": app_doc.hsc_percentage or app_doc.percentage},
                {"label": "12th Board", "value": app_doc.class_xii_board},
                {"label": "12th Year", "value": app_doc.class_xii_year_of_completion},
                {"label": "HSC Group", "value": app_doc.hsc_group},
            ],
            "application": [
                {"label": "Application ID", "value": app_doc.applicant_id or app_doc.name},
                {"label": "Program", "value": app_doc.program},
                {"label": "Admission Cycle", "value": app_doc.admission_cycle},
                {"label": "Fee Status", "value": app_doc.application_fee_status},
                {"label": "Reservation Category", "value": app_doc.reservation_category},
            ],
            "admission_results": entry.get("results", []),
            "merit_list": entry.get("merit", []),
            "can_edit": (status == "Draft"),
            "active_stage": app_doc.current_stage
        }
        
        # Build action buttons for this summary
        actions = []
        if status == "Draft":
            actions.append({"label": "Continue Application", "url": "/application-form/" + app_doc.name, "type": "primary"})
        elif status == "Offer Issued":
            actions.append({"label": "Accept Offer", "url": "/application-form/" + app_doc.name, "type": "success"})
            if program_slug:
                actions.append({"label": "View Program", "url": "/admission/" + program_slug, "type": "outline"})
        else:
            if program_slug:
                actions.append({"label": "View Program", "url": "/admission/" + program_slug, "type": "outline"})
        summary["action_buttons"] = actions

        applications.append(summary)
        
        # Set active app if it matches target or if it's the first one
        if target_app_id == app_doc.name or not active_app_summary:
            active_app_summary = summary

    context.applications = applications
    context.active_app = active_app_summary
    context.no_cache = 1
    context.title = "My Applications"
