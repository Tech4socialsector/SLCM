import frappe
from frappe import _

from slcm.admission.utils.portal import get_portal_config

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    # Portal config
    try:
        cfg = get_portal_config()
        context.portal_config = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
    except Exception:
        context.portal_config = {}

    context.title = _("Offer Letter Detail")
    context.no_cache = 1
