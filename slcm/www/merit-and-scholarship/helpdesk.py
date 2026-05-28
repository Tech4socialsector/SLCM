import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/admission/login"
        raise frappe.Redirect

    # ── Portal config (colours, fonts, mission text) ───────────────
    from slcm.admission.utils.portal import get_portal_config
    try:
        cfg = get_portal_config()
        context.portal_config = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
    except Exception:
        context.portal_config = {}

    # ── Mission text (used by the sidebar) ────────────────────────
    pc = context.portal_config
    context._mission_txt = (pc.get("mission_text") if callable(getattr(pc, "get", None)) else getattr(pc, "mission_text", "")) or ""

    context.title = _("Help Desk")
    return context
