import frappe
from slcm.admission.doctype.eligibility_result.eligibility_result import get_applicant_data
from slcm.admission.utils.portal import get_portal_config

def get_context(context):
    context.portal_config = get_portal_config()
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.unauthorized = True
        return context

    # ── Application cards (new) ──────────────────────────────────
    STATUS_STYLE = {
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

    applicants = frappe.get_all(
        "Applicant",
        filters=[["owner", "=", frappe.session.user]],
        fields=["name", "candidate_name", "program", "admission_cycle",
                "application_status", "intake_type", "creation", "current_stage"],
        order_by="creation desc"
    )

    cards = []
    for a in applicants:
        program_name = frappe.db.get_value(
            "Program", a.program, "program_name"
        ) or a.program or "—"

        # Get current active stage from cycle
        curr_stage = a.current_stage or ""
        if not curr_stage and a.admission_cycle:
            try:
                from slcm.admission.utils.stage_control import get_current_stage
                intake = a.intake_type or frappe.db.get_value(
                    "Program", a.program, "intake_type"
                ) or "All"
                s = get_current_stage(a.admission_cycle, intake)
                curr_stage = s.stage_name if s else "—"
            except Exception:
                curr_stage = "—"

        status = a.application_status or "Draft"
        sc = STATUS_STYLE.get(status, STATUS_STYLE["Draft"])

        cards.append({
            "name":         a.name,
            "program_name": program_name,
            "cycle":        a.admission_cycle or "—",
            "status":       status,
            "color":        sc["color"],
            "bg":           sc["bg"],
            "intake_type":  a.intake_type or "—",
            "stage":        curr_stage,
            "submitted_on": frappe.utils.formatdate(a.creation, "dd MMM yyyy"),
        })

    context.application_cards = cards
    context.has_applications = len(cards) > 0

    # ── Existing merit/scholarship data ─────────────────────────
    data = get_applicant_data()
    if isinstance(data, dict) and "error" in data:
        context.error = data["error"]
    else:
        context.applicant_data = data

    return context
