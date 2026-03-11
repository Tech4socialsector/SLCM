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
            "send_welcome_email": 0,
            "redirect_url": "/fle/login.html",
        }
    )
    
    user.flags.ignore_permissions = True
    user.flags.ignore_password_policy = True
    user.insert()

    # Generate the password reset link silently (without emailing)
    frappe_link = user.reset_password(send_email=False)
    
    # Extract the path + query (e.g., /update-password?key=XYZ)
    import urllib.parse
    parsed = urllib.parse.urlparse(frappe_link)
    
    # Rebuild the link using frappe.utils.get_url which picks up the request host/port correctly
    from frappe.utils import get_url
    correct_link = get_url(parsed.path + "?" + parsed.query)
    
    # Prepare and send the welcome email
    site_name = frappe.db.get_default("site_name") or frappe.get_conf().get("site_name")
    subject = _("Welcome to {0}").format(site_name) if site_name else _("Complete Registration")
    welcome_email_template = frappe.db.get_system_setting("welcome_email_template")

    user.send_login_mail(
        subject,
        "new_user",
        dict(link=correct_link, site_url=get_url()),
        custom_template=welcome_email_template,
    )

    default_role = frappe.get_single_value("Portal Settings", "default_role")
    if default_role:
        user.add_roles(default_role)

    # Reliable fallback cache assignment
    frappe.cache().hset("redirect_after_login", user.name, "/fle/login.html")
    
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
    import base64
    
    query_params = urllib.parse.urlencode({
        "email_address": email,
        "candidate_contact_number": mobile
    })
    
    frappe.local.response["home_page"] = f"/foundations-for-a-legal-education/new?{query_params}"

@frappe.whitelist(allow_guest=True)
def get_payment_status(docname):
    if not docname:
        return {}
        
    if not frappe.db.exists("Foundations for a Legal Education", docname):
        return {}
        
    doc = frappe.get_doc("Foundations for a Legal Education", docname)
    
    # Allow if session user is the owner, or if they have System Manager role
    if frappe.session.user != "Guest" and frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            return {}
            
    return {
        "payment_status": doc.payment_status,
        "docstatus": doc.docstatus
    }
