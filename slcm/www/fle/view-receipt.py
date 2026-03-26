import frappe

no_cache = True


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/fle/login"
        raise frappe.Redirect

    docname = frappe.form_dict.get("docname")
    if not docname:
        frappe.local.flags.redirect_location = "/fle/enrolled"
        raise frappe.Redirect

    if not frappe.db.exists("Foundations for a Legal Education", docname):
        frappe.throw("Document not found", frappe.DoesNotExistError)

    doc = frappe.get_doc("Foundations for a Legal Education", docname)

    if frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw("Not permitted", frappe.PermissionError)

    context.docname = docname
