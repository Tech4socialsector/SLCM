# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

"""
Migration patch: rename 'Course Result Access' → 'Access Result Settings'

Updates every place in the Frappe database that still holds the old doctype
name so that after running `bench migrate` the UI is fully consistent with
the renamed doctype.

Covers:
  1. Workspace Sidebar   – link_to / label columns
  2. Workspace Links     – link_to / label columns inside workspace definitions
  3. Workspace content   – shortcut_name inside the JSON content blob
  4. Property Setter     – doc_type column (moves old overrides to new doctype)
  5. Custom Field        – dt column
"""

import json
import frappe


OLD_NAME = "Course Result Access"
NEW_NAME = "Access Result Settings"


def execute():
    _update_workspace_sidebar()
    _update_workspace_links()
    _update_workspace_content()
    _update_property_setters()
    _update_custom_fields()
    frappe.db.commit()


# ── 1. Workspace Sidebar ──────────────────────────────────────────────────────

def _update_workspace_sidebar():
    # Items live in the child table "Workspace Sidebar Item", not on the parent.
    if not frappe.db.table_exists("Workspace Sidebar Item"):
        return
    rows = frappe.db.get_all(
        "Workspace Sidebar Item",
        filters={"link_to": OLD_NAME, "link_type": "DocType"},
        fields=["name", "label"],
    )
    for row in rows:
        updates = {"link_to": NEW_NAME}
        # Only rename the label when it literally matches the old doctype name;
        # custom labels ("Result Access Settings", "Access Results", …) are kept.
        if row.get("label") == OLD_NAME:
            updates["label"] = NEW_NAME
        frappe.db.set_value("Workspace Sidebar Item", row["name"], updates)


# ── 2. Workspace Links table ──────────────────────────────────────────────────

def _update_workspace_links():
    """Update rows in the child-table 'Workspace Link' embedded in Workspace docs."""
    if not frappe.db.table_exists("Workspace Link"):
        return

    rows = frappe.db.get_all(
        "Workspace Link",
        filters={"link_to": OLD_NAME, "link_type": "DocType"},
        fields=["name", "label"],
    )
    for row in rows:
        updates = {"link_to": NEW_NAME}
        if row.get("label") == OLD_NAME:
            updates["label"] = NEW_NAME
        frappe.db.set_value("Workspace Link", row["name"], updates)


# ── 3. Workspace content (JSON blob with shortcuts) ───────────────────────────

def _update_workspace_content():
    """Rewrite shortcut_name inside the serialised content JSON of each Workspace."""
    workspaces = frappe.db.get_all(
        "Workspace",
        fields=["name", "content"],
    )
    for ws in workspaces:
        raw = ws.get("content") or ""
        if OLD_NAME not in raw:
            continue
        try:
            content = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        changed = False
        for item in content:
            if not isinstance(item, dict):
                continue
            data = item.get("data", {})
            if isinstance(data, dict) and data.get("shortcut_name") == OLD_NAME:
                data["shortcut_name"] = NEW_NAME
                changed = True

        if changed:
            frappe.db.set_value(
                "Workspace", ws["name"],
                "content", json.dumps(content),
                update_modified=False,
            )


# ── 4. Property Setter ────────────────────────────────────────────────────────

def _update_property_setters():
    """Move property-setter overrides from old doctype name to new doctype name."""
    rows = frappe.db.get_all(
        "Property Setter",
        filters={"doc_type": OLD_NAME},
        fields=["name"],
    )
    for row in rows:
        new_ps_name = row["name"].replace(OLD_NAME, NEW_NAME)
        # If a record for the new name already exists, delete the old duplicate.
        if frappe.db.exists("Property Setter", new_ps_name):
            frappe.db.delete("Property Setter", row["name"])
        else:
            frappe.db.set_value(
                "Property Setter", row["name"],
                {"doc_type": NEW_NAME, "name": new_ps_name},
            )


# ── 5. Custom Field ───────────────────────────────────────────────────────────

def _update_custom_fields():
    """Move any custom fields that were added to the old doctype."""
    rows = frappe.db.get_all(
        "Custom Field",
        filters={"dt": OLD_NAME},
        fields=["name"],
    )
    for row in rows:
        frappe.db.set_value("Custom Field", row["name"], "dt", NEW_NAME)
