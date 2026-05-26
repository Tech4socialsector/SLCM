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
