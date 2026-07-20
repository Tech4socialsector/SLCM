# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
Second half of the Attendance Edit Log consolidation - see
stash_attendance_edit_log_for_consolidation (pre_model_sync) for context.

Runs post_model_sync, once `tabAttendance Edit Entry` exists and the old
flat columns are gone from `tabAttendance Edit Log`. Reads the pre-sync
stash, collapses all rows per attendance_record into a single parent with
one Attendance Edit Entry child row per historical edit, then drops the
stash table.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "Attendance Edit Log"):
        return
    if not frappe.db.exists("DocType", "Attendance Edit Entry"):
        return
    if "__attendance_edit_log_stash" not in frappe.db.get_tables(cached=False):
        return

    rows = frappe.db.sql(
        """
        SELECT name, attendance_record, field_changed, old_value, new_value,
               edit_reason, edited_by, edit_timestamp, creation
        FROM `__attendance_edit_log_stash`
        ORDER BY attendance_record, edit_timestamp ASC, creation ASC
        """,
        as_dict=True,
    )

    # The pre_model_sync patch already deleted duplicate parent rows, keeping
    # MIN(name) per attendance_record so the unique constraint could be added.
    # That surviving name is the parent every child entry must attach to here.
    survivor_by_attendance_record = dict(
        frappe.db.sql("SELECT attendance_record, name FROM `tabAttendance Edit Log`")
    )

    if rows:
        by_attendance_record = {}
        for row in rows:
            by_attendance_record.setdefault(row.attendance_record, []).append(row)

        # Attendance Edit Entry autonames via Frappe's "autoincrement" naming,
        # which is application-level (max(name) + 1), not a DB AUTO_INCREMENT
        # column - so `name` must be supplied explicitly on raw-SQL inserts.
        next_name = (frappe.db.sql(
            "SELECT COALESCE(MAX(name), 0) + 1 FROM `tabAttendance Edit Entry`"
        ) or [[1]])[0][0]

        for attendance_record, entries in by_attendance_record.items():
            parent_name = survivor_by_attendance_record.get(attendance_record)
            if not parent_name:
                continue

            for i, entry in enumerate(entries):
                frappe.db.sql(
                    """
                    INSERT INTO `tabAttendance Edit Entry`
                        (name, parent, parenttype, parentfield, idx, docstatus,
                         owner, creation, modified, modified_by,
                         field_changed, old_value, new_value, edit_reason, edited_by, edit_timestamp)
                    VALUES (%(name)s, %(parent)s, 'Attendance Edit Log', 'edit_entries', %(idx)s, 0,
                            %(owner)s, %(creation)s, %(creation)s, %(owner)s,
                            %(field_changed)s, %(old_value)s, %(new_value)s, %(edit_reason)s,
                            %(edited_by)s, %(edit_timestamp)s)
                    """,
                    {
                        "name": next_name,
                        "parent": parent_name,
                        "idx": i + 1,
                        "owner": entry.edited_by or "Administrator",
                        "creation": entry.creation,
                        "field_changed": entry.field_changed,
                        "old_value": entry.old_value,
                        "new_value": entry.new_value,
                        "edit_reason": entry.edit_reason,
                        "edited_by": entry.edited_by,
                        "edit_timestamp": entry.edit_timestamp,
                    },
                )
                next_name += 1

    frappe.db.commit()
    frappe.db.sql_ddl("DROP TABLE IF EXISTS `__attendance_edit_log_stash`")
