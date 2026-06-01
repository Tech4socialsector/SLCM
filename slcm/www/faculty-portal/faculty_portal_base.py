import frappe


def get_context(context):
    frappe.local.flags.redirect_location = "/faculty-portal"
    raise frappe.Redirect
