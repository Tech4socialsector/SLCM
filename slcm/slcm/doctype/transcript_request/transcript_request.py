# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


# Razorpay gateway_status → business payment_status
# Matches the GATEWAY_TO_SYSTEM_STATUS convention in slcm/payment.py
RAZORPAY_TO_PAYMENT_STATUS = {
    "created":    "Payment Initiated",   # order created, checkout opened
    "authorized": "Authorized",          # card authorised, capture pending
    "captured":   "Paid",                # money captured — final success
    "failed":     "Payment Failed",      # gateway-side failure
    "refunded":   "Refunded",            # money returned
    "cancelled":  "Payment Cancelled",   # student closed/dismissed checkout
}


class TranscriptRequest(Document):

    def before_insert(self):
        self.requested_on = frappe.utils.today()
        self._apply_fee_settings()

    def on_trash(self):
        # Clear back-references in Student Transcript so Frappe doesn't block deletion
        linked = frappe.get_all(
            "Student Transcript",
            filters={"transcript_request": self.name},
            pluck="name",
        )
        for tr_name in linked:
            frappe.db.set_value("Student Transcript", tr_name, "transcript_request", None)

    def on_update(self):
        """Send notification emails when status changes via the desk (manual edit)."""
        prev_status = self.get_doc_before_save()
        if not prev_status:
            return
        old_status = prev_status.status
        new_status = self.status

        if old_status == new_status:
            if prev_status.payment_status != self.payment_status:
                self._sync_helpdesk_ticket()
            return

        if new_status == "Approved" and not self.approval_email_sent:
            self._notify_on_approval()

        elif new_status == "Rejected" and not self.rejection_email_sent:
            self._notify_on_rejection()

        elif new_status in ("Generated", "Delivered") and not self.transcript_ready_email_sent:
            self._notify_on_ready()

        self._sync_helpdesk_ticket()

    def _sync_helpdesk_ticket(self):
        """
        Mirror status/payment changes onto the linked HD Ticket (set when this
        request was created from a "Transcript Request" Helpdesk ticket), so
        agents can track everything from the Helpdesk queue without opening
        this doctype directly.
        """
        if not self.helpdesk_ticket:
            return
        if not frappe.db.exists("HD Ticket", self.helpdesk_ticket):
            return

        try:
            from helpdesk.api.nls_student import sync_transcript_status_to_ticket
            sync_transcript_status_to_ticket(self)
        except ImportError:
            pass
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Transcript Request → HD Ticket sync failed")

    def _notify_on_approval(self):
        try:
            from slcm.api.transcript_request import _send_template_email
            settings = frappe.get_doc("Transcript Fee Settings", "Transcript Fee Settings")
            ctx = _build_email_ctx(self)
            if _send_template_email(self.student, settings.notify_on_approval, ctx):
                frappe.db.set_value("Transcript Request", self.name, "approval_email_sent", 1)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Transcript approval notification error")

    def _notify_on_rejection(self):
        try:
            from slcm.api.transcript_request import _send_template_email
            settings = frappe.get_doc("Transcript Fee Settings", "Transcript Fee Settings")
            ctx = _build_email_ctx(self)
            if _send_template_email(self.student, settings.notify_on_rejection, ctx):
                frappe.db.set_value("Transcript Request", self.name, "rejection_email_sent", 1)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Transcript rejection notification error")

    def _notify_on_ready(self):
        try:
            from slcm.api.transcript_request import _send_template_email
            settings = frappe.get_doc("Transcript Fee Settings", "Transcript Fee Settings")
            ctx = _build_email_ctx(self, transcript_doc=self.transcript_doc or "")
            if _send_template_email(self.student, settings.notify_on_ready, ctx):
                frappe.db.set_value("Transcript Request", self.name, "transcript_ready_email_sent", 1)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Transcript ready notification error")

    def _apply_fee_settings(self):
        """Look up Transcript Fee Settings and populate payment fields."""
        if not frappe.db.exists("DocType", "Transcript Fee Settings"):
            return
        if not frappe.db.exists("Transcript Fee Settings", "Transcript Fee Settings"):
            return

        settings = frappe.get_doc("Transcript Fee Settings", "Transcript Fee Settings")
        if not settings.enable_payment:
            self.payment_required = 0
            self.payment_status = "Not Required"
            self.razorpay_payment_status = ""
            return

        fee = _get_fee_for_type(settings, self.transcript_type)
        copies = max(int(self.num_copies or 1), 1)
        base_fee = fee * copies
        if self.urgency == "Urgent" and settings.urgent_fee:
            base_fee += settings.urgent_fee

        self.payment_required = 1
        self.fee_amount = base_fee
        self.payment_status = "Pending"
        self.razorpay_payment_status = ""
        self.status = "Payment Pending"


def _build_email_ctx(doc, transcript_doc=""):
    from slcm.api.transcript_request import _get_student_full_name
    return {
        "student":          doc.student,
        "student_name":     _get_student_full_name(doc.student),
        "request_name":     doc.name,
        "transcript_type":  doc.transcript_type,
        "rejection_reason": doc.rejection_reason or "",
        "transcript_doc":   transcript_doc,
    }


def _get_fee_for_type(settings, transcript_type):
    return {
        "Interim Transcript":      settings.interim_fee or 0,
        "Final Transcript":        settings.final_fee or 0,
        "Consolidated Marksheet":  settings.marksheet_fee or 0,
        "Duplicate Transcript":    settings.duplicate_fee or 0,
        "Digital Transcript":      settings.digital_fee or 0,
    }.get(transcript_type, settings.interim_fee or 0)
