import frappe


def execute():
    """
    Update Parent Portal Settings to use NLSIU sidebar colours:
    #2b2e4a (dark navy) background with #e8e9f0 (near-white) text.
    Only updates if the values are still at the old white default.
    """
    if not frappe.db.exists("Parent Portal Settings", "Parent Portal Settings"):
        return

    doc = frappe.get_single("Parent Portal Settings")

    changed = False

    if (doc.sidebar_bg_color or "#ffffff").strip().lower() in ("#ffffff", "#fff", ""):
        doc.sidebar_bg_color = "#2b2e4a"
        changed = True

    if (doc.sidebar_text_color or "#374151").strip().lower() in ("#374151", ""):
        doc.sidebar_text_color = "#e8e9f0"
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
