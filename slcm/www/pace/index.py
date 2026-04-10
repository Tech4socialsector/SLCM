import frappe

from slcm.pace.api import get_pace_programmes


def get_context(context):
    context.no_cache = 1
    try:
        context.pace_programmes = get_pace_programmes()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "PACE index — get_pace_programmes")
        context.pace_programmes = []
