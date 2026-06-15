import frappe

def get_context(context):
    context.no_cache = 1

    enable_pace_site = frappe.db.get_single_value("Applicant Portal Config", "enable_pace_site")
    if not enable_pace_site:
        raise frappe.PageDoesNotExistError()

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/paceadmissions/login"
        raise frappe.Redirect

