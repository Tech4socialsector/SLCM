"""
Migrates Student Enrollment field data after rename:
  data_xgxm   → batch_year_ref  (Frappe sync already created new column)
  table_hxbo  → enrolled_courses (child table ref, no DB column)

Since bench migrate syncs the DocType JSON first, batch_year_ref already
exists by the time this patch runs. We just copy data across and drop the
old column.
"""
import frappe


def execute():
    has_old = frappe.db.has_column("Student Enrollment", "data_xgxm")
    has_new = frappe.db.has_column("Student Enrollment", "batch_year_ref")

    if has_old and has_new:
        # Copy any existing data from old column into new one
        frappe.db.sql("""
            UPDATE `tabStudent Enrollment`
            SET `batch_year_ref` = `data_xgxm`
            WHERE (`batch_year_ref` IS NULL OR `batch_year_ref` = '')
              AND `data_xgxm` IS NOT NULL
              AND `data_xgxm` != ''
        """)
        # Drop the now-redundant old column
        frappe.db.sql("ALTER TABLE `tabStudent Enrollment` DROP COLUMN `data_xgxm`")
        frappe.db.commit()

    elif has_old and not has_new:
        # Old column exists but new one hasn't been created yet (edge case)
        frappe.db.sql(
            "ALTER TABLE `tabStudent Enrollment` "
            "CHANGE `data_xgxm` `batch_year_ref` VARCHAR(140)"
        )
        frappe.db.commit()

    # has_new only, or neither: already clean, nothing to do
