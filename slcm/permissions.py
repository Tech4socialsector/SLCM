import frappe


# --------------------------------------------------
# Applicant Doctype - Email Based Restriction
# --------------------------------------------------

def applicant_query_conditions(user):

    roles = frappe.get_roles(user)

    # Full access roles
    if "Administrator" in roles or "Entrance Test Admin" in roles:
        return ""

    # Applicant role restriction
    if "Applicant" in roles:
        return f"`tabApplicant`.email = '{user}'"

    return ""


# --------------------------------------------------
# Entrance Test Seat Allocation - Email Based
# --------------------------------------------------

def seat_allocation_query_conditions(user):

    roles = frappe.get_roles(user)

    if "Administrator" in roles or "Entrance Test Admin" in roles:
        return ""

    if "Applicant" in roles:
        return f"`tabEntrance Test Seat Allocation`.email = '{user}'"

    return ""