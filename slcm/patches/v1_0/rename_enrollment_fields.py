"""
Renames Student Enrollment fields:
  table_hxbo  → enrolled_courses  (child table reference, no DB column)
  data_xgxm   → batch_year_ref    (Data field, DB column rename required)
"""
import frappe


def execute():
    # Rename the Data column in the DB table
    if frappe.db.has_column("Student Enrollment", "data_xgxm"):
        frappe.db.sql("ALTER TABLE `tabStudent Enrollment` CHANGE `data_xgxm` `batch_year_ref` VARCHAR(140)")
        frappe.db.commit()

    # Update any raw SQL references in Attendance / Office Hours (office_hours_group.py uses it)
    # No action needed – the Python code already uses the new name after this patch.
