import frappe
from slcm.admission.utils.stage_control import get_current_stage

login_required = True

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/merit-and-schoarship/admission_dashboard"
        raise frappe.Redirect

    # Portal config for theme
    try:
        from slcm.admission.utils.portal import get_portal_config
        cfg = get_portal_config()
        context.portal_config = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
    except Exception:
        context.portal_config = {}

    context.candidate_name = (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user.split(" @")[0].title()
    )

    # Find all applications for this user
    applicants = frappe.get_all(
        "Applicant",
        filters=[["owner", "=", frappe.session.user]],
        fields=["name", "candidate_name", "program", "admission_cycle",
                "application_status", "intake_type", "creation",
                "current_stage", "merit_score"],
        order_by="creation desc"
    )

    STATUS_COLOR = {
        "Draft":          {"color": "#6b7280", "bg": "#f3f4f6"},
        "Submitted":      {"color": "#1d4ed8", "bg": "#dbeafe"},
        "Under Review":   {"color": "#d97706", "bg": "#fef3c7"},
        "Shortlisted":    {"color": "#059669", "bg": "#d1fae5"},
        "Waitlisted":     {"color": "#7c3aed", "bg": "#ede9fe"},
        "Offer Issued":   {"color": "#0369a1", "bg": "#e0f2fe"},
        "Offer Accepted": {"color": "#065f46", "bg": "#d1fae5"},
        "Rejected":       {"color": "#dc2626", "bg": "#fee2e2"},
        "Selected":       {"color": "#065f46", "bg": "#d1fae5"},
    }

    cards = []
    for a in applicants:
        program_name = frappe.db.get_value(
            "Program", a.program, "program_name"
        ) or a.program or "—"

        intake  = a.intake_type or "All"
        cycle   = a.admission_cycle or ""
        curr_st = None
        if cycle:
            try:
                curr_st = get_current_stage(cycle, intake)
            except Exception:
                pass

        status = a.application_status or "Draft"
        sc     = STATUS_COLOR.get(status, STATUS_COLOR["Draft"])

        cards.append({
            "name":          a.name,
            "program_name":  program_name,
            "cycle":         cycle or "—",
            "status":        status,
            "status_color":  sc["color"],
            "status_bg":     sc["bg"],
            "intake_type":   intake,
            "current_stage": a.current_stage or
                             (curr_st.stage_name if curr_st else "—"),
            "submitted_on":  frappe.utils.formatdate(a.creation, "dd MMM yyyy"),
            "detail_url":    "/my-applications",
        })

    context.application_cards  = cards
    context.has_applications   = len(cards) > 0
    context.title              = "My Applications"
    context.no_cache           = 1
