import io
import json
import os
import zipfile

import frappe
from frappe import _, throw, msgprint
from frappe.model.document import Document
from frappe.utils.file_manager import save_file


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
            "Accepted": ("Offer Accepted", "Offer Accepted"),
            "Payment Completed": ("Fee Paid", "Fee Paid"),
            "Issued": ("Offer Issued", "Offer Issued")
        }

        if self.offer_status not in status_map:
            return
            
        from slcm.api.service.offer_service import OfferService
        from slcm.api.service.fee_service import FeeService

        sa_status, app_status = status_map[self.offer_status]

        # 0. Automatic Fee Assignment for Accepted status
        if self.offer_status == "Accepted":
            FeeService.create_fee_assignment_from_offer(self)

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
                    # Exception 1: Allow setting accepted_on and offer_status for standard transitions
                    is_status_accept = fieldname == "offer_status" and self.offer_status == "Accepted"
                    is_field_accept = fieldname == "accepted_on" and not db_doc.get("accepted_on")
                    
                    if is_status_accept or is_field_accept:
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


@frappe.whitelist()
def get_bulk_offers_zip(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)

	query_filters = {}
	for field in [
		"campus",
		"program",
		"admission_cycle",
		"academic_year",
		"admission_year",
		"offer_status",
	]:
		if filters.get(field):
			query_filters[field] = filters[field]

	offers = frappe.get_all(
		"Offer Letter",
		filters=query_filters,
		fields=["name", "applicant", "offer_letter_pdf", "offer_configrationn"],
	)

	if not offers:
		frappe.throw(_("No offer letters found for the selected filters."))

	if len(offers) > 10:
		frappe.enqueue(
			method="slcm.admission.doctype.offer_letter.offer_letter.bulk_zip_worker",
			queue="long",
			offers=offers,
			user=frappe.session.user
		)
		return {
			"status": "enqueued",
			"message": _("Preparing ZIP for {0} offer letters in the background. You will receive a notification when it's ready.").format(len(offers))
		}

	return process_bulk_zip(offers, user=frappe.session.user)

@frappe.whitelist()
def bulk_zip_worker(offers, user):
	frappe.set_user(user)
	try:
		file_url, summary, errors = process_bulk_zip(offers, user=user)
		
		error_details = ""
		if errors:
			error_details = "<br><br><b>Errors:</b><ul>" + "".join([f"<li>{e}</li>" for e in errors[:10]]) + "</ul>"
			if len(errors) > 10:
				error_details += _("<p>...and {0} more errors.</p>").format(len(errors) - 10)

		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
		enqueue_create_notification(
			[user],
			{
				"subject": _("Bulk Offer Download Ready"),
				"email_content": _("{0}. <a href='{1}' target='_blank'><b>Click here to download</b></a>. {2}").format(summary, file_url, error_details),
				"type": "Alert",
				"document_type": "Offer Letter"
			}
		)

		# AUTO-DOWNLOAD TRIGGER
		frappe.publish_realtime("bulk_download_complete", {
			"file_url": file_url,
			"doctype": "Offer Letter"
		}, user=user)

	except Exception as e:
		frappe.log_error(f"Bulk Offer Download Worker Failed: {e!s}", "Bulk Download Error")

def process_bulk_zip(offers, user=None):
	zip_buffer = io.BytesIO()
	total = len(offers)
	success_count = 0
	failure_count = 0
	errors = []

	# Bulk Offer Letters filename format: {applicant} - offer letter.pdf
	with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
		for i, offer in enumerate(offers):
			filename = f"{offer.applicant} - offer letter.pdf"
			pdf_content = None

			try:
				# 1. Try to get existing PDF from offer_letter_pdf field
				if offer.offer_letter_pdf:
					try:
						file_path = frappe.get_site_path("public", offer.offer_letter_pdf.lstrip("/"))
						if os.path.exists(file_path):
							with open(file_path, "rb") as f:
								pdf_content = f.read()
					except Exception:
						pdf_content = None

				# 2. Fallback: Generate PDF on the fly
				if not pdf_content:
					print_format = "Offer Letter 2026"
					if offer.get("offer_configrationn"):
						pdf_format = frappe.db.get_value("Offer Configuration", offer.offer_configrationn, "pdf_format")
						if pdf_format:
							print_format = pdf_format

					pdf_content = frappe.get_print(
						"Offer Letter",
						offer.name,
						print_format,
						as_pdf=True,
					)

				if pdf_content:
					zip_file.writestr(filename, pdf_content)
					success_count += 1
				else:
					failure_count += 1
					errors.append(f"Could not retrieve PDF for {offer.name}")

			except Exception as e:
				failure_count += 1
				error_msg = str(e)
				errors.append(f"Error processing {offer.name}: {error_msg}")
				frappe.log_error(
					f"Error generating PDF for {offer.name}: {error_msg}",
					"Bulk Offer Letter Download Error",
				)
				continue

			# Adaptive Real-time progress update
			update_step = 100 if total > 1000 else 10
			if (i + 1) % update_step == 0 or i == total - 1:
				frappe.publish_realtime("bulk_offer_download_progress", {
					"progress": [(i + 1) * 100 / total],
					"title": _("Preparing Bulk Download..."),
					"description": _("Processing {0} of {1} offer letters ({2} successful, {3} failed)").format(
						i + 1, total, success_count, failure_count
					)
				}, user=user or frappe.session.user)

	if success_count == 0:
		frappe.throw(_("Failed to generate any offer letters. Please check the error logs."))

	zip_filename = f"Bulk_Offer_Letters_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
	saved_zip = save_file(
		zip_filename,
		zip_buffer.getvalue(),
		"Offer Letter",
		"Bulk Download",
		is_private=1,
	)

	summary = _("Bulk Download Complete: {0} offers successful").format(success_count)
	if failure_count > 0:
		summary += _(", {0} failed").format(failure_count)

	return saved_zip.file_url, summary, errors
