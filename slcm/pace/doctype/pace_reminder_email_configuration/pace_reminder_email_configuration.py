import frappe
from frappe.model.document import Document

class PACEReminderEmailConfiguration(Document):
    pass

def is_reminder_enabled(reminder_fieldname):
    """
    Checks if a specific reminder is enabled in the configuration.
    reminder_fieldname: str (e.g., 'enable_application_reminder')
    Returns: bool
    """
    config = frappe.get_single("PACE Reminder Email Configuration")
    return config.get(reminder_fieldname) == "Active"
