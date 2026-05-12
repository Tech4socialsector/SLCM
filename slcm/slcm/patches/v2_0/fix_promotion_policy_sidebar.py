"""
Ensure the 'Promotions' Workspace, Workspace Sidebar, and Desktop Icon
are consistent in the database.

Safe to re-run:
  - Deletes any stale 'Promotion Management' / 'Promotion Policy' records
    and re-imports the canonical 'Promotions' workspace from the JSON file.
  - Upserts the Workspace Sidebar and Desktop Icon so a fresh install also
    gets the correct navigation entries (not just renames of old records).
"""

import frappe


def execute():
    import os

    json_path = os.path.join(
        os.path.dirname(frappe.get_app_path("slcm")),
        "slcm", "slcm", "workspace", "promotion_policy", "promotion_policy.json",
    )

    # ── 1. Clean up any old workspace names and re-import ─────────────────────
    for old_name in ("Promotion Management", "Promotion Policy", "Promotions"):
        if frappe.db.exists("Workspace", old_name):
            frappe.delete_doc("Workspace", old_name, ignore_permissions=True, force=True)
    frappe.db.commit()

    frappe.modules.import_file.import_file_by_path(json_path, force=True, reset_permissions=True)
    frappe.db.commit()

    # ── 2. Rename any legacy Workspace Sidebar records → 'Promotions' ─────────
    for old in ("Promotion Management", "Promotion Policy"):
        if frappe.db.exists("Workspace Sidebar", old):
            frappe.db.sql(
                "UPDATE `tabWorkspace Sidebar Item` SET parent='Promotions' WHERE parent=%s",
                old,
            )
            frappe.db.sql(
                "UPDATE `tabWorkspace Sidebar` SET name='Promotions' WHERE name=%s",
                old,
            )
    frappe.db.commit()

    # ── 3. Upsert Workspace Sidebar 'Promotions' ──────────────────────────────
    now = frappe.utils.now_datetime()

    if not frappe.db.exists("Workspace Sidebar", "Promotions"):
        frappe.db.sql("""
            INSERT INTO `tabWorkspace Sidebar`
                (name, creation, modified, modified_by, owner,
                 docstatus, title, module, standard)
            VALUES
                ('Promotions', %s, %s, 'Administrator', 'Administrator',
                 0, 'Promotions', 'SLCM', 0)
        """, (now, now))
        frappe.db.commit()

    # Replace sidebar items completely so they stay canonical on every migrate
    frappe.db.sql("DELETE FROM `tabWorkspace Sidebar Item` WHERE parent='Promotions'")

    sidebar_items = [
        # (label, link_type, link_to, type, idx)
        ("Promotions",            "Workspace", "Promotions",            "Link", 1),
        ("Promotion Management",  "Page",      "promotion-management",  "Link", 2),
        ("New Promotion Policy",  "DocType",   "Promotion Policy",      "Link", 3),
        ("Promotion Policy List", "DocType",   "Promotion Policy",      "Link", 4),
        ("Student Promotion",     "DocType",   "Student Promotion",     "Link", 5),
    ]
    for label, link_type, link_to, itype, idx in sidebar_items:
        item_name = frappe.generate_hash(length=10)
        frappe.db.sql("""
            INSERT INTO `tabWorkspace Sidebar Item`
                (name, creation, modified, modified_by, owner, docstatus,
                 idx, label, link_type, link_to, type, parent, parentfield, parenttype)
            VALUES
                (%s, %s, %s, 'Administrator', 'Administrator', 0,
                 %s, %s, %s, %s, %s, 'Promotions', 'items', 'Workspace Sidebar')
        """, (item_name, now, now, idx, label, link_type, link_to, itype))
    frappe.db.commit()

    # ── 4. Rename any legacy Desktop Icon records → 'Promotions' ─────────────
    for old in ("Promotion Management", "Promotion Policy"):
        if frappe.db.exists("Desktop Icon", old):
            frappe.db.sql(
                "UPDATE `tabDesktop Icon` SET name='Promotions', label='Promotions' WHERE name=%s",
                old,
            )
    frappe.db.commit()

    # ── 5. Upsert Desktop Icon 'Promotions' ───────────────────────────────────
    # Use INSERT ... ON DUPLICATE KEY UPDATE so it works regardless of prior state
    frappe.db.sql("""
        INSERT INTO `tabDesktop Icon`
            (name, creation, modified, modified_by, owner, docstatus,
             label, link_type, link_to, standard)
        VALUES
            ('Promotions', %s, %s, 'Administrator', 'Administrator', 0,
             'Promotions', 'Workspace Sidebar', 'Promotions', 0)
        ON DUPLICATE KEY UPDATE
            label     = 'Promotions',
            link_type = 'Workspace Sidebar',
            link_to   = 'Promotions',
            modified  = %s
    """, (now, now, now))
    frappe.db.commit()

    # ── 6. Clear cache ─────────────────────────────────────────────────────────
    frappe.clear_cache()
