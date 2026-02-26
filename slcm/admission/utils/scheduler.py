import frappe
from frappe.utils import now, get_datetime


def auto_publish_announcements():
    """
    Runs every 15 minutes via scheduler.
    - Publishes announcements whose publish_date has passed and status is Draft.
    - Archives announcements whose expiry_date has passed and status is Published.
    """
    current_time = get_datetime(now())

    # Auto-publish: Draft → Published
    to_publish = frappe.get_all(
        "Portal Announcement",
        filters={
            "status": "Draft",
            "show_on_portal": 1,
            "publish_date": ["<=", current_time]
        },
        fields=["name", "title"]
    )
    for ann in to_publish:
        try:
            frappe.db.set_value("Portal Announcement", ann.name, "status", "Published")
            frappe.logger().info(f"Auto-published announcement: {ann.title}")
        except Exception as e:
            frappe.log_error(f"Failed to publish {ann.name}: {e}", "Announcement Scheduler")

    # Auto-archive: Published → Archived
    to_archive = frappe.get_all(
        "Portal Announcement",
        filters={
            "status": "Published",
            "expiry_date": ["<=", current_time],
            "expiry_date": ["!=", ""]
        },
        fields=["name", "title"]
    )
    for ann in to_archive:
        try:
            frappe.db.set_value(
                "Portal Announcement", ann.name,
                {"status": "Archived", "show_on_portal": 0}
            )
            frappe.logger().info(f"Auto-archived announcement: {ann.title}")
        except Exception as e:
            frappe.log_error(f"Failed to archive {ann.name}: {e}", "Announcement Scheduler")

    # Clear cache after updates
    if to_publish or to_archive:
        frappe.cache().delete_key("portal_announcements")
        frappe.db.commit()
