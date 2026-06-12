import frappe
import urllib.parse
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

class AuthRedirect(HTTPException):
    def __init__(self, location):
        super().__init__()
        self.location = location

    def get_response(self, environ=None):
        return Response(
            f'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
            f'<title>Redirecting...</title>\n'
            f'<h1>Redirecting...</h1>\n'
            f'<p>You should be redirected automatically to target URL: '
            f'<a href="{self.location}">{self.location}</a>. If not click the link.</p>',
            status=302,
            mimetype="text/html",
            headers={"Location": self.location}
        )

def intercept_login():
    try:
        path = frappe.local.request.path
    except Exception:
        path = (getattr(frappe.local, "path_info", "") or "").strip("/")
        if path:
            path = "/" + path
    
    if not path:
        return

    normalized_path = path.strip("/").lower()

    # Dynamically capture current URL including query params for redirect
    full_path = path
    try:
        if hasattr(frappe.local, "request") and frappe.local.request.query_string:
            query_string = frappe.local.request.query_string.decode('utf-8')
            if query_string:
                full_path = f"{path}?{query_string}"
    except Exception:
        pass

    # IMPORTANT: Prevent redirect loops if the current path is already a login path
    if "paceadmissions/login" in full_path.lower() or "admission/login" in full_path.lower():
        return

    encoded_url = urllib.parse.quote(full_path, safe='')

    # 0. Guard /paceadmissions route based on Applicant Portal Config
    if (normalized_path == "paceadmissions" or 
        normalized_path.startswith("paceadmissions/") or 
        normalized_path.startswith("pace-application-form")):
        
        # Don't block the login or forgot_password pages themselves
        if not (normalized_path.startswith("paceadmissions/login") or 
                normalized_path.startswith("paceadmissions/forgot_password")):
            
            enable_pace_site = frappe.db.get_single_value("Applicant Portal Config", "enable_pace_site")
            if not int(enable_pace_site or 0):
                # ONLY redirect guests to login. Logged-in users should be allowed to proceed
                # (or they will be stopped by standard permission checks if they don't have roles).
                if frappe.session.user == "Guest":
                    raise AuthRedirect(f"/paceadmissions/login?redirect-to={encoded_url}#register")

    # 1. Intercept Guest hitting protected Web Forms directly BEFORE Frappe drops the query params
    if frappe.session.user == "Guest":
        if (normalized_path.startswith("paceadmissions/application-form") or 
            normalized_path.startswith("pace-application-form") or 
            normalized_path.startswith("applicant-form")):
            
            if "pace" in normalized_path:
                # Redirect to login with #register tab active and return to the SPECIFIC page after login
                raise AuthRedirect(f"/paceadmissions/login?redirect-to={encoded_url}#register")
            else:
                raise AuthRedirect(f"/admission/login?redirect-to={encoded_url}")
                
    # 2. Intercept the standard Frappe /login fallback
    if path == "/login":
        if frappe.session.user != "Guest":
            return
            
        # Check if we have a logged_out_from cookie
        logged_out_from = ""
        if hasattr(frappe.local, "request") and frappe.local.request:
            logged_out_from = frappe.local.request.cookies.get("logged_out_from") or ""
            
        # We must clear the cookie so it doesn't affect subsequent logins/actions
        if hasattr(frappe.local, "cookie_manager") and frappe.local.cookie_manager:
            frappe.local.cookie_manager.delete_cookie("logged_out_from")
            
        if logged_out_from:
            logged_out_from = urllib.parse.unquote(logged_out_from)
            
        if logged_out_from == "desk":
            # Show the standard/default Frappe login page (return without redirecting)
            return
        elif logged_out_from == "pace" or logged_out_from == "paceadmissions":
            raise AuthRedirect("/paceadmissions/login")
        elif logged_out_from == "admission":
            raise AuthRedirect("/admission/login")
            
        # Normal fallback if no logout cookie is found
        redirect_to = frappe.form_dict.get("redirect-to") or frappe.form_dict.get("redirect_to") or ""
        
        if "/paceadmissions/application-form" in redirect_to or "/pace/" in redirect_to or "/paceadmissions" in redirect_to:
            target = "/paceadmissions/login"
        elif "/applicant-form" in redirect_to or "/admission/" in redirect_to:
            target = "/admission/login"
        else:
            target = "/admission/login"
            
        encoded_redirect = urllib.parse.quote(redirect_to, safe='')
        location = f"{target}?redirect-to={encoded_redirect}"
        
        raise AuthRedirect(location)

def handle_logout(login_manager=None):
    user = getattr(login_manager, "user", None) or frappe.session.user
    if not user or user == "Guest":
        return
        
    roles = frappe.get_roles(user)
    
    # Check referrer to see if they logged out from pace, admission or desk
    req = getattr(frappe.local, "request", None)
    referrer = req.headers.get("Referer", "") if req else ""
    
    target = None
    
    # 1. Referrer checks first for explicit paths
    if "/desk" in referrer or "/app" in referrer:
        target = "desk"
    elif "/paceadmissions" in referrer or "/pace" in referrer:
        target = "paceadmissions"
    elif "/admission" in referrer or "/applicant" in referrer:
        target = "admission"
    else:
        # 2. If referrer is ambiguous or other page (like /merit-and-scholarship), use roles:
        if "System Manager" in roles or "Desk User" in roles or user == "Administrator":
            target = "desk"
        elif "PACE Applicant" in roles:
            target = "paceadmissions"
        elif "Applicant" in roles:
            target = "admission"
        else:
            target = "desk"
            
    if target and hasattr(frappe.local, "cookie_manager") and frappe.local.cookie_manager:
        frappe.local.cookie_manager.set_cookie("logged_out_from", target)

