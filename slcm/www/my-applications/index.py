import frappe
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.utils.stage_control import (
    can_edit_application, get_current_stage, get_portal_stage_list
)

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

    # Find Applicant record
    applicant = None
    # 1. By owner
    applicant_list = frappe.get_all("Applicant", filters={"owner": frappe.session.user}, fields=["name"], limit=1)
    if applicant_list:
        applicant = frappe.get_doc("Applicant", applicant_list[0].name)
    
    # 2. By email fallback
    if not applicant:
        applicant_list = frappe.get_all("Applicant", filters={"email": frappe.session.user}, fields=["name"], limit=1)
        if applicant_list:
            applicant = frappe.get_doc("Applicant", applicant_list[0].name)

    if applicant:
        context.applicant = applicant
        context.candidate_name = applicant.candidate_name or frappe.session.user.split("@")[0].replace(".", " ").title()
        
        # Stage-driven edit permission and stage context
        intake  = applicant.intake_type or "All"
        cycle   = applicant.admission_cycle or ""
        if cycle:
            context.can_edit       = can_edit_application(cycle, intake)
            context.portal_stages  = get_portal_stage_list(cycle, intake)
            curr_st                = get_current_stage(cycle, intake)
            context.active_stage   = curr_st.stage_name if curr_st else ""
        else:
            context.can_edit       = False
            context.portal_stages  = []
            context.active_stage   = ""

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
        
        status = applicant.application_status or "Draft"
        style = STATUS_STYLE.get(status, STATUS_STYLE["Draft"])
        
        # Build Summary
        app_summary = {
            "header": {
                "name": applicant.name,
                "program_name": frappe.db.get_value("Program", applicant.program, "program_name") or applicant.program or "Application",
                "program_slug": frappe.db.get_value("Program", applicant.program, "program_slug") or "",
                "cycle": applicant.admission_cycle or "—",
                "status": status,
                "status_color": style["color"],
                "status_bg": style["bg"],
                "submitted_on": frappe.utils.formatdate(applicant.creation, "dd MMM yyyy"),
                "current_stage": applicant.current_stage or "Pending"
            },
            "personal": [
                {"label": "Full Name", "value": applicant.candidate_name},
                {"label": "Date of Birth", "value": frappe.utils.formatdate(applicant.date_of_birth, "dd MMM yyyy") if applicant.date_of_birth else None},
                {"label": "Gender", "value": applicant.gender},
                {"label": "Nationality", "value": applicant.nationality},
                {"label": "Email", "value": applicant.email},
                {"label": "Mobile Number", "value": applicant.mobile_number},
                {"label": "Religion", "value": applicant.religion},
                {"label": "Annual Household Income", "value": applicant.annual_house_hold_income}
            ],
            "academic": [
                {"label": "Class X Percentage", "value": applicant.class_x_percentage},
                {"label": "Class X Board", "value": applicant.class_x_board},
                {"label": "Class X Year", "value": applicant.class_x_year_of_completion},
                {"label": "Class XII Percentage", "value": applicant.hsc_percentage or applicant.percentage},
                {"label": "Class XII Board", "value": applicant.class_xii_board},
                {"label": "Class XII Year", "value": applicant.class_xii_year_of_completion},
                {"label": "Program Level", "value": applicant.program_level}
            ],
            "application": [
                {"label": "Application ID", "value": applicant.name},
                {"label": "Program", "value": applicant.program},
                {"label": "Admission Cycle", "value": applicant.admission_cycle},
                {"label": "Fee Status", "value": applicant.application_fee_status},
                {"label": "Merit Score", "value": applicant.merit_score if hasattr(applicant, 'merit_score') else "—"}
            ]
        }
        
        context.app_summary = app_summary
        
        # Build action buttons
        actions = []
        if status == "Draft":
            actions.append({"label": "Continue Application", "url": f"/application-form/{applicant.name}", "class": "btn-primary-adm"})
        else:
            actions.append({"label": "View / Edit Form", "url": f"/application-form/{applicant.name}", "class": "btn-outline-adm"})
            
        if status == "Offer Issued":
            actions.append({"label": "Accept Offer", "url": f"/application-form/{applicant.name}", "class": "btn-primary-adm", "style": "background:#059669"})
            
        if app_summary["header"]["program_slug"]:
            actions.append({"label": "View Program", "url": f"/admission/{app_summary['header']['program_slug']}", "class": "btn-outline-adm"})
            
        context.action_buttons = actions
    else:
        context.applicant = None
        context.candidate_name = frappe.db.get_value("User", frappe.session.user, "full_name") or "Candidate"

    context.no_cache = 1
    context.title = "My Applications"
