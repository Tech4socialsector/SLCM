import frappe

login_required = True

def get_context(context):
    # Import and run the existing dashboard controller
    # Frappe converts hyphens to underscores in module paths
    try:
        from slcm.www.merit_and_scholarship.admission_dashboard import get_context as _get
        _get(context)
    except ImportError:
        # Fallback if the above fails
        from slcm.www.merit_and_scholarship import admission_dashboard
        admission_dashboard.get_context(context)
