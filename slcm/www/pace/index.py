import frappe


def get_context(context):
    context.no_cache = 1
    try:
        pc = frappe.get_single("Applicant Portal Config")
        if not int(pc.get("enable_pace_admission") or 0):
            raise frappe.PageDoesNotExistError
    except frappe.PageDoesNotExistError:
        raise
    except Exception:
        # If config is missing/misconfigured, don't expose the page publicly.
        raise frappe.PageDoesNotExistError
