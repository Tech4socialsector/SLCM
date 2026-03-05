import frappe
from slcm.admission.utils.portal import get_portal_config

def get_context(context):
    # 1. Fetch Portal Config
    try:
        cfg = get_portal_config()
        context.portal_config = cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
    except Exception:
        context.portal_config = {}

    # 2. Fetch Active Cycle
    context.active_cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name") or ""

    # 3. Candidate Info
    if frappe.session.user != "Guest":
        context.candidate_name = frappe.db.get_value("User", frappe.session.user, "full_name")
    
    # 4. Pass Website Settings
    context.website_settings = frappe.get_doc("Website Settings")
