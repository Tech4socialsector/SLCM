import frappe


# ==========================================================
# STUDENT MASTER - STATUS-BASED ACCESS CONTROL
# ==========================================================
#
# Each registration-workflow role sees only the students that
# are currently in *their* workflow stage.
#
# Admin-level roles (System Manager, slcm_Registrar, Accounts User)
# see every record without restriction.
#
# slcm_Faculty / slcm_Programme Chair see all *academically active*
# students (academic_status = 'Active').
#
# slcm_Student sees only their own record (matched by email).

# Map  role  →  tuple of registration_status values visible to that role
_WORKFLOW_ROLE_STATUS_MAP = {
    "slcm_REGO Officer":          ("Pending REGO",),
    "slcm_FINO Officer":          ("Pending FINO",),
    # Registration Officer handles two stages: intake + final approval
    "slcm_Registration Officer":  ("Pending Registration", "Final Verification REGO"),
    "slcm_Documentation Officer": ("Pending Print & Scan",),
    "slcm_Hostel Admin":          ("Pending Residences",),
    "slcm_Hostel Warden":         ("Pending Residences",),
    "slcm_IT Admin":              ("Pending IT", "Final Verification REGO"),
    # Registration User only needs to see students awaiting submission
    "slcm_Registration User":     ("Selected",),
}

# Roles that can see *all* Student Master records
_FULL_ACCESS_ROLES = {"System Manager", "slcm_Registrar", "Accounts User"}

# Roles that see only academically-active students
_ACTIVE_STUDENTS_ROLES = {"slcm_Faculty", "slcm_Programme Chair"}


def student_master_query_conditions(user):
    """
    Called by Frappe for every Student Master list/search query.

    Returns a raw SQL WHERE fragment (without the WHERE keyword) or "" for
    unrestricted access.  Returning "1=0" denies access completely.
    """
    if user == "Administrator":
        return ""

    roles = set(frappe.get_roles(user))

    # --- Full access ---
    if roles & _FULL_ACCESS_ROLES:
        return ""

    # --- Faculty / Programme Chair: only see active enrolled students ---
    if roles & _ACTIVE_STUDENTS_ROLES:
        return "`tabStudent Master`.academic_status = 'Active'"

    # --- Registration workflow roles: stage-specific view ---
    for role, statuses in _WORKFLOW_ROLE_STATUS_MAP.items():
        if role in roles:
            status_list = ", ".join(f"'{s}'" for s in statuses)
            return f"`tabStudent Master`.registration_status IN ({status_list})"

    # --- Student: own record only (matched by email) ---
    if "slcm_Student" in roles:
        safe_user = user.replace("'", "\\'")
        return f"`tabStudent Master`.email = '{safe_user}'"

    # Deny by default – unknown roles should not see Student Master
    return "1=0"


# ==========================================================
# APPLICANT – EMAIL-BASED RESTRICTION
# ==========================================================

def applicant_query_conditions(user):

    roles = frappe.get_roles(user)

    # Full access roles
    if "Administrator" in roles or "Entrance Test Admin" in roles:
        return ""

    # Applicant role restriction
    if "Applicant" in roles:
        return f"`tabApplicant`.email = '{user}'"

    return ""


# ==========================================================
# ENTRANCE TEST PROVIDER – SELF RECORD ONLY
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
# ENTRANCE TEST SEAT ALLOCATION – STRICT PROVIDER FILTER
# ==========================================================

def seat_allocation_query_conditions(user):

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    if "Entrance Test Admin" in roles:
        return ""

    if "Entrance Test Provider" in roles:

        provider_name = frappe.db.get_value(
            "Entrance Test Provider",
            {"user": user},
            "name"
        )

        if not provider_name:
            return "1=0"

        return f"`tabEntrance Test Seat Allocation`.entrance_test_provider = '{provider_name}'"

    if "Applicant" in roles:
        return f"`tabEntrance Test Seat Allocation`.email = '{user}'"

    return ""


# ==========================================================
# INTERVIEW STAFF MEMBER – SELF RECORD ONLY
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
# INTERVIEW SEAT ALLOCATION – ROLE-BASED FILTER
# ==========================================================

def interview_seat_allocation_query_conditions(user):

    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    if "Applicant" in roles:
        return f"`tabInterview Seat Allocation`.email = '{user}'"

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
