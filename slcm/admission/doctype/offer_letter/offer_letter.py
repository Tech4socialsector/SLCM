import io
import json
import os
import zipfile

import frappe
from frappe import _, throw, msgprint
from frappe.model.document import Document
from frappe.utils.file_manager import save_file


class OfferLetter(Document):

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
        if self.status == "Draft" and self.fee_structure:
            from slcm.api.service.fee_service import FeeService
            is_foreign = frappe.db.get_value("Applicant", self.applicant, "foriegn_national") == "Yes"
            fee_data = FeeService._calculate_and_freeze_fees(self.fee_structure, is_foreign=is_foreign)
            self.payable_amount = fee_data.get("total_payable")

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

        if self.status not in status_map:
            return
            
        from slcm.api.service.offer_service import OfferService
        from slcm.api.service.fee_service import FeeService

        sa_status, app_status = status_map[self.status]

        # 0. Automatic Fee Assignment for Accepted status
        if self.status == "Accepted":
            FeeService.create_fee_assignment_from_offer(self)
            
            # 0.1 Withdraw other issued offers for this applicant's email
            applicant_email = self.email or frappe.db.get_value("Applicant", self.applicant, "email")
            if applicant_email:
                other_offers = frappe.get_all("Offer Letter", filters={
                    "email": applicant_email,
                    "name": ["!=", self.name],
                    "status": "Issued"
                }, pluck="name")
                
                for other_name in other_offers:
                    other_doc = frappe.get_doc("Offer Letter", other_name)
                    other_doc.status = "Withdrawn"
                    other_doc.db_set("status", "Withdrawn")
                    
                    # Manually trigger sync since we used db_set to avoid full validation hooks
                    other_doc.sync_status_to_seat_allocation()
                    


        # 1. Automatic Fee Cancellation for termination statuses
        if self.status in ["Rejected", "Expired", "Withdrawn"]:
            FeeService.cancel_linked_fee_assignment(self.name, reason=self.status)

        # 2. Synchronize Status to Seat Allocation
        OfferService.sync_seat_allocation_status(self, sa_status)

        # 3. Synchronize Status to Applicant
        OfferService.update_applicant_status(self.applicant, app_status)

    def validate_status_transition(self):
        """Ensures that status transitions follow the defined lifecycle."""
        if self.is_new():
            if not self.status:
                self.status = "Draft"
            return

        db_status = frappe.db.get_value(self.doctype, self.name, "status")
        if db_status == self.status:
            return


    @frappe.whitelist()
    def sync_fee_amount(self):
        from slcm.api.service.fee_service import FeeService
        if self.status not in ["Draft", "Issued"]:
            frappe.throw(_("Fee can only be synced when Offer Letter is in Draft or Issued status."))
        
        if not self.fee_structure:
            frappe.throw(_("Fee Structure is not set."))

        is_foreign = frappe.db.get_value("Applicant", self.applicant, "foriegn_national") == "Yes"
        
        fee_data = FeeService._calculate_and_freeze_fees(self.fee_structure, is_foreign=is_foreign)
        new_payable_amount = fee_data.get("total_payable")
        
        if new_payable_amount != self.payable_amount:
            self.payable_amount = new_payable_amount
            if self.status == "Issued":
                self.ignore_lock = True
                self.edit_reason = "Synced fee amount from updated Fee Structure"
            self.save(ignore_permissions=True)
            return True
        return False

    def handle_audit_and_locking(self):
        """Detects changes in sensitive fields and enforces locking."""
        if self.is_new():
            return

        db_doc = self.get_doc_before_save()
        if not db_doc:
            return

        sensitive_fields = ["status", "payment_deadline", "payable_amount", "campus", "program","accepted_on"]
        db_status = db_doc.status

        # If Issued or beyond, restrict modification of sensitive fields
        is_locked_state = db_status not in ["Draft"]
        
        for fieldname in sensitive_fields:
            if self.has_value_changed(fieldname):
                # Status change is handled by validate_status_transition
                if fieldname == "status":
                    continue
                
                # Check for lock override
                if is_locked_state and not self.get("ignore_lock"):
                    # Exception 1: Allow setting accepted_on and status for standard transitions
                    is_status_accept = fieldname == "status" and self.status == "Accepted"
                    is_field_accept = fieldname == "accepted_on" and not db_doc.get("accepted_on")
                    
                    if is_status_accept or is_field_accept:
                        pass
                    else:
                        self.enforce_lock_override(fieldname)



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



    def on_payment_authorized(self, status):
        """
        Called by the payments app when a payment is successful.
        """
        if status in ["Authorized", "Completed"]:
            self.status = "Payment Completed"
            self.db_set("status", "Payment Completed")
            
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
		"status",
	]:
		if filters.get(field):
			query_filters[field] = filters[field]

	output_format = filters.get("output_format", "ZIP Archive")

	offers = frappe.get_all(
		"Offer Letter",
		filters=query_filters,
		fields=["name", "applicant", "offer_letter_pdf", "offer_configrationn"],
	)

	if not offers:
		frappe.throw(_("No offer letters found for the selected filters."))

	if len(offers) > 1000:
		frappe.enqueue(
			method="slcm.admission.doctype.offer_letter.offer_letter.bulk_zip_worker",
			queue="long",
			offers=offers,
			user=frappe.session.user,
			output_format=output_format
		)
		return {
			"status": "enqueued",
			"message": _("Preparing {0} for {1} offer letters in the background. You will receive a notification when it's ready.").format(output_format, len(offers))
		}

	file_url, summary, errors = process_bulk_zip(offers, user=frappe.session.user, output_format=output_format)
	return file_url

@frappe.whitelist()
def bulk_zip_worker(offers, user, output_format="ZIP Archive"):
	frappe.set_user(user)
	try:
		file_url, summary, errors = process_bulk_zip(offers, user=user, output_format=output_format)
		
		error_details = ""
		if errors:
			error_details = "<br><br><b>Errors:</b><ul>" + "".join([f"<li>{e}</li>" for e in errors[:250]]) + "</ul>"
			if len(errors) > 250:
				error_details += _("<p>...and {0} more errors.</p>").format(len(errors) - 250)

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

def process_bulk_zip(offers, user=None, output_format="ZIP Archive"):
	import tempfile
	import os
	
	total = len(offers)
	success_count = 0
	failure_count = 0
	errors = []

	# Use a temporary file on disk for memory safety
	with tempfile.NamedTemporaryFile(delete=False, suffix=".zip" if output_format == "ZIP Archive" else ".pdf") as temp_out:
		temp_path = temp_out.name
		
		if output_format == "ZIP Archive":
			with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
				for i, offer in enumerate(offers):
					filename = f"{offer.applicant} - offer letter.pdf"
					try:
						content = _get_offer_pdf_content(offer)
						if content:
							zip_file.writestr(filename, content)
							success_count += 1
						else:
							failure_count += 1
							errors.append(f"Empty content for {offer.name}")
					except Exception as e:
						failure_count += 1
						errors.append(f"Error zipping {offer.name}: {str(e)}")
					
					_update_bulk_progress(i, total, success_count, failure_count, user, "bulk_offer_download_progress")
		
		else:
			# PDF Merging logic
			from pypdf import PdfWriter
			merger = PdfWriter()
			
			for i, offer in enumerate(offers):
				try:
					content = _get_offer_pdf_content(offer)
					if content:
						import io
						merger.append(io.BytesIO(content))
						success_count += 1
					else:
						failure_count += 1
						errors.append(f"Empty content for {offer.name}")
				except Exception as e:
					failure_count += 1
					errors.append(f"Error merging {offer.name}: {str(e)}")
				
				_update_bulk_progress(i, total, success_count, failure_count, user, "bulk_offer_download_progress")
			
			with open(temp_path, "wb") as f:
				merger.write(f)
			merger.close()

	if success_count == 0:
		if os.path.exists(temp_path):
			os.remove(temp_path)
		frappe.throw(_("Failed to generate any offer letters. Please check the error logs."))

	# Save the final file from disk to Frappe
	final_filename = f"Bulk_Offers_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}"
	final_filename += ".zip" if output_format == "ZIP Archive" else ".pdf"
	
	with open(temp_path, "rb") as f:
		saved_file = save_file(
			final_filename,
			f.read(),
			"Offer Letter",
			"Bulk Download",
			is_private=1,
		)

	# Cleanup temp file
	if os.path.exists(temp_path):
		os.remove(temp_path)

	summary = _("Bulk Download Complete: {0} offers successful").format(success_count)
	if failure_count > 0:
		summary += _(", {0} failed").format(failure_count)

	return saved_file.file_url, summary, errors

def _get_offer_pdf_content(offer):
	"""Internal helper to get PDF content for an offer letter (cached or dynamic)."""
	pdf_content = None
	# 1. Try to get existing PDF from offer_letter_pdf field
	if offer.offer_letter_pdf:
		try:
			file_path = frappe.get_site_path("public", offer.offer_letter_pdf.lstrip("/"))
			if os.path.exists(file_path):
				with open(file_path, "rb") as f:
					pdf_content = f.read()
		except Exception:
			pass

	# 2. Fallback: Generate PDF on the fly
	if not pdf_content:
		print_format = "Offer Letter"
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
	return pdf_content

def _update_bulk_progress(i, total, success, failure, user, event_name):
	"""Internal helper for adaptive progress updates."""
	update_step = 100 if total > 1000 else 10
	if (i + 1) % update_step == 0 or i == total - 1:
		frappe.publish_realtime(event_name, {
			"progress": [(i + 1) * 100 / total],
			"title": _("Preparing Bulk Download..."),
			"description": _("Processing {0} of {1} records ({2} successful, {3} failed)").format(
				i + 1, total, success, failure
			)
		}, user=user or frappe.session.user)

