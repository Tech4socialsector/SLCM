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
                full_path += "?" + query_string

            encoded_url = urllib.parse.quote(full_path, safe='')

            if "pace" in path:
                raise AuthRedirect(f"/pace/login?redirect-to={encoded_url}")
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
        applicant_route = (frappe.get_cached_value("Web Form", "applicant-form", "route") or "admission/application-form").strip("/")
        pace_route = (frappe.get_cached_value("Web Form", "pace-application-form", "route") or "paceadmissions/application-form").strip("/")

        if (normalized_path.startswith(pace_route) or normalized_path.startswith("pace-application-form")):
            raise AuthRedirect(f"/paceadmissions/login?redirect-to={encoded_url}#register")
        elif (normalized_path.startswith(applicant_route) or normalized_path.startswith("applicant-form")):
            raise AuthRedirect(f"/admission/login?redirect-to={encoded_url}#register")

        if path.startswith("/student-portal"):
            encoded_url = urllib.parse.quote(path, safe='')
            raise AuthRedirect(f"/student/login?redirect-to={encoded_url}")

        if path.startswith("/faculty-portal"):
            encoded_url = urllib.parse.quote(path, safe='')
            raise AuthRedirect(f"/faculty/login?redirect-to={encoded_url}")

        if path.startswith("/parent-portal"):
            encoded_url = urllib.parse.quote(path, safe='')
            raise AuthRedirect(f"/parent/login?redirect-to={encoded_url}")

    elif frappe.session.user != "Guest":
        applicant_route = (frappe.get_cached_value("Web Form", "applicant-form", "route") or "admission/application-form").strip("/")
        pace_route = (frappe.get_cached_value("Web Form", "pace-application-form", "route") or "paceadmissions/application-form").strip("/")
        
        is_application_form = False
        base_route = ""
        if normalized_path in (pace_route, f"{pace_route}/new", "pace-application-form", "pace-application-form/new"):
            is_application_form = True
            base_route = pace_route
        elif normalized_path in (applicant_route, f"{applicant_route}/new", "applicant-form", "applicant-form/new"):
            is_application_form = True
            base_route = applicant_route

        if is_application_form:
            active_cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, ["name", "allow_multiple_applications"], as_dict=True)
            if active_cycle:
                requested_program = frappe.form_dict.get("program") or ""
                allow_multiple = int(active_cycle.allow_multiple_applications or 0)
                
                filters = {
                    "email": frappe.session.user,
                    "admission_cycle": active_cycle.name
                }
                
                if allow_multiple:
                    if requested_program:
                        filters["program"] = requested_program
                        existing_app = frappe.db.exists("Applicant", filters)
                        if existing_app:
                            raise AuthRedirect(f"/{base_route}/{existing_app}")
                else:
                    # If multiple applications are not allowed, ANY application in this cycle counts
                    # If requested_program is present, try to match it first just in case
                    if requested_program:
                        exact_match_filters = filters.copy()
                        exact_match_filters["program"] = requested_program
                        existing_app = frappe.db.exists("Applicant", exact_match_filters)
                        if existing_app:
                            raise AuthRedirect(f"/{base_route}/{existing_app}")
                    
                    # Otherwise get the most recent application
                    existing_app = frappe.db.get_value("Applicant", filters, "name", order_by="creation desc")
                    if existing_app:
                        raise AuthRedirect(f"/{base_route}/{existing_app}")

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
        elif logged_out_from == "student":
            raise AuthRedirect("/student/login")
        elif logged_out_from == "faculty":
            raise AuthRedirect("/faculty/login")
        elif logged_out_from == "parent":
            raise AuthRedirect("/parent/login")

        # Normal fallback if no logout cookie is found
        redirect_to = frappe.form_dict.get("redirect-to") or frappe.form_dict.get("redirect_to") or ""

        if "/pace-application-form" in redirect_to or "/pace/" in redirect_to:
            target = "/pace/login"
        
        if "/paceadmissions/application-form" in redirect_to or "/pace/" in redirect_to or "/paceadmissions" in redirect_to:
            target = "/paceadmissions/login"
        elif "/applicant-form" in redirect_to or "/admission/" in redirect_to:
            target = "/admission/login"
        elif "/student-portal" in redirect_to or "/student/" in redirect_to:
            target = "/student/login"
        elif "/faculty-portal" in redirect_to or "/faculty/" in redirect_to:
            target = "/faculty/login"
        elif "/parent-portal" in redirect_to or "/parent/" in redirect_to:
            target = "/parent/login"
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
    elif "/student-portal" in referrer or "/student/" in referrer:
        target = "student"
    elif "/faculty-portal" in referrer or "/faculty/" in referrer:
        target = "faculty"
    elif "/parent-portal" in referrer or "/parent/" in referrer:
        target = "parent"
    else:
        # 2. If referrer is ambiguous or other page, use roles:
        if "System Manager" in roles or "Desk User" in roles or user == "Administrator":
            target = "desk"
        elif "PACE Applicant" in roles:
            target = "paceadmissions"
        elif "Applicant" in roles:
            target = "admission"
        elif "slcm_student" in roles or "Student" in roles:
            target = "student"
        elif "slcm_faculty" in roles or "Faculty" in roles:
            target = "faculty"
        elif "slcm_parent" in roles or "Parent" in roles:
            target = "parent"
        else:
            target = "desk"
            
    if target and hasattr(frappe.local, "cookie_manager") and frappe.local.cookie_manager:
        frappe.local.cookie_manager.set_cookie("logged_out_from", target)

