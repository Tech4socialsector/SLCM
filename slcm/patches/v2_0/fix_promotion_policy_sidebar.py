"""
Fix: import Promotion Policy workspace, then align Workspace Sidebar
and Desktop Icon so the desktop icon routes correctly.
"""

import frappe


def execute():
    # ── 1. Import workspace from JSON file ────────────────────────────────────
    import os, json
    json_path = os.path.join(
        os.path.dirname(frappe.get_app_path("slcm")),
        "slcm", "slcm", "workspace", "promotion_policy", "promotion_policy.json",
    )

    for old_name in ("Promotion Management", "Promotion Policy"):
        if frappe.db.exists("Workspace", old_name):
            frappe.delete_doc("Workspace", old_name, ignore_permissions=True, force=True)
    frappe.db.commit()

    frappe.modules.import_file.import_file_by_path(json_path, force=True, reset_permissions=True)
    frappe.db.commit()

    # ── 2. Fix Workspace Sidebar via direct SQL (avoids Dynamic Link validation) ─
    if frappe.db.exists("Workspace Sidebar", "Promotion Management"):
        frappe.db.sql("""
            UPDATE `tabWorkspace Sidebar Item`
            SET link_to = 'Promotion Policy', label = 'Promotion Policy'
            WHERE parent = 'Promotion Management' AND link_to = 'Promotion Management'
        """)
        frappe.db.sql("""
            UPDATE `tabWorkspace Sidebar`
            SET name = 'Promotion Policy'
            WHERE name = 'Promotion Management'
        """)
        frappe.db.sql("""
            UPDATE `tabWorkspace Sidebar Item`
            SET parent = 'Promotion Policy'
            WHERE parent = 'Promotion Management'
        """)
        frappe.db.commit()

    # ── 3. Fix Desktop Icon label via direct SQL ─────────────────────────────
    if frappe.db.exists("Desktop Icon", "Promotion Management"):
        frappe.db.sql("""
            UPDATE `tabDesktop Icon`
            SET label = 'Promotion Policy', name = 'Promotion Policy'
            WHERE name = 'Promotion Management'
        """)
        frappe.db.commit()

    # ── 4. Clear cache ───────────────────────────────────────────────────────
    frappe.clear_cache()
