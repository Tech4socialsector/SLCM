import frappe
from frappe import _
from frappe.utils import random_string

@frappe.whitelist(allow_guest=True)
def register_fle_user(email, mobile_number):
    if not email or not mobile_number:
        frappe.throw(_("Email and Mobile Number are mandatory"))

    if frappe.db.exists("User", email):
        frappe.throw(_("User with this email already exists."))
        
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": email.split('@')[0],
            "mobile_no": mobile_number,
            "enabled": 1,
            "new_password": random_string(10),
            "user_type": "Website User",
            "send_welcome_email": 1,
        }
    )
    
    user.flags.ignore_permissions = True
    user.flags.ignore_password_policy = True
    user.insert()

    default_role = frappe.get_single_value("Portal Settings", "default_role")
    if default_role:
        user.add_roles(default_role)

    frappe.cache.hset("redirect_after_login", user.name, "/foundations-for-a-legal-education")

    return {"status": "success", "message": "Check your email to set your password and activate your account!"}

@frappe.whitelist(allow_guest=True)
def login_fle_user(usr, pwd):
    from frappe.auth import LoginManager
    try:
        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["message"] = "Incorrect password"
        return

    frappe.local.response["message"] = "Logged In"

    # Get the user to fetch email and mobile
    user_doc = frappe.get_doc("User", usr)
    email = user_doc.email or ""
    mobile = user_doc.mobile_no or ""
    
    import urllib.parse
    query_params = urllib.parse.urlencode({"email": email, "mobile": mobile})
    
    frappe.local.response["home_page"] = f"/foundations-for-a-legal-education/new?{query_params}"
