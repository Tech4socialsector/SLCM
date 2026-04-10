import frappe

@frappe.whitelist(allow_guest=True)
def get_pace_programmes(academic_year=None):
    """
    Fetches the programmes child table rows for the active PACE Admission record.
    Filters by academic_year if provided. Handles guest access if it's for public pages.
    """
    # Define query filters for active PACE Admission record
    filters = {"active": 1}
    if academic_year:
        filters["academic_year"] = academic_year

    # Get the latest active admission record name based on filters
    pace_admission = frappe.db.get_value("PACE Admission", filters, "name", order_by="creation desc")

    if not pace_admission:
        # Return an empty list as per requirement if no active admission found
        return []

    # Query the child table "PACE Admission Programme" for the found parent record.
    # We fetch the specific fields identified from the child DocType JSON.
    programmes = frappe.get_all("PACE Admission Programme", 
        filters={"parent": pace_admission, "parenttype": "PACE Admission"}, 
        fields=[
            "programme", 
            "total_seats", 
            "max_applications", 
            "application_received", 
            "appliocation_fee_indian",
            "appliocation_fee_foreign"
        ],
        order_by="idx asc"
    )

    return programmes
