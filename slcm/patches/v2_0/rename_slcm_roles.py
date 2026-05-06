"""
Patch: rename_slcm_roles
========================
Renames all SLCM Student-Lifecycle module roles to follow the `slcm_` naming
convention so they are clearly distinguishable from built-in Frappe / ERPNext
roles and from Admission-module roles.

Admission-module roles (Applicant, Merit Admin, Scholarship Admin, etc.) are
intentionally left unchanged.

Run order: post_model_sync (all doctypes already exist before this runs).
"""

import frappe


# ---------------------------------------------------------------------------
# Role rename map
# old_name → new_name
# ---------------------------------------------------------------------------
ROLE_RENAMES = [
    ("Student",                   "slcm_Student"),
    ("Faculty",                   "slcm_Faculty"),
    ("SLCM Registrar",            "slcm_Registrar"),
    ("Programme Chair",           "slcm_Programme Chair"),
    ("Hostel Warden",             "slcm_Hostel Warden"),
    ("Placement Officer",         "slcm_Placement Officer"),
    # Student-registration workflow roles
    ("REGO Officer",              "slcm_REGO Officer"),
    ("FINO Officer",              "slcm_FINO Officer"),
    ("Registration Officer",      "slcm_Registration Officer"),
    ("Documentation Officer",     "slcm_Documentation Officer"),
    ("Residence / Hostel Admin",  "slcm_Hostel Admin"),
    ("IT Admin",                  "slcm_IT Admin"),
    ("Registration User",         "slcm_Registration User"),
]


def execute():
    for old_name, new_name in ROLE_RENAMES:
        _rename_role(old_name, new_name)

    frappe.db.commit()


def _rename_role(old_name: str, new_name: str) -> None:
    """
    Idempotent role rename.

    1. Skip entirely if the old role does not exist.
    2. Skip if both old and new already map to the same role (already done).
    3. Create the new role (if missing), migrate all DB references, then
       remove the old role record.
    """

    old_exists = frappe.db.exists("Role", old_name)
    new_exists = frappe.db.exists("Role", new_name)

    if not old_exists:
        # Already renamed in a previous run, or role never existed here.
        return

    if old_exists and not new_exists:
        # Create the new role with the same settings as the old one.
        old_doc = frappe.get_doc("Role", old_name)
        new_doc = frappe.new_doc("Role")
        new_doc.role_name = new_name
        new_doc.desk_access = old_doc.desk_access
        new_doc.disabled = old_doc.disabled
        new_doc.two_factor_auth = old_doc.two_factor_auth
        new_doc.restrict_to_domain = old_doc.restrict_to_domain
        new_doc.insert(ignore_permissions=True)

    # --- Migrate all DB references from old_name to new_name ---------------

    # 1. User role assignments
    frappe.db.sql(
        "UPDATE `tabHas Role` SET role = %(new)s WHERE role = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 2. DocPerm (role permissions defined on DocType)
    frappe.db.sql(
        "UPDATE `tabDocPerm` SET role = %(new)s WHERE role = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 3. Role Profile entries
    frappe.db.sql(
        "UPDATE `tabRole Profile Role` SET role = %(new)s WHERE role = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 4. Custom DocPerm (Role Permission Manager overrides)
    frappe.db.sql(
        "UPDATE `tabCustom DocPerm` SET role = %(new)s WHERE role = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 5. Workflow States (allow_edit)
    frappe.db.sql(
        "UPDATE `tabWorkflow State` SET allow_edit = %(new)s WHERE allow_edit = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 6. Workflow Transitions (allowed)
    frappe.db.sql(
        "UPDATE `tabWorkflow Transition` SET allowed = %(new)s WHERE allowed = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 7. User Permissions (if any use role field)
    frappe.db.sql(
        "UPDATE `tabUser Permission` SET role = %(new)s WHERE role = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # 8. Shared Documents
    frappe.db.sql(
        "UPDATE `tabDocShare` SET role = %(new)s WHERE role = %(old)s",
        {"new": new_name, "old": old_name},
    )

    # --- Remove the old role record ----------------------------------------
    frappe.db.delete("Role", {"name": old_name})

    frappe.logger().info(f"[slcm] Renamed role: '{old_name}' → '{new_name}'")
