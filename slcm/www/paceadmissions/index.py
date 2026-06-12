import frappe


def get_context(context):
    frappe.local.flags.redirect_location = "/paceadmissions/login"
    raise frappe.Redirect
