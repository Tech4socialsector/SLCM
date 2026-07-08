# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

"""
Migration patch: rename DocType 'Cohort' -> 'Batch'.

Runs pre_model_sync (before the new "batch" doctype JSON is synced) so that
the existing "Cohort" table/records are renamed in place via Frappe's
standard rename_doc("DocType", ...) machinery instead of leaving the old
table orphaned and the new "Batch" doctype created empty.

frappe.rename_doc("DocType", ...) already takes care of, among other things:
  - renaming the `tabCohort` table to `tabBatch`
  - updating every Link field's `options` (DocField / Custom Field) that
    pointed at "Cohort" to "Batch"
  - updating Dynamic Link values (e.g. Workspace Link/Shortcut `link_to`)
    that referenced the "Cohort" DocType
  - renaming Number Card / Dashboard Chart `document_type` values referencing it

This patch additionally covers the two things rename_doc does not touch:
Property Setter and Custom Field records that belong directly to the old
doctype (`doc_type`/`dt` == "Cohort"), matching the pattern used in
rename_program_to_programme.py.

Note: as part of this same rename, the Cohort doctype's own free-text field
"batch" (label "Batch") was renamed to "section" in source (to avoid a
same-named field on the new "Batch" doctype). Frappe's doctype-sync step
does not detect that as a rename - left alone it would add a new, empty
"section" column and leave the old "batch" column (with data) orphaned.
This patch renames the DB column directly, before the doctype-sync step
runs, so existing data is preserved under the new field name.
"""

import frappe
from frappe.model.rename_doc import rename_doc

OLD_NAME = "Cohort"
NEW_NAME = "Batch"


def execute():
    if not frappe.db.exists("DocType", OLD_NAME):
        return

    if frappe.db.exists("DocType", NEW_NAME):
        # Already renamed (or a fresh install that only ever had "Batch").
        return

    _rename_batch_field_to_section()

    rename_doc(
        "DocType",
        OLD_NAME,
        NEW_NAME,
        force=True,
        ignore_permissions=True,
        show_alert=False,
    )

    _migrate_property_setters()
    _migrate_custom_fields()

    frappe.db.commit()


def _rename_batch_field_to_section():
    """Preserve data in Cohort's own "batch" column ahead of the doctype rename."""
    if frappe.db.has_column(OLD_NAME, "batch") and not frappe.db.has_column(OLD_NAME, "section"):
        frappe.db.rename_column(OLD_NAME, "batch", "section")


def _migrate_property_setters():
    rows = frappe.db.get_all("Property Setter", filters={"doc_type": OLD_NAME}, fields=["name"])
    for row in rows:
        new_ps_name = row["name"].replace(OLD_NAME, NEW_NAME)
        if frappe.db.exists("Property Setter", new_ps_name):
            frappe.db.delete("Property Setter", row["name"])
        else:
            frappe.db.set_value(
                "Property Setter", row["name"],
                {"doc_type": NEW_NAME, "name": new_ps_name},
            )


def _migrate_custom_fields():
    rows = frappe.db.get_all("Custom Field", filters={"dt": OLD_NAME}, fields=["name"])
    for row in rows:
        frappe.db.set_value("Custom Field", row["name"], "dt", NEW_NAME)
