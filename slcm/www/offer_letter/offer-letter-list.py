import frappe
from frappe import _

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    context.title = _("Offer Letter List")
    context.no_cache = 1
