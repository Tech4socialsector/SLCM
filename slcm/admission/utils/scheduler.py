import frappe

def auto_manage_announcements():
    """
    Runs every 15 minutes via scheduler.
    1. Auto-publishes Scheduled announcements when publish_date <= now
    2. Auto-archives Published announcements when expiry_date <= now
    Never touches Draft announcements.
    """
    from frappe.utils import now_datetime
    now = now_datetime()

    # --- Auto-publish Scheduled announcements ---
    to_publish = frappe.get_all(
        "Portal Announcement",
        filters={
            "status": "Scheduled",
            "publish_date": ["<=", now]
        },
        fields=["name", "title"]
    )
    for ann in to_publish:
        try:
            frappe.db.set_value(
                "Portal Announcement", ann.name,
                {
                    "status": "Published",
                    "published_on": now
                }
            )
        except Exception as e:
            frappe.log_error(
                f"Auto-publish failed for {ann.name}: {e}",
                "Announcement Scheduler"
            )

    # --- Auto-archive Published announcements ---
    to_archive = frappe.get_all(
        "Portal Announcement",
        filters={
            "status": "Published",
            "expiry_date": ["not in", ["", None]],
            "expiry_date": ["<=", now]
        },
        fields=["name", "title"]
    )
    for ann in to_archive:
        try:
            frappe.db.set_value(
                "Portal Announcement", ann.name,
                {"status": "Archived"}
            )
        except Exception as e:
            frappe.log_error(
                f"Auto-archive failed for {ann.name}: {e}",
                "Announcement Scheduler"
            )

    if to_publish or to_archive:
        frappe.db.commit()
