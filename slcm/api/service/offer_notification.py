import frappe
from frappe import _

class OfferNotificationService:
    """
    Standalone service to handle Offer Letter notifications (Emails and Portal Notifications)
    triggered by status changes.
    """

    @staticmethod
    def process_status_change(offer_doc, old_status, new_status):
        if old_status == new_status:
            return

        if not offer_doc.offer_configrationn:
            return

        config = frappe.get_doc("Offer Configuration", offer_doc.offer_configrationn)

        # Rule 4: Based on this only send notification
        if not config.enable_notifications:
            return

        email_template_field = None
        portal_notification_subject = None
        portal_notification_content = None
        category = "Offer Letter"

        program_name = frappe.db.get_value("Programme", offer_doc.program, "program_name") or offer_doc.program
        
        # Try to get the Admission Fee amount from Applicant Fee Assignment
        full_fee_amount = frappe.db.get_value("Applicant Fee Assignment", {"offer_letter": offer_doc.name, "fee_type": "Admission Fee"}, "final_payable_amount")
        formatted_full_fee = frappe.format_value(full_fee_amount, {"fieldtype": "Currency"}) if full_fee_amount else ""

        # Rule 3: Use specific email fields based on status
        if new_status == "Issued":
            email_template_field = "offer_issued_email"
            portal_notification_subject = _("Admission Offer Issued")
            portal_notification_content = _("You have received an admission offer for {0}. Please check your email and portal for details.").format(program_name)
        elif new_status == "Accepted":
            email_template_field = "offer_accepted_email"
            portal_notification_subject = _("Admission Offer Accepted")
            portal_notification_content = _("You have successfully accepted the admission offer for {0}.").format(program_name)
        elif new_status == "Confirmation Fee Paid":
            email_template_field = "confirmation_fee_email"
            portal_notification_subject = _("Confirmation Fee Payment Completed")
            payable = frappe.format_value(offer_doc.payable_amount, offer_doc.meta.get_field("payable_amount"), offer_doc) if offer_doc.payable_amount else ""
            portal_notification_content = _("Your payment of {0} for {1} has been received successfully.").format(payable, program_name)
            category = "Fee"
        elif new_status == "Full Fee Paid":
            email_template_field = "full_fee_email"
            portal_notification_subject = _("Full Fee Payment Completed")
            if formatted_full_fee:
                portal_notification_content = _("Your payment of {0} for {1} has been received successfully.").format(formatted_full_fee, program_name)
            else:
                portal_notification_content = _("Your full fee payment for {0} has been received successfully.").format(program_name)
            category = "Fee"
        elif new_status == "Rejected":
            email_template_field = "offer_rejected_email"
            portal_notification_subject = _("Admission Offer Rejected")
            portal_notification_content = _("You have rejected the admission offer for {0}.").format(program_name)
        elif new_status == "Expired":
            email_template_field = "offer_expired_withdraw_email"
            portal_notification_subject = _("Admission Offer Expired")
            portal_notification_content = _("Your admission offer for {0} has expired as the payment deadline has passed.").format(program_name)
        elif new_status == "Withdrawn":
            email_template_field = "offer_expired_withdraw_email"
            portal_notification_subject = _("Admission Offer Withdrawn")
            portal_notification_content = _("Your admission offer for {0} has been withdrawn.").format(program_name)
        else:
            return

        # Send Portal Notification
        if portal_notification_subject and portal_notification_content:
            try:
                # Log to custom communication log
                from slcm.admission.utils.notifications import log_communication
                log_communication(
                    applicant=offer_doc.applicant,
                    communication_type="Portal Notification",
                    category=category,
                    subject=portal_notification_subject,
                    content=portal_notification_content,
                    reference_doctype="Offer Letter",
                    reference_name=offer_doc.name
                )
                
                # Create System Notification Log for UI (Top-right Bell Icon)
                receiver = offer_doc.notification_receiver
                if not receiver and offer_doc.applicant:
                    applicant_email = frappe.db.get_value("Applicant", offer_doc.applicant, "email")
                    if applicant_email:
                        receiver = frappe.db.get_value("User", {"email": applicant_email}, "name")
                
                if receiver:
                    frappe.get_doc({
                        "doctype": "Notification Log",
                        "subject": portal_notification_subject,
                        "email_content": portal_notification_content,
                        "document_type": "Offer Letter",
                        "document_name": offer_doc.name,
                        "for_user": receiver,
                        "type": "Alert"
                    }).insert(ignore_permissions=True)

            except Exception as e:
                frappe.log_error(f"Failed to log portal notification for Offer {offer_doc.name}: {str(e)}", "Offer Notification Service")

        # Rule 5: If there is no email template configured then don't send anything
        if email_template_field:
            template_name = config.get(email_template_field)
            if template_name:
                OfferNotificationService._send_email(offer_doc, template_name, new_status, config)

    @staticmethod
    def _send_email(offer_doc, template_name, status, config):
        applicant_email = frappe.db.get_value("Applicant", offer_doc.applicant, "email")
        if not applicant_email:
            frappe.log_error(f"Email not found for Applicant {offer_doc.applicant}", "Offer Email Error")
            return

        try:
            tpl = frappe.get_doc("Email Template", template_name)
            
            from slcm.api.service.offer_service import OfferService
            context = OfferService._get_template_context(offer_doc)
            
            subject = frappe.render_template(tpl.subject, context)
            message = frappe.render_template(tpl.response_html or tpl.response, context)

            attachments = None
            if status == "Issued" and config.pdf_format:
                from slcm.admission.doctype.offer_letter.offer_letter import _get_offer_pdf_content
                pdf_content = _get_offer_pdf_content(offer_doc)
                if pdf_content:
                    attachments = [{
                        "fname": f"Offer_Letter_{offer_doc.applicant}.pdf",
                        "fcontent": pdf_content
                    }]

            sender_email = None
            if tpl.get("email_account"):
                sender_email = frappe.db.get_value("Email Account", tpl.get("email_account"), "email_id") or tpl.get("email_account")

            frappe.sendmail(
                sender=sender_email,
                recipients=[applicant_email],
                subject=subject,
                message=message,
                attachments=attachments,
                reference_doctype="Offer Letter",
                reference_name=offer_doc.name,
                now=True
            )
            
            # Frappe automatically creates a Notification Log for the recipient when a Communication 
            # is attached to a document. We delete it here to prevent a duplicate, ugly UI notification 
            # with the full email body, since we manually create a much cleaner one earlier in process_status_change.
            frappe.db.delete("Notification Log", {
                "document_type": "Communication",
                "subject": subject
            })
            
        except Exception as e:
            frappe.log_error(f"Failed to send email for Offer {offer_doc.name}: {str(e)}", "Offer Notification Service")
