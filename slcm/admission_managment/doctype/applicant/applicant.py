import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address, getdate, date_diff, today, now
from slcm.admission_managment.utils.regulatory import log_audit_trail

class Applicant(Document):

    def validate(self):
        self.validate_email()
        self.validate_age()
        self.validate_percentages()
        self.validate_reservation_documents()
        self.validate_preferences()
        self.validate_declaration()

    def validate_email(self):
        if not validate_email_address(self.email):
            frappe.throw(
                f"Invalid email address: {self.email}",
                title="Invalid Email"
            )

    def validate_age(self):
        if self.date_of_birth:
            age = date_diff(today(), self.date_of_birth) / 365
            if age < 17:
                frappe.throw(
                    "Applicant must be at least 17 years old.",
                    title="Age Restriction"
                )

    def validate_percentages(self):
        if self.class_x_percentage:
            if not 0 <= self.class_x_percentage <= 100:
                frappe.throw(
                    "Class X Percentage must be between 0 and 100.",
                    title="Invalid Percentage"
                )
        if self.class_xii_percentage:
            if not 0 <= self.class_xii_percentage <= 100:
                frappe.throw(
                    "Class XII Percentage must be between 0 and 100.",
                    title="Invalid Percentage"
                )

    def validate_reservation_documents(self):
        if self.reservation_category == "EWS" and not self.ews_certificate:
            frappe.throw(
                "EWS Certificate is mandatory for EWS category.",
                title="Missing Document"
            )
        if self.reservation_category in ["SC", "ST", "OBC"] and not self.caste_certificate:
            frappe.throw(
                f"Caste Certificate is mandatory for {self.reservation_category} category.",
                title="Missing Document"
            )
        if self.reservation_category == "PwD" and not self.pwd_certificate:
            frappe.throw(
                "PwD Certificate is mandatory for PwD category.",
                title="Missing Document"
            )

    def validate_preferences(self):
        if not self.first_preference:
            frappe.throw(
                "First Campus Preference is mandatory.",
                title="Missing Preference"
            )
        preferences = [
            self.first_preference,
            self.second_preference,
            self.third_preference
        ]
        filled = [p for p in preferences if p]
        if len(filled) != len(set(filled)):
            frappe.throw(
                "Duplicate campus preferences are not allowed.",
                title="Duplicate Preference"
            )

    def validate_declaration(self):
        if self.docstatus == 1 and not self.declaration_undertaking:
            frappe.throw(
                "Declaration Undertaking must be accepted before submission.",
                title="Declaration Required"
            )

    def before_save(self):
        if not self.application_id:
            self.application_id = frappe.generate_hash(length=8).upper()

    def on_submit(self):
        self.db_set("application_status", "Submitted")
        self.db_set("submitted_on", now())
        log_audit_trail(
            self.doctype, self.name,
            "Submitted", "application_status",
            "Draft", "Submitted", "General"
        )
        frappe.sendmail(
            recipients=[self.email],
            subject=f"NLSIU Application Submitted - {self.application_id}",
            message=f"""
            Dear {self.candidate_name},<br><br>
            Your application <b>{self.application_id}</b> has been
            successfully submitted.<br>
            Application Type: {self.application_type}<br>
            Program: {self.program}<br><br>
            You will be notified of further updates.<br><br>
            NLSIU Admissions Team
            """
        )

    def on_cancel(self):
        self.db_set("application_status", "Draft")
        log_audit_trail(
            self.doctype, self.name,
            "Cancelled", "application_status",
            "Submitted", "Draft", "General"
        )
