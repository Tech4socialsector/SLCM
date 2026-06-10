import frappe
from frappe.utils import cint

@frappe.whitelist()
def test():
    # mock request
    frappe.local.request = frappe._dict({"args": {}})
    frappe.local.session = frappe._dict({"data": frappe._dict({"csrf_token": ""})})
    frappe.session.user = "Guest"
    
    # Test pace login context
    import slcm.www.pace.login as pace_login
    context = frappe._dict()
    try:
        pace_login.get_context(context)
    except Exception as e:
        print("get_context error:", e)
        import traceback
        traceback.print_exc()
    
    print("PACE is_closed:", context.is_closed)
    print("PACE disable_signup:", context.disable_signup)
