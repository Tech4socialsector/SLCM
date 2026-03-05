import frappe

login_required = False

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()
    
    name = frappe.form_dict.get("name") or ""
    if not name or not frappe.db.exists("Portal Announcement", {"name": name, "is_active": 1}):
        frappe.throw("Announcement not found or inactive", frappe.DoesNotExistError)
        
    ann = frappe.get_doc("Portal Announcement", name)
    context.announcement = ann
    context.no_cache = 1
    context.title = ann.title
