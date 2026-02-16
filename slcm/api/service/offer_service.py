import frappe
import json
from frappe import _, throw
from frappe.utils import add_days, getdate, now_datetime, get_datetime
from frappe.utils.pdf import get_pdf

class OfferService:
    """
    Offer Lifecycle Engine - Service Layer.
    Consolidates business logic for student offer management.
    """

    @staticmethod
    def get_active_config(admission_year, admission_cycle, campus):
        """
        Validates and returns the unique active Offer Configuration 
        for a given year, cycle, and campus.
        """
        config_name = frappe.db.get_value("Offer Configuration", {
            "admission_year": admission_year,
            "admission_cycle": admission_cycle,
            "campus": campus,
            "is_active": 1
        })

        if not config_name:
            throw(_("No active Offer Configuration found for Year: {0}, Cycle: {1}, Campus: {2}").format(
                admission_year, admission_cycle, campus
            ))
            
        return frappe.get_doc("Offer Configuration", config_name)

    @staticmethod
    @frappe.whitelist(allow_guest=True)
    def generate_offer(applicant, campus, program, cycle, admission_year=None):
        """
        Main entry point for generating an offer letter.
        Ensures idempotency and follows financial snapshotting rules.
        """
        # Validate unique identifier (Year) if not provided
        if not admission_year:
            admission_year = frappe.db.get_value("Admission Application", 
                {"applicant": applicant, "campus": campus, "admission_cycle": cycle}, 
                "admission_year") or frappe.db.get_value("Applicant", applicant, "admission_year")

        if not admission_year:
            throw(_("Admission Year missing for applicant {0}. Unable to determine configuration.").format(applicant))

        # Idempotency: Prevent duplicate offers for same campus , cycle , program  and admission_year
        existing = frappe.db.exists("Offer Letter", {
            "applicant": applicant,
            "admission_cycle": cycle,
            "campus": campus,
            "program": program,
            "admission_year": admission_year,
            "offer_status": ["not in", ["Expired", "Withdrawn", "Rejected"]]
        })
        if existing:
            throw(_("An active offer already exists for Applicant {0} in Cycle {1} for Campus {2} and Program {3}.").format(applicant, cycle, campus, program))

        config = OfferService.get_active_config(admission_year, cycle, campus)

        # Start Transaction
        frappe.db.begin()
        try:
            offer = frappe.new_doc("Offer Letter")
            offer.applicant = applicant
            offer.campus = campus
            offer.program = program
            offer.admission_cycle = cycle
            offer.offer_configrationn = config.name  # Note: fieldname typo from DocType definition
            offer.offer_status = "Draft"
            offer.issued_on = now_datetime()
            
            # Set validity/deadline
            offer.payment_deadline = OfferService._calculate_deadline(config)
            
            # Freeze Fees
            fee_data = OfferService._calculate_and_freeze_fees(applicant, program, campus, cycle)
            offer.payable_amount = fee_data.get("total_payable")
            
            # Snapshot Content
            offer.rendered_content = OfferService._render_snapshot(offer, config.email_template)
            
            offer.insert(ignore_permissions=True)

            # Create the actual snapshot record
            OfferService._create_snapshot_record(offer.name, fee_data)

            # Generate and Attach PDF
            if config.pdf_format:
                OfferService._generate_offer_pdf(offer, config.pdf_format)

            # Transition to Issued
            offer.offer_status = "Issued"
            offer.save(ignore_permissions=True)

            # Log action
            OfferService.log_action(offer.name, "Issued", _("Offer generated and issued automatically."))

            frappe.db.commit()
            return offer.name
        except Exception as e:
            frappe.db.rollback()
            raise e

    @staticmethod
    def accept_offer(offer_name):
        """
        Business logic for accepting an offer.
        Validates transition and deadline.
        """
        offer = frappe.get_doc("Offer Letter", offer_name)
        
        if offer.offer_status != "Issued":
            throw(_("Only 'Issued' offers can be accepted. Current status: {0}").format(offer.offer_status))

        if offer.payment_deadline and get_datetime(offer.payment_deadline) < now_datetime():
            throw(_("This offer expired on {0} and cannot be accepted.").format(offer.payment_deadline))

        offer.offer_status = "Accepted"
        offer.accepted_on = now_datetime()
        offer.save(ignore_permissions=True)

        OfferService.log_action(offer.name, "Accepted")
        return True

    @staticmethod
    def reject_offer(offer_name, reason=None):
        """
        Handles student/admin rejection of an offer.
        """
        offer = frappe.get_doc("Offer Letter", offer_name)
        
        if offer.offer_status not in ["Issued", "Draft"]:
            throw(_("Cannot reject offer in status: {0}").format(offer.offer_status))

        offer.offer_status = "Rejected"
        offer.save(ignore_permissions=True)

        OfferService.log_action(offer.name, "Rejected", reason)
        return True

    @staticmethod
    def expire_offers():
        """
        Scheduled job logic to transition 'Issued' offers to 'Expired' 
        after the payment deadline.
        """
        to_expire = frappe.get_all("Offer Letter", filters={
            "offer_status": "Issued",
            "payment_deadline": ["<", now_datetime()]
        }, fields=["name"])

        processed = 0
        for entry in to_expire:
            try:
                # We save each individually to trigger any status hooks if needed
                doc = frappe.get_doc("Offer Letter", entry.name)
                doc.offer_status = "Expired"
                doc.save(ignore_permissions=True)
                OfferService.log_action(entry.name, "Expired", _("Automatically expired by system scheduler."))
                processed += 1
            except Exception:
                frappe.log_error(frappe.get_traceback(), _("Manual Offer Expiry Failed"))
        
        return processed

    @staticmethod
    @frappe.whitelist()
    def bulk_generate_offers(applicants_json):
        """
        API endpoint for bulk offer generation.
        Expects JSON list of dicts: [{"applicant": "...", "campus": "...", "program": "...", "cycle": "..."}]
        """
        if isinstance(applicants_json, str):
            applicants = json.loads(applicants_json)
        else:
            applicants = applicants_json

        results = {"success": [], "errors": []}
        
        for data in applicants:
            try:
                name = OfferService.generate_offer(
                    applicant=data.get("applicant"),
                    campus=data.get("campus"),
                    program=data.get("program"),
                    cycle=data.get("cycle"),
                    admission_year=data.get("admission_year")
                )
                results["success"].append({"applicant": data.get("applicant"), "offer": name})
            except Exception as e:
                # We catch errors to continue with next applicants
                results["errors"].append({"applicant": data.get("applicant"), "error": str(e)})
                frappe.log_error(f"Bulk Offer Generation Error: {str(e)}")

        return results

    @staticmethod
    @frappe.whitelist()
    def bulk_update_status(offer_names, action, notes=None):
        """
        API endpoint for bulk status updates (Accept/Reject).
        """
        if isinstance(offer_names, str):
            offer_names = json.loads(offer_names)

        results = {"success": [], "errors": []}
        
        for name in offer_names:
            try:
                if action == "Accepted":
                    OfferService.accept_offer(name)
                elif action == "Rejected":
                    OfferService.reject_offer(name, reason=notes)
                else:
                    throw(_("Invalid action: {0}").format(action))
                results["success"].append(name)
            except Exception as e:
                results["errors"].append({"name": name, "error": str(e)})

        return results

    # --- Internal Utilities ---

    @staticmethod
    def _calculate_deadline(config):
        """Determines payment deadline based on configuration."""
        if config.validity_type == "Days valid":
            return add_days(now_datetime(), config.valid_days or 0)
        elif config.validity_type == "Fixed due date":
            return get_datetime(config.offer_expiry_date)
        return None

    @staticmethod
    def _calculate_and_freeze_fees(applicant, program, campus, cycle):
        """
        Financial Logic: Calculates fees and returns a structured dict.
        Place for actual fee calculation logic integrations.
        """
        # Placeholder integration with Fee Engine
        # In production, this would look up Fee Structure for the Program/Cycle
        # For demonstration, we assume standard calculation.
        
        # Example lookup:
        # fee_doc = frappe.get_doc("Fee Schedule", {"program": program, ...})
        
        return {
            "base_fee": 100000, 
            "scholarship_amount": 10000,
            "tax_amount": 16200,
            "total_payable": 106200,
            "breakdown": {"Base": 100000, "Tax": 16200, "Scholarship": -10000}
        }

    @staticmethod
    def _create_snapshot_record(offer_name, fee_data):
        """Creates the Offer Fee Snapshot record."""
        snapshot = frappe.new_doc("Offer Fee Snapshot")
        snapshot.offer_id = offer_name
        snapshot.base_fee = fee_data.get("base_fee")
        snapshot.scholarship_amount = fee_data.get("scholarship_amount")
        snapshot.tax_amount = fee_data.get("tax_amount")
        snapshot.total_payable = fee_data.get("total_payable")
        snapshot.frozen_on = now_datetime()
        snapshot.frozen_by = frappe.session.user
        # Note: If breakdown_json field exists:
        # snapshot.breakdown_json = json.dumps(fee_data.get("breakdown"))
        snapshot.insert(ignore_permissions=True)

    @staticmethod
    def _render_snapshot(offer_doc, template_name):
        """Renders the HTML content snapshot of the offer."""
        if not template_name:
            return ""
            
        tpl_doc = frappe.get_doc("Email Templates", template_name)
        html = tpl_doc.response_html if tpl_doc.use_html else tpl_doc.response
        
        if not html:
            return ""

        # Context for rendering
        context = {
            "doc": offer_doc,
            "applicant": frappe.get_doc("Applicant", offer_doc.applicant) if offer_doc.applicant else None,
            "frappe": frappe
        }
        
        return frappe.render_template(html, context)

    @staticmethod
    def _generate_offer_pdf(offer_doc, print_format):
        """Generates PDF and attaches it to the Offer Letter record."""
        try:
            pdf_content = frappe.get_print("Offer Letter", offer_doc.name, print_format, as_pdf=True)
            
            file_name = f"Offer_Letter_{offer_doc.name}.pdf"
            
            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": file_name,
                "attached_to_doctype": "Offer Letter",
                "attached_to_name": offer_doc.name,
                "attached_to_field": "offer_letter_pdf",
                "content": pdf_content,
                "is_private": 1
            })
            _file.insert(ignore_permissions=True)
            
            # Update the attachment field in the doc (avoid recursive save)
            frappe.db.set_value("Offer Letter", offer_doc.name, "offer_letter_pdf", _file.file_url)
            
        except Exception as e:
            frappe.log_error(f"PDF Generation Failed for {offer_doc.name}: {str(e)}")

    @staticmethod
    def log_action(offer_name, action, notes=None):
        """Utility to log every transition in the lifecycle."""
        log = frappe.new_doc("Offer Action Log")
        log.offer_letter = offer_name
        log.action = action
        log.performed_by = frappe.session.user
        log.timestamp = now_datetime()
        log.notes = notes
        log.insert(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
def generate_offer(applicant, campus, program, cycle, admission_year=None):
    return OfferService.generate_offer(applicant, campus, program, cycle, admission_year)

@frappe.whitelist()
def bulk_generate_offers(applicants_json):
    return OfferService.bulk_generate_offers(applicants_json)

@frappe.whitelist()
def bulk_update_status(offer_names, action, notes=None):
    return OfferService.bulk_update_status(offer_names, action, notes)
