import frappe
from frappe.model.document import Document

class ApplicantPaymentReceipt(Document):
    def validate(self):
        self.set_notification_receiver()

    def set_notification_receiver(self):
        if self.applicant:
            applicant_email = frappe.db.get_value("Applicant", self.applicant, "email")
            if applicant_email:
                user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
                if user_name:
                    self.notification_receiver = user_name
