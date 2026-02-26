import frappe
from frappe.model.document import Document
from frappe.utils import now, get_datetime


class PortalAnnouncement(Document):

    def before_save(self):
        # Record who created and what role
        if not self.created_by_role:
            roles = frappe.get_roles(frappe.session.user)
            if "Admission Admin" in roles:
                self.created_by_role = "Admission Admin"
            elif "System Manager" in roles:
                self.created_by_role = "System Manager"
            else:
                self.created_by_role = "Staff"

    def validate(self):
        if self.expiry_date and self.publish_date:
            if get_datetime(self.expiry_date) <= get_datetime(self.publish_date):
                frappe.throw("Expiry Date must be after Publish Date.")
        if self.target_audience == "By Program" and not self.target_program:
            frappe.throw("Please select a Target Program.")
        if self.target_audience == "By Cycle" and not self.target_cycle:
            frappe.throw("Please select a Target Cycle.")
        if self.target_audience == "By Campus" and not self.target_campus:
            frappe.throw("Please select a Target Campus.")

    def on_update(self):
        frappe.cache().delete_key("portal_announcements")
