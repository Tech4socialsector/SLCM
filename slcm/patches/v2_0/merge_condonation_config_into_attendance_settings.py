"""
Patch: merge_condonation_config_into_attendance_settings
=========================================================
"Attendance Condonation Configuration" was a standalone singleton doctype
with its own page, separate from "Attendance Settings" where every other
attendance-related config (percentage thresholds, RFID, parent alerts,
condonation eligibility) already lives. This copies its saved values into
the new Condonation fields on Attendance Settings, then removes the old
doctype so admins only ever have one place to configure attendance.

Run order: after doctypes are migrated (both doctypes must already exist
with their final schema — Attendance Settings with the new condonation
fields, and the old Attendance Condonation Configuration still present so
its data can be read before being dropped).
"""

import frappe

FIELD_MAP = {
    "l1_assignment_email_template": "l1_assignment_email_template",
    "l1_approval_email_template": "l1_approval_email_template",
    "l1_rejected_email_template": "l1_rejected_email_template",
    "l1_due_days": "l1_due_days",
    "l1_last_assigned_index": "l1_last_assigned_index",
    "l2_assignment_email_template": "l2_assignment_email_template",
    "l2_approval_email_template": "l2_approval_email_template",
    "l2_rejected_email_template": "l2_rejected_email_template",
    "l2_due_days": "l2_due_days",
    "l2_last_assigned_index": "l2_last_assigned_index",
}

CHILD_TABLE_FIELDS = ["level_one_authority", "level_two_authority"]


def execute():
    if not frappe.db.exists("DocType", "Attendance Condonation Configuration"):
        # Already merged/removed in a previous run.
        return

    if not frappe.db.table_exists("Attendance Condonation Configuration"):
        _drop_old_doctype()
        return

    old = frappe.get_single("Attendance Condonation Configuration")
    settings = frappe.get_single("Attendance Settings")

    for old_fieldname, new_fieldname in FIELD_MAP.items():
        value = old.get(old_fieldname)
        if value:
            settings.set(new_fieldname, value)

    for table_fieldname in CHILD_TABLE_FIELDS:
        settings.set(table_fieldname, [])
        for row in old.get(table_fieldname) or []:
            settings.append(table_fieldname, {
                "authority": row.authority,
                "programme": row.programme,
                "assigned": row.assigned,
                "approved": row.approved,
                "rejected": row.rejected,
            })

    settings.flags.ignore_validate = True
    settings.flags.ignore_mandatory = True
    settings.save(ignore_permissions=True)

    _drop_old_doctype()

    frappe.db.commit()


def _drop_old_doctype():
    frappe.delete_doc(
        "DocType",
        "Attendance Condonation Configuration",
        ignore_missing=True,
        force=True,
    )
    frappe.logger().info(
        "[slcm] Merged Attendance Condonation Configuration into Attendance Settings and removed the old doctype."
    )
