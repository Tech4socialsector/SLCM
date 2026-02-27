import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime


class PortalAnnouncement(Document):

    def validate(self):
        self._validate_dates()
        self._validate_status_transition()

    def before_save(self):
        if self.status == "Published" and not self.get("published_on"):
            self.published_on = now_datetime()

    def _validate_dates(self):
        now = now_datetime()

        if self.publish_date and self.expiry_date:
            if get_datetime(self.expiry_date) <= get_datetime(self.publish_date):
                frappe.throw(
                    "Expiry Date must be after Publish Date.",
                    title="Invalid Date Range"
                )

        if self.status == "Scheduled":
            if not self.publish_date:
                frappe.throw(
                    "Publish Date is required when status is Scheduled.",
                    title="Publish Date Required"
                )
            if not self.expiry_date:
                frappe.throw(
                    "Expiry Date is required when status is Scheduled.",
                    title="Expiry Date Required"
                )
            if get_datetime(self.publish_date) <= now:
                frappe.throw(
                    "Publish Date must be in the future for a Scheduled "
                    "announcement. If you want to publish immediately, "
                    "set status to Published.",
                    title="Publish Date Must Be Future"
                )

        if self.status == "Published":
            if self.publish_date and get_datetime(self.publish_date) > now:
                frappe.throw(
                    "Publish Date is in the future. "
                    "Use status 'Scheduled' to auto-publish at that time.",
                    title="Use Scheduled Status"
                )

        if self.status == "Archived":
            if self.expiry_date and get_datetime(self.expiry_date) > now:
                frappe.throw(
                    "Cannot archive this announcement because its "
                    "Expiry Date has not passed yet.",
                    title="Cannot Archive Yet"
                )

    def _validate_status_transition(self):
        if self.is_new():
            return
        old_status = frappe.db.get_value(
            "Portal Announcement", self.name, "status"
        )
        if not old_status:
            return
        valid_transitions = {
            "Draft":     ["Draft", "Scheduled", "Published"],
            "Scheduled": ["Scheduled", "Published", "Draft"],
            "Published": ["Published", "Archived"],
            "Archived":  ["Archived"]
        }
        allowed = valid_transitions.get(old_status, [])
        if self.status not in allowed:
            frappe.throw(
                f"Cannot change status from '{old_status}' "
                f"to '{self.status}'.",
                title="Invalid Status Transition"
            )
