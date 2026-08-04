# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
City.city_name is being made unique, but existing sites have duplicate
city_name values (records created before this constraint existed).
sync_all() applies the new `unique` index on city_name in the same
schema-sync pass this patch precedes, so duplicates left in `tabCity`
at that point make the ALTER TABLE ... ADD UNIQUE fail outright.

Merges each duplicate into the earliest-created City with that
city_name via frappe.rename_doc(merge=True), which repoints every
Link/Dynamic Link field across the app (Applicant, Campus, Student
Master, Pace Application, etc.) before deleting the duplicate.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "City"):
        return

    duplicates = frappe.db.sql(
        """
        SELECT city_name
        FROM `tabCity`
        GROUP BY city_name
        HAVING COUNT(*) > 1
        """,
        as_dict=True,
    )

    for row in duplicates:
        names = frappe.get_all(
            "City",
            filters={"city_name": row.city_name},
            order_by="creation asc",
            pluck="name",
        )
        keeper = names[0]
        for duplicate in names[1:]:
            frappe.rename_doc("City", duplicate, keeper, merge=True, force=True, show_alert=False)

    frappe.db.commit()
