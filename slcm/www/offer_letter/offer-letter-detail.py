import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    
    context.title = _("Offer Letter Detail")
    context.no_cache = 1
