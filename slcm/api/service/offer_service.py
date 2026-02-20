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
        filters = {
            "admission_year": admission_year,
            "campus": campus,
            "is_active": 1
        }
        
        # 1. Try strict match with provided cycle
        if admission_cycle:
            filters["admission_cycle"] = admission_cycle
            config_name = frappe.db.get_value("Offer Configuration", filters)
            if config_name:
                return frappe.get_doc("Offer Configuration", config_name)
        
        # 2. Fallback: If no strict match, try to find ANY active config for this Year and Campus
        # This helps if the applicant's cycle is missing, invalid, or pointing to a different ID
        # that actually represents the same semantic cycle.
        del filters["admission_cycle"]
        configs = frappe.db.get_all("Offer Configuration", filters=filters, fields=["name"])
        
        if len(configs) == 1:
            return frappe.get_doc("Offer Configuration", configs[0].name)
        elif len(configs) > 1:
            # If multiple active cycles exist, we can't safely fallback without more info
            throw(_("Multiple active Offer Configurations found for Year: {0}, Campus: {1}. Please specify a valid Admission Cycle.").format(
                admission_year, campus
            ))

        # 3. Final error if nothing found
        throw(_("No active Offer Configuration found for Year: {0}, Cycle: {1}, Campus: {2}").format(
            admission_year, admission_cycle, campus
        ))

    @staticmethod
    def resolve_admission_year(applicant, campus, cycle, admission_year=None):
        """
        Resolves the Admission Year based on direct input, Application, or Academic Year.
        """
        # 1. If admission_year is provided, check if it's actually an Academic Year
        if admission_year:
            if not frappe.db.exists("Admission Year", admission_year):
                # Probably an Academic Year name (e.g. 2026-2027), find active Admission Year for it
                resolved = frappe.db.get_value("Admission Year", 
                    {"academic_year": admission_year, "is_active": 1}, "name")
                if resolved:
                    return resolved
            return admission_year

        # 2. Try to get from Admission Application (most specific)
        admission_year = frappe.db.get_value("Admission Application", 
            {"applicant": applicant, "campus": campus, "admission_cycle": cycle}, 
            "admission_year")
        if admission_year:
            return admission_year

        # 3. Try to map from Applicant's Academic Year (most common fallback)
        academic_year = frappe.db.get_value("Applicant", applicant, "academic_year")
        if academic_year:
            admission_year = frappe.db.get_value("Admission Year", 
                {"academic_year": academic_year, "is_active": 1}, "name")
            
        return admission_year

    @staticmethod
    @frappe.whitelist(allow_guest=True)
    def generate_offer(applicant, campus, program, cycle, admission_year=None):
        """
        Main entry point for generating an offer letter.
        Ensures idempotency and follows financial snapshotting rules.
        """
        # Resolve the actual Admission Year DocType entry
        admission_year = OfferService.resolve_admission_year(applicant, campus, cycle, admission_year)

        if not admission_year:
            throw(_("No active Admission Year found for applicant {0}. Please ensure an Admission Year is configured and active for their Academic Year.").format(applicant))

        config = OfferService.get_active_config(admission_year, cycle, campus)
        resolved_cycle = config.admission_cycle

        # Idempotency: Prevent duplicate offers for same campus, cycle, program and admission_year
        existing = frappe.db.exists("Offer Letter", {
            "applicant": applicant,
            "admission_cycle": resolved_cycle,
            "campus": campus,
            "program": program,
            "admission_year": admission_year,
            "offer_status": ["not in", ["Expired", "Withdrawn", "Rejected"]]
        })
        if existing:
            throw(_("An active offer already exists for Applicant {0} in Cycle {1} for Campus {2} and Program {3}.").format(
                applicant, resolved_cycle, campus, program
            ))

        # Start Transaction
        frappe.db.begin()
        
        offer = frappe.new_doc("Offer Letter")
        offer.applicant = applicant
        offer.campus = campus
        offer.program = program
        offer.admission_year = admission_year
        offer.admission_cycle = resolved_cycle
        offer.offer_configrationn = config.name
        offer.offer_status = "Draft"
        offer.issued_on = now_datetime()
        
        # Find matching Fee Structure from Configuration
        fee_structure_name = None
        for row in config.fee_structure:
            fs_program = frappe.db.get_value("Fee Structure", row.fee_structure, "program")
            if fs_program == program:
                fee_structure_name = row.fee_structure
                break
        
        if not fee_structure_name:
            throw(_("No Fee Structure found for program {0} in Offer Configuration {1}").format(
                frappe.bold(program), frappe.bold(config.name)
            ))

        offer.fee_structure = fee_structure_name
        
        # Set validity/deadline from Fee Structure
        offer.payment_deadline = OfferService._calculate_deadline(fee_structure_name)
        
        # Freeze Fees from Fee Structure
        fee_data = OfferService._calculate_and_freeze_fees(fee_structure_name)
        offer.payable_amount = fee_data.get("total_payable")
        
        # Snapshot Content
        offer.rendered_content = OfferService._render_snapshot(offer, config.email_template)
        
        # Ensure Fetch From doesn't overwrite our resolved cycle if it's different from the applicant
        offer.insert(ignore_permissions=True)

        # Create the actual snapshot record
        OfferService._create_snapshot_record(offer.name, fee_data)

        # Generate and Attach PDF
        if config.pdf_format:
            OfferService._generate_offer_pdf(offer, config.pdf_format)
        
        # Send offer letter email to applicant
        OfferService._send_offer_letter_email(offer, config.email_template)
        
        # Transition to Issued
        offer.offer_status = "Issued"
        offer.save(ignore_permissions=True)

        frappe.db.commit()
        return {
            "offer_name": offer.name,
            "offer_status": offer.offer_status,
            "payment_deadline": offer.payment_deadline,
            "payable_amount": offer.payable_amount,
            "message": "Offer letter generated successfully"
        }

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
    def bulk_generate_offers(applicants):
        """
        API endpoint for bulk offer generation.
        Accepts:
        1. JSON list of dicts: [{"applicant": "...", "campus": "...", "program": "...", "cycle": "...", "admission_year": "..."}]
        2. JSON list of applicant names: ["APP-2026-00001", "APP-2026-00002"]
        """
        if isinstance(applicants, str):
            applicants = json.loads(applicants)

        results = {"success": [], "errors": []}
        
        for data in applicants:
            try:
                # Handle case where only applicant name is passed
                if isinstance(data, str):
                    applicant_name = data
                    # Fetch details from Applicant record
                    details = frappe.db.get_value("Applicant", applicant_name, 
                        ["campus", "program", "admission_cycle", "academic_year"], as_dict=1)
                    
                    if not details:
                        raise ValueError(_("Applicant {0} not found").format(applicant_name))
                    
                    payload = {
                        "applicant": applicant_name,
                        "campus": details.campus,
                        "program": details.program,
                        "cycle": details.admission_cycle,
                        "admission_year": details.academic_year
                    }
                else:
                    payload = data

                name = OfferService.generate_offer(
                    applicant=payload.get("applicant"),
                    campus=payload.get("campus"),
                    program=payload.get("program"),
                    cycle=payload.get("cycle"),
                    admission_year=payload.get("admission_year")
                )
                results["success"].append({"applicant": payload.get("applicant"), "offer": name})
            except Exception as e:
                results["errors"].append({"applicant": str(data), "error": str(e)})
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
    def _calculate_deadline(fee_structure_name):
        """Determines payment deadline based on Fee Structure."""
        if not fee_structure_name:
            return None
            
        valid_until = frappe.db.get_value("Fee Structure", fee_structure_name, "valid_until")
        # Ensure it's returned as a datetime/date object for the field
        return get_datetime(valid_until) if valid_until else None

    @staticmethod
    def extended_fee_deadline(fee_structure_name):
        """Updates payment deadline for all active Offer Letters linked to this Fee Structure."""
        if not fee_structure_name:
            return
            
        valid_until = frappe.db.get_value("Fee Structure", fee_structure_name, "valid_until")
        if not valid_until:
            return

        new_deadline = get_datetime(valid_until)
        
        # Find all active offers linked to this Fee Structure
        offers = frappe.get_all("Offer Letter", filters={
            "fee_structure": fee_structure_name,
            "offer_status": ["in", ["Draft", "Issued"]]
        }, fields=["name"])
        
        for entry in offers:
            doc = frappe.get_doc("Offer Letter", entry.name)
            if doc.payment_deadline != new_deadline:
                doc.payment_deadline = new_deadline
                doc.add_comment("Comment", _("Payment deadline automatically syncronized to {0} due to Fee Structure update.").format(
                    frappe.utils.format_datetime(new_deadline)
                ))
                doc.save(ignore_permissions=True)

    
    @staticmethod
    def _calculate_and_freeze_fees(fee_structure_name):
        """
        Financial Logic: Calculates fees and returns a structured dict.
        Fetches data from the linked Fee Structure and its components.
        """
        if not fee_structure_name:
            return {}

        fs_doc = frappe.get_doc("Fee Structure", fee_structure_name)
        
        base_fee = 0
        tax_amount = 0
        breakdown = {}
        components = []
        for component in fs_doc.components:
            base_fee += component.amount
            tax_amount += component.tax_amount
            # Use component name or the link name if name not set
            label = component.component_name or component.fee_component 
            breakdown[label] = component.total_amount
            
            components.append({
                "fee_component": component.fee_component,
                "component_name": component.component_name,
                "amount": component.amount,
                "is_taxable": component.is_taxable,
                "tax_rate": component.tax_rate,
                "tax_amount": component.tax_amount,
                "total_amount": component.total_amount
            })

        return {
            "base_fee": base_fee, 
            "scholarship_amount": 0, # Could be extended later if scholarships are handled
            "tax_amount": tax_amount,
            "total_payable": fs_doc.total_amount,
            "breakdown": breakdown,
            "components": components
        }

    @staticmethod
    def _send_offer_letter_email(offer, email_template):
        """Sends the offer letter email to the applicant."""
        if not email_template or not offer.applicant:
            return

        applicant_email = frappe.db.get_value("Applicant", offer.applicant, "email")
        if not applicant_email:
            frappe.log_error(f"Email not found for Applicant {offer.applicant}", "Offer Email Error")
            return

        tpl = frappe.get_doc("Email Templates", email_template)
        
        # Prepare context with full objects for template rendering
        context = OfferService._get_template_context(offer)
        
        subject = frappe.render_template(tpl.subject, context)
        message = OfferService._render_snapshot(offer, email_template)

        attachments = []
        if offer.offer_letter_pdf:
            try:
                # Use standard way to get file from URL or filters
                file_doc = frappe.get_doc("File", {
                    "attached_to_doctype": "Offer Letter",
                    "attached_to_name": offer.name,
                    "attached_to_field": "offer_letter_pdf"
                })
                attachments.append({
                    "fname": file_doc.file_name,
                    "fcontent": file_doc.get_content()
                })
            except Exception as e:
                frappe.log_error(f"Failed to attach PDF to email for {offer.name}: {str(e)}")

        frappe.sendmail(
            recipients=[applicant_email],
            subject=subject,
            message=message,
            attachments=attachments
        )

    @staticmethod
    def _create_snapshot_record(offer_name, fee_data):
        """Creates the Offer Fee Snapshot record with full component breakdown."""
        snapshot = frappe.new_doc("Offer Fee Snapshot")
        snapshot.offer_id = offer_name
        snapshot.scholarship_amount = fee_data.get("scholarship_amount")
        snapshot.total_payable = fee_data.get("total_payable")
        snapshot.frozen_on = now_datetime()
        snapshot.frozen_by = frappe.session.user
        
        # Populate components child table
        if fee_data.get("components"):
            for comp in fee_data.get("components"):
                snapshot.append("fee_component", comp)
                
        snapshot.insert(ignore_permissions=True)

    @staticmethod
    def _get_template_context(offer):
        """Helper to build rich context for Jinja templates."""
        # Inject virtual fields for template compatibility
        offer.offer_id = offer.name
        offer.valid_till = offer.payment_deadline

        context = {
            "doc": offer,
            "frappe": frappe
        }
        
        if offer.applicant:
            applicant_doc = frappe.get_doc("Applicant", offer.applicant)
            context["applicant_doc"] = applicant_doc
            # Map 'applicant' to the candidate name as per requirement
            name = applicant_doc.candidate_name or applicant_doc.name
            context["applicant"] = name
            context["applicant_name"] = name
            
        if offer.program:
            context["program"] = frappe.get_doc("Program", offer.program)
            
        if offer.campus:
            context["campus"] = frappe.get_doc("Campus", offer.campus)
            
        if offer.admission_cycle:
            context["admission_cycle"] = frappe.get_doc("Admission Cycle", offer.admission_cycle)
            
        return context

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
        context = OfferService._get_template_context(offer_doc)
        
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
            
            # Set the attachment field on the object so it gets saved in the final .save() call
            offer_doc.offer_letter_pdf = _file.file_url
            
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



@frappe.whitelist()
def extended_fee_deadline():
	return OfferService.extended_fee_deadline()

@frappe.whitelist(allow_guest=True)
def generate_offer(applicant, campus, program, cycle, admission_year=None):
    return OfferService.generate_offer(applicant, campus, program, cycle, admission_year)

@frappe.whitelist()
def bulk_generate_offers(applicants):
    return OfferService.bulk_generate_offers(applicants)

@frappe.whitelist()
def bulk_update_status(offer_names, action, notes=None):
    return OfferService.bulk_update_status(offer_names, action, notes)

@frappe.whitelist()
def accept_offer(offer_name):
    return OfferService.accept_offer(offer_name)

@frappe.whitelist()
def reject_offer(offer_name, reason=None):
    return OfferService.reject_offer(offer_name, reason)

@frappe.whitelist()
def expire_offers():
    return OfferService.expire_offers()