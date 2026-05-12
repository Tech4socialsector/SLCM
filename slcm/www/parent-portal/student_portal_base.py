import frappe


def get_context(context):
    frappe.local.flags.redirect_location = "/parent-portal"
    raise frappe.Redirect
