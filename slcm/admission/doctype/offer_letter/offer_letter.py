import frappe
import json
from frappe import _, throw, msgprint
from frappe.model.document import Document

class OfferLetter(Document):

    def autoname(self):
        if getattr(self, "naming_series", None):
            from frappe.model.naming import make_autoname
            self.name = make_autoname(self.naming_series)
        else:
            self.name = f"OL-{self.applicant}-{self.program}-{self.campus}"
    def before_insert(self):
        """
        Ensure data integrity before record creation.
        """
        # If admission_cycle is fetched from applicant and points to a non-existent record,
        # we should ensure it's valid if we have a configuration selected.
        if self.applicant and self.admission_cycle:
            if not frappe.db.exists("Admission Cycle", self.admission_cycle):
                # If we have an offer configuration, use its cycle instead
                if self.offer_configrationn:
                    self.admission_cycle = frappe.db.get_value("Offer Configuration", self.offer_configrationn, "admission_cycle")
                else:
                    self.admission_cycle = None

    def validate(self):
        print("VALIDATE TRIGGERED")
        self.set_notification_receiver()
        self.validate_status_transition()
        self.handle_audit_and_locking()

    def set_notification_receiver(self):
        if self.applicant:
            applicant_email = frappe.db.get_value("Applicant", self.applicant, "email")
            if applicant_email:
                user_name = frappe.db.get_value("User", {"email": applicant_email}, "name")
                if user_name:
                    self.notification_receiver = user_name

    def on_update(self):
        # Deterministic logging after successful update
        # We use flags to pass audit data from validate to on_update to avoid redundant logic
        print("on update called for offer letter")
        if getattr(self, "_audit_logs", None):
            for log_data in self._audit_logs:
                self.log_action(**log_data)
                print(f"Logged action called: {log_data['action']} for Offer Letter {self.name}")
            # Clear logs to avoid duplicates in same session
            self._audit_logs = []

        self.sync_status_to_seat_allocation()

    def sync_status_to_seat_allocation(self):
        """
        If this offer is Rejected, Expired, or Withdrawn, 
        update the Seat Allocation status and cancel linked fees.
        """
        if self.offer_status not in ["Rejected", "Expired", "Withdrawn"]:
            return
        
        # 1. Cancel Linked Fee Assignment automatically
        from slcm.api.service.fee_service import FeeService
        FeeService.cancel_linked_fee_assignment(self.name)

        # Find Seat Allocation
        sa_records = frappe.get_all("Seat Allocation", filters={
            "admission_cycle": self.admission_cycle,
            "campus": self.campus,
            "docstatus": ["<", 2]
        }, fields=["name"])

        for sa_rec in sa_records:
            sa_doc = frappe.get_doc("Seat Allocation", sa_rec.name)
            updated = False
            for row in sa_doc.selection_applicant:
                if row.applicant == self.applicant and row.program == self.program:
                    if row.selection_status != "Rejected":
                        row.selection_status = "Rejected"
                        updated = True
                        print(f"Sync: Updated {self.applicant} in {sa_rec.name} to Rejected")

            if updated:
                # Save without permission to trigger the seat_allocation.py hooks
                sa_doc.save(ignore_permissions=True)
                # Important: Committing here might be risky if we are in a transaction,
                # but Frappe's save() inside on_update is generally okay.

    def validate_status_transition(self):
        """Ensures that status transitions follow the defined lifecycle."""
        if self.is_new():
            if not self.offer_status:
                self.offer_status = "Draft"
            return

        db_status = frappe.db.get_value(self.doctype, self.name, "offer_status")
        if db_status == self.offer_status:
            return

        allowed_transitions = {
            "Draft": ["Issued", "Withdrawn"],
            "Issued": ["Accepted", "Rejected", "Expired", "Withdrawn"],
            "Accepted": ["Withdrawn", "Payment Completed"],
            "Payment Completed": ["Withdrawn"],
            "Rejected": [],
            "Expired": ["Issued"],
            "Withdrawn": ["Draft"]
        }

        if self.offer_status not in allowed_transitions.get(db_status, []):
            throw(_("Invalid status transition: From {0} to {1}").format(db_status, self.offer_status))

        # Track status change for audit
        self._queue_audit_log(
            action=self.offer_status,
            notes=_("Status changed from {0} to {1}").format(db_status, self.offer_status)
        )

    def handle_audit_and_locking(self):
        """Detects changes in sensitive fields and enforces locking."""
        if self.is_new():
            return

        db_doc = self.get_doc_before_save()
        if not db_doc:
            return

        sensitive_fields = ["offer_status", "payment_deadline", "payable_amount", "campus", "program","accepted_on"]
        db_status = db_doc.offer_status

        # If Issued or beyond, restrict modification of sensitive fields
        is_locked_state = db_status not in ["Draft"]
        
        for fieldname in sensitive_fields:
            if self.has_value_changed(fieldname):
                # Status change is handled by validate_status_transition
                if fieldname == "offer_status":
                    continue
                
                # Check for lock override
                if is_locked_state and not self.get("ignore_lock"):
                    # Exception: Allow setting accepted_on for the first time
                    if fieldname == "accepted_on" and not db_doc.get("accepted_on"):
                        pass
                    else:
                        self.enforce_lock_override(fieldname)

                # Queue log for field change
                self._queue_audit_log(
                    action="Field Updated",
                    field_changed=fieldname,
                    old_value=db_doc.get(fieldname),
                    new_value=self.get(fieldname),
                    reason=self.get("edit_reason") or frappe.flags.edit_reason or ""
                )

    def enforce_lock_override(self, fieldname):
        """Validates if the user has permission to override a locked field."""

        if "System Manager" not in frappe.get_roles():
            throw(_("Modification of '{0}' is locked after the offer is Issued. Only System Managers can override.").format(
                self.meta.get_label(fieldname)
            ))

        # Require reason for override
        reason = (self.get("edit_reason") or "").strip()

        if not reason:
            throw(_("A reason is required to override the lock on field '{0}'. Please provide an Edit Reason before saving.").format(
                self.meta.get_label(fieldname)
            ))

    def _queue_audit_log(self, **kwargs):
        """Queues an audit log to be created in on_update."""
        if not hasattr(self, "_audit_logs"):
            self._audit_logs = []
        
        # Ensure timestamp and user are set (though helper handles it)
        kwargs.update({
            "timestamp": frappe.utils.now_datetime(),
            "performed_by": frappe.session.user
        })
        self._audit_logs.append(kwargs)

    def log_action(self, action, field_changed=None, old_value=None, new_value=None, reason=None, notes=None, **kwargs):
        """Creates an entry in the Offer Action Log."""
        # Prevent duplicate status logs if already logged by generate_offer etc.
        # This is a safety check for deterministic logging.
        print(f"Logging action: {action} for Offer Letter {self.name}")
        log = frappe.new_doc("Offer Action Log")
        log.offer_letter = self.name
        log.action = action
        log.field_changed = field_changed
        log.old_value = frappe.as_json(old_value) if old_value is not None else None
        log.new_value = frappe.as_json(new_value) if new_value is not None else None
        log.reason = reason
        log.notes = notes
        log.timestamp = kwargs.get("timestamp") or frappe.utils.now_datetime()
        log.performed_by = kwargs.get("performed_by") or frappe.session.user
        log.insert(ignore_permissions=True)
        print(f"Logged action: {action} for Offer Letter {self.name} with log ID {log.name}")

    def on_payment_authorized(self, status):
        """
        Called by the payments app when a payment is successful.
        """
        if status in ["Authorized", "Completed"]:
            self.db_set("offer_status", "Payment Completed")
            
            # Update any linked Payment Request
            frappe.db.set_value("Payment Request", 
                {"reference_doctype": self.doctype, "reference_name": self.name}, 
                "status", "Paid")
            
            from slcm.api.service.offer_service import OfferService
            # Update Applicant status
            OfferService.update_applicant_status(self.applicant, application_status="Fee Paid")
            
            # 3. Update Applicant Fee Assignment status to 'Paid'
            frappe.db.set_value("Applicant Fee Assignment", 
                {"offer_letter": self.name, "status": ["!=", "Cancelled"]}, 
                "status", "Paid")

            # 4. Sync Seat Allocation child status
            OfferService.sync_seat_allocation_status(self, status="Fee Paid")

            # Note: We don't queue 'Fee Paid' log here because generate_receipt() 
            # will log 'Payment Received' with the receipt ID shortly after this method returns.
            # This prevents duplicate logs in the Offer Action history.
            
            self.on_update()

