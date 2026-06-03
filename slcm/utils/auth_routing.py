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
    path = frappe.local.request.path
    
    # 1. Intercept Guest hitting protected Web Forms directly BEFORE Frappe drops the query params
    if frappe.session.user == "Guest":
        if path.startswith("/pace-application-form") or path.startswith("/applicant-form"):
            query_string = frappe.local.request.query_string.decode('utf-8')
            full_path = path
            if query_string:
                full_path += "?" + query_string
                
            encoded_url = urllib.parse.quote(full_path, safe='')
            
            if "pace" in path:
                raise AuthRedirect(f"/pace/login?redirect-to={encoded_url}")
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
        elif logged_out_from == "pace":
            raise AuthRedirect("/pace/login")
        elif logged_out_from == "admission":
            raise AuthRedirect("/admission/login")
            
        # Normal fallback if no logout cookie is found
        redirect_to = frappe.form_dict.get("redirect-to") or frappe.form_dict.get("redirect_to") or ""
        
        if "/pace-application-form" in redirect_to or "/pace/" in redirect_to:
            target = "/pace/login"
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
    elif "/pace" in referrer:
        target = "pace"
    elif "/admission" in referrer or "/applicant" in referrer:
        target = "admission"
    else:
        # 2. If referrer is ambiguous or other page (like /merit-and-scholarship), use roles:
        if "System Manager" in roles or "Desk User" in roles or user == "Administrator":
            target = "desk"
        elif "PACE Applicant" in roles:
            target = "pace"
        elif "Applicant" in roles:
            target = "admission"
        else:
            target = "desk"
            
    if target and hasattr(frappe.local, "cookie_manager") and frappe.local.cookie_manager:
        frappe.local.cookie_manager.set_cookie("logged_out_from", target)

