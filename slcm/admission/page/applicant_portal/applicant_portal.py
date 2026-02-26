import frappe

def get_context(context):
    """
    Page is publicly accessible — no redirect for guests.
    Login is only required when applicant clicks Apply Now.
    The JS handles the login redirect at action time.
    """
    context.no_cache = 1
    return context
