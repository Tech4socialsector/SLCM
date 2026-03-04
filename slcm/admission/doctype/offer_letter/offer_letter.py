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
        Synchronizes legal/admission status changes to linked records 
        (Seat Allocation, Applicant, and Fee Assignments).
        """
        status_map = {
            "Rejected": ("Offer Declined", "Offer Declined"),
            "Withdrawn": ("Offer Declined", "Offer Declined"),
            "Expired": ("Offer Expired", "Offer Expired"),
            "Accepted": ("Accepted", "Offer Accepted"),
            "Payment Completed": ("Fee Paid", "Fee Paid"),
            "Issued": ("Offer Issued", "Offer Issued")
        }

        if self.offer_status not in status_map:
            return
            
        from slcm.api.service.offer_service import OfferService
        from slcm.api.service.fee_service import FeeService

        sa_status, app_status = status_map[self.offer_status]

        # 1. Automatic Fee Cancellation for termination statuses
        if self.offer_status in ["Rejected", "Expired", "Withdrawn"]:
            FeeService.cancel_linked_fee_assignment(self.name)

        # 2. Synchronize Status to Seat Allocation
        OfferService.sync_seat_allocation_status(self, sa_status)

        # 3. Synchronize Status to Applicant
        OfferService.update_applicant_status(self.applicant, app_status)

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
            notes=_("Status changed from {0} to {1}").format(db_status, self.offer_status),
            reason=self.get("edit_reason") or frappe.flags.edit_reason or ""
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
            self.offer_status = "Payment Completed"
            self.db_set("offer_status", "Payment Completed")
            
            # Update any linked Payment Request
            frappe.db.set_value("Payment Request", 
                {"reference_doctype": self.doctype, "reference_name": self.name}, 
                "status", "Paid")
            # 3. Update Applicant Fee Assignment status to 'Paid'
            frappe.db.set_value("Applicant Fee Assignment", 
                {"offer_letter": self.name, "status": ["!=", "Cancelled"]}, 
                "status", "Paid")

            # Note: We don't queue 'Fee Paid' log here because generate_receipt() 
            # will log 'Payment Received' with the receipt ID shortly after this method returns.
            # This prevents duplicate logs in the Offer Action history.
            
            # The on_update() call below will trigger sync_status_to_seat_allocation() 
            # which correctly synchronizes Applicant and Seat Allocation status to 'Fee Paid'.
            self.on_update()

