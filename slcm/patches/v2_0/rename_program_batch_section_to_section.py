# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

"""
Migration patch: rename DocType 'Program Batch Section' -> 'Section'.

Runs pre_model_sync (before the new "section" doctype JSON is synced) so
that the existing "Program Batch Section" table/records are renamed in
place via Frappe's standard rename_doc("DocType", ...) machinery instead of
leaving the old table orphaned and the new "Section" doctype created empty.

frappe.rename_doc("DocType", ...) already takes care of, among other things:
  - renaming the `tabProgram Batch Section` table to `tabSection`
  - updating every Link field's `options` (DocField / Custom Field) that
    pointed at "Program Batch Section" to "Section"
  - updating Dynamic Link values (e.g. Workspace Link/Shortcut `link_to`)
    that referenced the "Program Batch Section" DocType

This patch additionally covers the two things rename_doc does not touch:
Property Setter and Custom Field records that belong directly to the old
doctype (`doc_type`/`dt` == "Program Batch Section"), matching the pattern
used in rename_program_to_programme.py.

Note: the new "Section" doctype drops the "department", "program" and
"academic_year" fields that "Program Batch Section" had, since all three
are already derivable from its "batch" field (Batch -> Programme ->
Department / Academic Year). Those columns are simply left behind as
orphaned columns on the renamed table; Frappe's schema sync does not drop
columns automatically, so no data is lost, they are just no longer surfaced
on the doctype.
"""

import frappe
from frappe.model.rename_doc import rename_doc

OLD_NAME = "Program Batch Section"
NEW_NAME = "Section"


def execute():
    if not frappe.db.exists("DocType", OLD_NAME):
        return

    if frappe.db.exists("DocType", NEW_NAME):
        # Already renamed (or a fresh install that only ever had "Section").
        return

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
