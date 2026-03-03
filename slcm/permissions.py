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

# ==========================================================
# ENTRANCE TEST PROVIDER - SELF RECORD ONLY
# ==========================================================

def entrance_test_provider_query_conditions(user):

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    if "Entrance Test Provider" in roles:

        provider_name = frappe.db.get_value(
            "Entrance Test Provider",
            {"user": user},
            "name"
        )

        if not provider_name:
            return "1=0"

        return f"`tabEntrance Test Provider`.name = '{provider_name}'"

    return ""


# ==========================================================
# ENTRANCE TEST SEAT ALLOCATION - STRICT PROVIDER FILTER
# ==========================================================

def seat_allocation_query_conditions(user):

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    # 🔹 ENTRANCE TEST PROVIDER FILTER
    if "Entrance Test Provider" in roles:

        provider_name = frappe.db.get_value(
            "Entrance Test Provider",
            {"user": user},
            "name"
        )

        if not provider_name:
            return "1=0"

        # IMPORTANT: filter using Link field
        return f"`tabEntrance Test Seat Allocation`.entrance_test_provider = '{provider_name}'"

    # 🔹 APPLICANT FILTER (if applicable)
    if "Applicant" in roles:
        return f"`tabEntrance Test Seat Allocation`.email = '{user}'"

    return ""    
# ==========================================================
# INTERVIEW STAFF MEMBER - SELF RECORD ONLY
# ==========================================================

def interview_staff_member_query_conditions(user):

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    if "Interview Staff Member" in roles:

        staff_name = frappe.db.get_value(
            "Interview Staff Member",
            {"user": user},
            "name"
        )

        if not staff_name:
            return "1=0"

        return f"`tabInterview Staff Member`.name = '{staff_name}'"

    return ""


# ==========================================================
# INTERVIEW SEAT ALLOCATION - ROLE BASED FILTER
# ==========================================================

def interview_seat_allocation_query_conditions(user):

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    # -----------------------------
    # Applicant Restriction
    # -----------------------------
    if "Applicant" in roles:
        return f"`tabInterview Seat Allocation`.email = '{user}'"

    # -----------------------------
    # Interview Staff Member Restriction
    # -----------------------------
    if "Interview Staff Member" in roles:

        staff_name = frappe.db.get_value(
            "Interview Staff Member",
            {"user": user},
            "name"
        )

        if not staff_name:
            return "1=0"

        return f"`tabInterview Seat Allocation`.interview_staff_member = '{staff_name}'"

    return ""