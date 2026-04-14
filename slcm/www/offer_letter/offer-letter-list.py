import frappe
from frappe import _

from slcm.admission.utils.portal import get_portal_config

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Portal config
    try:
        cfg = get_portal_config()
        context.portal_config = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
    except Exception:
        context.portal_config = {}

    context.title = _("Offer Letter List")
    context.no_cache = 1

    # ── PACE Applications Count ──────────────────────────────────
    _user = frappe.session.user
    context._pace_enabled = frappe.db.get_single_value("Applicant Portal Config", "enable_pace_admission")
    if context._pace_enabled:
        context.pace_app_count = frappe.db.count("PACE Application", {"owner": _user})
