import frappe
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard, get_applied_scholarships_for_dashboard

no_cache = 1

def get_context(context):
    context.portal_config = get_portal_config()
    _user = frappe.session.user
    
    if _user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/merit-and-scholarship/scholarships"
        raise frappe.Redirect

    try:
        # Get all applications to fetch applicable scholarships
        apps_by_owner = frappe.get_all(
            "Applicant",
            filters={"owner": _user},
            fields=["name", "program", "application_status", "admission_cycle", "campus", "modified"],
            ignore_permissions=True
        )
        apps_by_email = frappe.get_all(
            "Applicant",
            filters={"email": _user},
            fields=["name", "program", "application_status", "admission_cycle", "campus", "modified"],
            ignore_permissions=True
        )
        combined = {a.name: a for a in (apps_by_owner + apps_by_email)}
        my_apps = sorted(combined.values(), key=lambda x: x.modified, reverse=True)

        available_scholarships = []
        applied_scholarships = []
        seen_schemes = set()
        seen_applications = set()
        
        for app in my_apps:
            # Get Applied
            apps = get_applied_scholarships_for_dashboard(app.name)
            for a in apps:
                if a.name not in seen_applications:
                    a["scheme_name"] = frappe.db.get_value("Scholarship Scheme", a.scholarship_scheme, "scheme_name") or a.scholarship_scheme
                    applied_scholarships.append(a)
                    seen_applications.add(a.name)

            if not all([app.admission_cycle, app.campus, app.program]):
                continue
                
            # Get Available
            schemes = get_available_scholarships_for_dashboard(
                app.name, 
                app.admission_cycle, 
                app.campus, 
                app.program, 
                [app.application_status] if app.application_status else []
            )
            for s in schemes:
                if s.name not in seen_schemes:
                    available_scholarships.append(s)
                    seen_schemes.add(s.name)
        
        context.scholarships = available_scholarships
        context.applied_scholarships = sorted(applied_scholarships, key=lambda x: x.creation, reverse=True)
    except Exception as e:
        frappe.log_error(f"Scholarship list fetch failed: {e}", "Scholarship List")
        context.scholarships = []
        context.applied_scholarships = []

    return context
