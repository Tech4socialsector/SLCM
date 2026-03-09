import frappe

def get_context(context):
    context.portal_config = frappe.get_single("Applicant Portal Config")
    context.show_sidebar = True
    context.no_cache = 1
    
    # Get applicant data if logged in and has an application
    if frappe.session.user != "Guest":
        applicant = frappe.get_all("Applicant", filters={"email": frappe.session.user}, limit=1)
        if applicant:
            context.applicant = frappe.get_doc("Applicant", applicant[0].name)
        else:
            context.applicant = None
    else:
        context.applicant = None

    # Fetch dynamic data for selects/links
    context.nationalities = frappe.get_all("Country", fields=["name"])
    # context.programs = frappe.get_all("Program", fields=["name", "title"])
    # filters can be applied based on config
    # ...
    
    return context
