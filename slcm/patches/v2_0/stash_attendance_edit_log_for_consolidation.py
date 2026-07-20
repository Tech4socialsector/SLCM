# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
Attendance Edit Log used to create one parent document per edited field,
so the same Student Attendance record ended up with many rows in the list
view. It now holds one parent per attendance_record with an edit_entries
child table (Attendance Edit Entry) carrying the per-edit history.

This runs pre_model_sync, while the old flat columns (field_changed,
old_value, new_value, edit_reason, edited_by, edit_timestamp) still exist
on `tabAttendance Edit Log`, and stashes them into a temp table.

It also deletes duplicate parent rows per attendance_record here (keeping
only the earliest), because sync_all() applies the new `unique` constraint
on attendance_record in the very same schema-sync pass that creates the
new child table - if duplicates are still in `tabAttendance Edit Log` when
that ALTER TABLE ... ADD UNIQUE runs, migration fails outright. The new
Attendance Edit Entry child table doesn't exist yet at this point, so the
actual child-row insertion happens later in
consolidate_attendance_edit_log_from_stash (post_model_sync); this patch
only needs to make `tabAttendance Edit Log` itself unique-safe.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Attendance Edit Log"):
        return
    if not frappe.db.has_column("Attendance Edit Log", "field_changed"):
        # Old flat schema already gone (fresh site or patch re-run) - nothing to stash.
        return

    frappe.db.sql_ddl("DROP TABLE IF EXISTS `__attendance_edit_log_stash`")
    frappe.db.sql(
        """
        CREATE TABLE `__attendance_edit_log_stash` AS
        SELECT name, attendance_record, field_changed, old_value, new_value,
               edit_reason, edited_by, edit_timestamp, creation
        FROM `tabAttendance Edit Log`
        """
    )

    # Keep only the earliest Attendance Edit Log row per attendance_record,
    # so the upcoming schema sync can safely add the unique constraint.
    duplicates = frappe.db.sql(
        """
        SELECT name
        FROM `tabAttendance Edit Log` t
        WHERE t.name NOT IN (
            SELECT keep_name FROM (
                SELECT MIN(name) AS keep_name
                FROM `tabAttendance Edit Log`
                GROUP BY attendance_record
            ) AS keepers
        )
        """,
        as_dict=True,
    )
    for row in duplicates:
        frappe.db.sql("DELETE FROM `tabAttendance Edit Log` WHERE name = %s", row.name)

    frappe.db.commit()
