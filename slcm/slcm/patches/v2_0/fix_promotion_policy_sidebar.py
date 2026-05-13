"""
Fix: import Promotions workspace, then align Workspace Sidebar
and Desktop Icon so the desktop icon routes correctly.

Renames workspace from "Promotion Policy" (slug conflicts with DocType)
to "Promotions" so shortcuts to the Promotion Policy doctype work.
"""

import frappe


def execute():
    # ── 1. Import workspace from JSON file ────────────────────────────────────
    import os, json
    json_path = os.path.join(
        os.path.dirname(frappe.get_app_path("slcm")),
        "slcm", "slcm", "workspace", "promotion_policy", "promotion_policy.json",
    )

    for old_name in ("Promotion Management", "Promotion Policy", "Promotions"):
        if frappe.db.exists("Workspace", old_name):
            frappe.delete_doc("Workspace", old_name, ignore_permissions=True, force=True)
    frappe.db.commit()

    frappe.modules.import_file.import_file_by_path(json_path, force=True, reset_permissions=True)
    frappe.db.commit()

    # ── 2. Fix Workspace Sidebar via direct SQL (avoids Dynamic Link validation) ─
    for old_sidebar in ("Promotion Management", "Promotion Policy"):
        if frappe.db.exists("Workspace Sidebar", old_sidebar):
            frappe.db.sql("""
                UPDATE `tabWorkspace Sidebar Item`
                SET link_to = 'Promotions', label = 'Promotions'
                WHERE parent = %(old)s AND link_to = %(old)s
            """, {"old": old_sidebar})
            frappe.db.sql("""
                UPDATE `tabWorkspace Sidebar Item`
                SET parent = 'Promotions'
                WHERE parent = %(old)s
            """, {"old": old_sidebar})
            frappe.db.sql("""
                UPDATE `tabWorkspace Sidebar`
                SET name = 'Promotions'
                WHERE name = %(old)s
            """, {"old": old_sidebar})
            frappe.db.commit()

    # ── 3. Fix Desktop Icon label via direct SQL ─────────────────────────────
    for old_icon in ("Promotion Management", "Promotion Policy"):
        if frappe.db.exists("Desktop Icon", old_icon):
            frappe.db.sql("""
                UPDATE `tabDesktop Icon`
                SET label = 'Promotions', name = 'Promotions'
                WHERE name = %(old)s
            """, {"old": old_icon})
            frappe.db.commit()

    # ── 4. Clear cache ───────────────────────────────────────────────────────
    frappe.clear_cache()
