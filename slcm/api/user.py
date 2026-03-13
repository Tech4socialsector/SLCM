import frappe
from frappe.core.doctype.user.user import sign_up

@frappe.whitelist(allow_guest=True)
def custom_sign_up(email, full_name, mobile_no=None, redirect_to=None):
    # Proactively check for existing email or mobile number
    if frappe.db.exists("User", email):
        return [0, "Email address already registered"]
    
    if mobile_no and frappe.db.exists("User", {"mobile_no": mobile_no}):
        return [0, "Mobile number already registered"]

    try:
        res = sign_up(email, full_name, redirect_to)
        if res and res[0] == 1 and mobile_no:
            # Update mobile_no for the newly created user
            frappe.db.set_value("User", email, "mobile_no", mobile_no)
            frappe.db.commit()
        return res
    except Exception as e:
        if "Duplicate entry" in str(e):
            if "mobile_no" in str(e):
                return [0, "Mobile number already registered"]
            return [0, "Email address already registered"]
        return [0, str(e)]

@frappe.whitelist()
def get_districts(state):
    return frappe.get_all("District", filters={"state": state}, fields=["name"], order_by="name asc")

@frappe.whitelist()
def get_user_details():
    user = frappe.session.user
    if user == "Guest":
        return {}
    
    return frappe.db.get_value("User", user, 
        ["name", "full_name", "email", "mobile_no", "user_image"], as_dict=True)

@frappe.whitelist()
def get_login_redirect():
    user = frappe.session.user
    if user == "Guest":
        return "/login"
    
    user_type = frappe.db.get_value("User", user, "user_type")
    if user_type == "System User":
        return "/app"
    else:
        return "/admission"
