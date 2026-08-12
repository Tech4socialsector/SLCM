from urllib.parse import quote

import frappe

no_cache = 1


def get_context(context):
    # Student/Faculty/Parent login has been unified onto /login (with a
    # role tab). This page is kept only so old bookmarks/links still work.
    redirect_to = (
        frappe.local.request.args.get("redirect-to", "") or
        frappe.local.request.args.get("redirect_to", "") or
        frappe.local.request.args.get("redirect", "") or
        frappe.local.request.args.get("next", "")
    )
    error = frappe.local.request.args.get("error", "")

    target = f"/login?tab=faculty-student&redirect-to={quote(redirect_to, safe='')}"
    if error:
        target += f"&error={quote(error, safe='')}"

    frappe.local.flags.redirect_location = target
    raise frappe.Redirect
