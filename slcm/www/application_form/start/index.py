# Application form "start" page: sets session from query params and redirects to /application_form.
# Use client-side redirect so the flow works regardless of server redirect handling.

import frappe

login_required = False


def get_context(context):
    if frappe.session.user == "Guest":
        context.redirect_url = "/login?redirect-to=/application_form"
        return

    program = (frappe.form_dict.get("program") or "").strip()
    admission_cycle = (frappe.form_dict.get("admission_cycle") or "").strip()
    if not program or not admission_cycle:
        context.redirect_url = "/admission"
        return

    exists = frappe.db.exists(
        "Admission Cycle Program",
        {"parent": admission_cycle, "program": program, "is_active": 1},
    )
    if not exists:
        context.redirect_url = "/admission"
        return

    sel = frappe.session.get("application_form_selection") or {}
    sel["program"] = program
    sel["admission_cycle"] = admission_cycle
    sel["campus"] = (frappe.form_dict.get("campus") or "").strip() or None
    sel["program_level"] = (frappe.form_dict.get("program_level") or "").strip() or None
    sel["intake_type"] = (frappe.form_dict.get("intake_type") or "").strip() or None
    frappe.session["application_form_selection"] = sel

    context.redirect_url = "/application_form"
