import frappe
import json
from frappe import _, throw
from frappe.utils import add_days, getdate, now_datetime, get_datetime, flt
from frappe.utils.pdf import get_pdf
from slcm.api.service.fee_service import FeeService

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
            
            # Fallback: Try matching admission_year against the Configuration's academic_year field
            if not config_name:
                alt_filters = filters.copy()
                alt_filters["academic_year"] = alt_filters.pop("admission_year")
                config_name = frappe.db.get_value("Offer Configuration", alt_filters)

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
        # Helper to find by configuration bridge
        def _resolve_from_config(year_val):
            # Check if this value is linked to any active configuration as either admission or academic year
            config_match = frappe.db.get_value("Offer Configuration", {
                "academic_year": year_val,
                "is_active": 1
            }, "admission_year") or frappe.db.get_value("Offer Configuration", {
                "admission_year": year_val,
                "is_active": 1
            }, "admission_year")
            return config_match

        # 1. If admission_year is provided, check if it exists as a record name
        if admission_year:
            if not frappe.db.exists("Admission Year", admission_year):
                # Probably an Academic Year name (e.g. 2026-2027), find valid Admission Year for it
                # via explicit year field
                resolved = frappe.db.get_value("Admission Year", 
                    {"year": admission_year, "is_active": 1}, "name")
                
                # If still not found, use Offer Configuration as a bridge (common case)
                if not resolved:
                    resolved = _resolve_from_config(admission_year)
                
                if resolved:
                    return resolved
            return admission_year

        # 2. Try to get from Applicant (most specific)
        admission_year = frappe.db.get_value("Applicant", 
            {"name": applicant, "campus": campus, "admission_cycle": cycle}, 
            "admission_year")
        if admission_year:
            return admission_year

        # 3. Try to map from Applicant's Academic Year (most common fallback)
        academic_year = frappe.db.get_value("Applicant", applicant, "academic_year")
        if academic_year:
            # Try to resolve directly via year field
            admission_year = frappe.db.get_value("Admission Year", 
                {"year": academic_year, "is_active": 1}, "name")
            
            # If still not found, use Offer Configuration bridge
            if not admission_year:
                admission_year = _resolve_from_config(academic_year)
            
        return admission_year

    @staticmethod
    @frappe.whitelist(allow_guest=True)
    def generate_offer(applicant, campus, program, cycle, admission_year=None):
        """
        Main entry point for generating an offer letter.
        Ensures idempotency and follows financial snapshotting rules.
        """
        if not applicant:
            throw(_("Applicant is required to generate an offer letter."))
        if not campus:
            throw(_("Campus is required to generate an offer letter."))

        # Resolve the actual Admission Year DocType entry
        admission_year = OfferService.resolve_admission_year(applicant, campus, cycle, admission_year)

        if not admission_year:
            throw(_("No active Admission Year found for applicant {0}. Please ensure an Admission Year is configured and active for their Academic Year.").format(applicant))

        config = OfferService.get_active_config(admission_year, cycle, campus)
        resolved_cycle = config.admission_cycle

        # --- PRE-FLIGHT CHECKS (Before Transaction) ---
        if getattr(config, "send_email", 0):
            if not config.email_template:
                throw(_("Email Template is missing in Offer Configuration {0}").format(config.name))
            
            applicant_email = frappe.db.get_value("Applicant", applicant, "email")
            if not applicant_email:
                throw(_("Applicant {0} does not have a valid email address. Cannot send offer letter.").format(applicant))
        
        if getattr(config, "generate_offer_letter_by_system", 0) and not config.pdf_format:
            throw(_("PDF Print Format is missing in Offer Configuration {0}").format(config.name))


        # Status verification: Only 'Selected' applicants in published Seat Allocations can receive offers
        sa_filters = {
            "applicant": applicant,
            "program": program,
            "selection_status": "Selected",
            "parenttype": "Seat Allocation"
        }
        status_check = frappe.db.get_value("Seat Selection Applicant", sa_filters, ["parent"], as_dict=1)
        
        if not status_check:
             # Try by applicant_id as fallback
             sa_filters["applicant_id"] = sa_filters.pop("applicant")
             status_check = frappe.db.get_value("Seat Selection Applicant", sa_filters, ["parent"], as_dict=1)

        if not status_check:
             # Check if an offer was ALREADY issued (in which case they would be 'Offer Issued')
             already_issued = frappe.db.exists("Offer Letter", {
                "applicant": applicant,
                "program": program,
                "offer_status": ["not in", ["Rejected", "Expired", "Withdrawn"]]
             })
             if not already_issued:
                throw(_("Applicant {0} is not in 'Selected' status for Program {1} in any Seat Allocation. Offer letter cannot be generated.").format(applicant, program))
        else:
            # Check if parent Seat Allocation is Published
            if frappe.db.get_value("Seat Allocation", status_check.parent, "status") != "Published":
                 throw(_("Seat Allocation for Applicant {0} is not yet 'Published'. Please publish the allocation first.").format(applicant))

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
            throw(_("An active offer already exists for Applicant {0} in Cycle {1} for Campus {2} and Program {3}. (Offer: {4})").format(
                applicant, resolved_cycle, campus, program, existing
            ))

        # Start Transaction
        frappe.db.begin()
        
        try:
            offer = frappe.new_doc("Offer Letter")
            offer.applicant = applicant
            offer.campus = campus
            offer.program = program
            offer.admission_year = admission_year
            offer.admission_cycle = resolved_cycle
            offer.offer_id = f"OFF-{applicant}" # Safe temporary ID for templates
            offer.offer_configrationn = config.name
            offer.offer_status = "Draft"
            offer.issued_on = now_datetime()
            
            # Handle possible name duplication if a rejected offer exists with the same ID
            potential_name = f"OL-{applicant}-{program}-{campus}"
            if frappe.db.exists("Offer Letter", potential_name):
                # If it already exists, use standard naming series to avoid SQL Collision
                offer.naming_series = "OL-RE-."
                offer.autoname() # Force standard naming

        
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
            offer.payment_deadline = FeeService._calculate_deadline(fee_structure_name)
            
            # Freeze Fees from Fee Structure
            fee_data = FeeService._calculate_and_freeze_fees(fee_structure_name)
            offer.payable_amount = fee_data.get("total_payable")
            
            # Ensure Fetch From doesn't overwrite our resolved campus and cycle 
            # if they differ from the applicant's default preferences
            offer.insert(ignore_permissions=True)
            if campus:
                offer.campus = campus
                offer.db_set('campus', campus)
            if resolved_cycle:
                offer.admission_cycle = resolved_cycle
                offer.db_set('admission_cycle', resolved_cycle)
                
            OfferService.update_applicant_status(applicant, application_status="Offer Issued")

            # Snapshot Content (Now we have the name/ID)
            offer.rendered_content = OfferService._render_snapshot(offer, config.email_template)
            offer.db_set('rendered_content', offer.rendered_content)
            
            # Create the actual snapshot record
            OfferService._create_snapshot_record(offer.name, fee_data)

            # Generate and Attach PDF
            if getattr(config, "generate_offer_letter_by_system", 0):
                if config.pdf_format:
                    OfferService._generate_offer_pdf(offer, config.pdf_format)
            else:
                if getattr(config, "offer_letter_pdf", None):
                    OfferService._attach_static_pdf(offer, config.offer_letter_pdf)
            
            # Send offer letter email to applicant
            if getattr(config, "send_email", 0):
                from_account = getattr(config, "from_email_account", None)
                OfferService._send_offer_letter_email(offer, config.email_template, from_account)
            
            offer.offer_status = "Issued"
            offer.save(ignore_permissions=True)
            OfferService.sync_seat_allocation_status(offer, "Offer Issued")

            frappe.db.commit()
            return {
                "offer_name": offer.name,
                "offer_status": offer.offer_status,
                "message": _("Offer letter generated successfully")
            }
        except Exception as e:
            frappe.db.rollback()
            # If it's a known Frappe exception, keep the message clean
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

        OfferService.create_fee_assignment_from_offer(offer)
        return True

    @staticmethod
    def reject_applicant_other_offer(applicant , reason):
        if not applicant:
            throw(_("Applicant is required"))
        applicant_other_offers = frappe.get_all("Offer Letter", filters={
            "applicant": applicant,
            "offer_status": ["not in", ["Rejected", "Expired", "Withdrawn", "Accepted"]],
            "name": ["!=", frappe.flags.current_offer or ""]
        }, fields=["name"])
        for offer in applicant_other_offers:
            OfferService.reject_offer(offer.name, reason)
        return True

    @staticmethod
    def update_applicant_status(applicant, application_status):
        if not applicant:
            throw(_("Applicant is required"))
        
        # Use db_set to bypass full validation (validate_eligibility) which may throw 
        # for ineligible applicants during status synchronization.
        frappe.db.set_value("Applicant", applicant, "application_status", application_status, update_modified=True)
        
        # Ensure 'current_stage' is updated if needed (safety fallback)
        if application_status == "Offer Accepted":
            frappe.db.set_value("Applicant", applicant, "current_stage", "Admission Confirmed")
            
        return True

    @staticmethod
    def process_fee_payment(offer_name, payment_mode="Cash", reference_number=None):
        return FeeService.process_fee_payment(offer_name, payment_mode, reference_number)
    
    @staticmethod
    def reject_offer(offer_name, reason=None):
        """
        Handles student/admin rejection of an offer.
        """
        offer = frappe.get_doc("Offer Letter", offer_name)
        
        if offer.offer_status not in ["Issued", "Draft"]:
            throw(_("Cannot reject offer in status: {0}").format(offer.offer_status))

        offer.offer_status = "Rejected"
        if reason:
            offer.edit_reason = reason # Passed to the log via model hook
        offer.save(ignore_permissions=True)
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
                # We save each individually to trigger the automated status hook
                doc = frappe.get_doc("Offer Letter", entry.name)
                doc.offer_status = "Expired"
                doc.edit_reason = _("Automatically expired by system scheduler.")
                doc.save(ignore_permissions=True)
                processed += 1
            except Exception:
                frappe.log_error(frappe.get_traceback(), _("Manual Offer Expiry Failed"))
        
        return processed

    @staticmethod
    @frappe.whitelist()
    def bulk_generate_offers(applicants):
        """
        Entry point for bulk generation.
        Small batches (< 10) are processed immediately.
        Large batches are sent to background workers.
        """
        if isinstance(applicants, str):
            applicants = json.loads(applicants)

        if not applicants:
            return {"message": "No applicants provided"}

        # Threshold for background processing
        if len(applicants) > 10:
            frappe.enqueue(
                method="slcm.api.service.offer_service.OfferService.background_bulk_worker",
                queue="long",
                applicants=applicants,
                user=frappe.session.user,
                now=frappe.flags.in_test
            )
            return {
                "queued": True,
                "message": _("Large batch detected ({0} applicants). Processing started in the background. You will receive a notification when finished.").format(len(applicants))
            }

        # Otherwise, process immediately (standard behavior)
        return OfferService._process_bulk_batch(applicants)

    @staticmethod
    def _process_bulk_batch(applicants):
        """Internal helper to process a batch and return summary."""
        results = {"success": [], "errors": []}
        for data in applicants:
            try:
                # payload resolution logic...
                if isinstance(data, dict) and "applicant" in data:
                    payload = data
                elif isinstance(data, str):
                    # Handle case where only applicant name is passed
                    applicant_name = data
                    # Fetch basic details from Applicant record as fallback
                    details = frappe.db.get_value("Applicant", applicant_name, 
                        ["campus", "program", "admission_cycle", "admission_year"], as_dict=1)
                    
                    if not details:
                        raise ValueError(_("Applicant {0} not found").format(applicant_name))
                    
                    details = frappe._dict(details)

                    # Try to find the Seat Allocation context
                    # Search for a row where this applicant is 'Selected' or 'Accepted'
                    sa_child_filters = {
                        "parenttype": "Seat Allocation",
                        "selection_status": ["in", ["Selected", "Accepted"]]
                    }
                    # Always search by applicant (which is now the Applicant ID)
                    sa_child_filters["applicant"] = applicant_name

                    sa_child_data = frappe.db.get_value(
                        "Seat Selection Applicant",
                        sa_child_filters,
                        ["parent", "program"],
                        as_dict=1
                    )

                    if sa_child_data:
                        parent_sa = frappe.db.get_value("Seat Allocation", sa_child_data.parent, 
                            ["campus", "admission_cycle"], as_dict=1)
                        if parent_sa:
                            # Prioritize Seat Allocation data
                            campus = parent_sa.campus
                            cycle = parent_sa.admission_cycle
                            program = sa_child_data.program
                        else:
                            campus = details.campus
                            cycle = details.admission_cycle
                            program = details.program
                    else:
                        campus = details.campus
                        cycle = details.admission_cycle
                        program = details.program

                    if not campus:
                        raise ValueError(_("Campus could not be determined for Applicant {0}.").format(applicant_name))
                    if not cycle:
                        raise ValueError(_("Admission Cycle could not be determined for Applicant {0}.").format(applicant_name))
                    if not program:
                        raise ValueError(_("Program could not be determined for Applicant {0}.").format(applicant_name))

                    payload = {
                        "applicant": applicant_name,
                        "campus": campus,
                        "program": program,
                        "cycle": cycle,
                        "admission_year": details.admission_year
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
                results["success"].append({
                    "applicant": payload.get("applicant"), 
                    "offer": name.get("offer_name") if isinstance(name, dict) else name
                })
            except Exception as e:
                frappe.db.rollback()
                error_msg = str(e) or "Unknown Server Error"
                results["errors"].append({"applicant": str(data.get("applicant") if isinstance(data, dict) else data), "error": error_msg})
                frappe.log_error(f"Bulk Offer Generation Error for {str(data)}: {error_msg}", "Offer Service")

    @staticmethod
    def background_bulk_worker(applicants, user):
        """Background task for high-volume generation."""
        # Switch session user to the requester
        frappe.set_user(user)

        results = OfferService._process_bulk_batch(applicants)

        # Create a System Notification upon completion
        success_count = len(results["success"])
        error_count = len(results["errors"])
        
        summary_msg = _("Successfully generated {0} offers.").format(success_count)
        if error_count > 0:
            summary_msg += _(" {0} errors encountered.").format(error_count)

        notification_content = f"""
            <h4>{_('Bulk Offer Generation Finished')}</h4>
            <p>{summary_msg}</p>
            <hr>
            <p><small>{_('Check the Offer Letter list for details.')}</small></p>
        """

        # Dispatch standard Frappe notification
        from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
        enqueue_create_notification(
            [user],
            {
                "subject": _("Bulk Offer Generation Report"),
                "email_content": notification_content,
                "type": "Alert",
                "document_type": "Offer Letter"
            }
        )

        # Also publish real-time alert if user is still logged in
        frappe.publish_realtime(
            "msgprint", 
            {
                "message": summary_msg, 
                "title": _("Background Process Completed"),
                "indicator": "green" if error_count == 0 else "orange"
            }, 
            user=user
        )
        
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
        return FeeService._calculate_deadline(fee_structure_name)

    @staticmethod
    def extended_fee_deadline(fee_structure_name):
        return FeeService.extended_fee_deadline(fee_structure_name)

    
    @staticmethod
    def _calculate_and_freeze_fees(fee_structure_name):
        return FeeService._calculate_and_freeze_fees(fee_structure_name)

    @staticmethod
    def _send_offer_letter_email(offer, email_template, from_email_account=None):
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

        sender = None
        if from_email_account:
            sender = frappe.db.get_value("Email Account", from_email_account, "email_id")

        frappe.sendmail(
            sender=sender,
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
        offer.offer_id = offer.name or _("Draft")
        offer.valid_till = offer.payment_deadline

        # Default values to prevent Jinja UndefinedError
        context = {
            "doc": offer,
            "frappe": frappe,
            "applicant": None,
            "applicant_name": None,
            "applicant_doc": frappe._dict(),
            "program": frappe._dict(),
            "campus": frappe._dict(),
            "admission_cycle": frappe._dict()
        }
        
        if offer.applicant:
            try:
                applicant_doc = frappe.get_doc("Applicant", offer.applicant)
                context["applicant_doc"] = applicant_doc
                name = applicant_doc.candidate_name or applicant_doc.name
                context["applicant"] = name
                context["applicant_name"] = name
            except Exception:
                pass
            
        if offer.program:
            try:
                context["program"] = frappe.get_doc("Program", offer.program)
            except Exception:
                pass
            
        if offer.campus:
            try:
                context["campus"] = frappe.get_doc("Campus", offer.campus)
            except Exception:
                pass
            
        if offer.admission_cycle:
            try:
                context["admission_cycle"] = frappe.get_doc("Admission Cycle", offer.admission_cycle)
            except Exception:
                pass
            
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
    def _attach_static_pdf(offer_doc, file_url):
        """Attaches a static PDF from configuration to the Offer Letter record."""
        try:
            if not file_url:
                return

            offer_doc.offer_letter_pdf = file_url
            
            # Find the original file record to copy metadata
            original_files = frappe.get_all("File", filters={"file_url": file_url}, limit=1)
            if original_files:
                original_doc = frappe.get_doc("File", original_files[0].name)
                
                # Create a new File record linked to this Offer Letter
                # This ensures it shows in the sidebar and _send_offer_letter_email can find it
                _file = frappe.new_doc("File")
                _file.file_name = original_doc.file_name
                _file.file_url = original_doc.file_url
                _file.attached_to_doctype = "Offer Letter"
                _file.attached_to_name = offer_doc.name
                _file.attached_to_field = "offer_letter_pdf"
                _file.is_private = original_doc.is_private
                _file.insert(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(f"Static PDF Attachment Failed for {offer_doc.name}: {str(e)}")

    @staticmethod
    def log_action(offer_name, action, notes=None, reason=None):
        """Utility to log every transition in the lifecycle."""
        log = frappe.new_doc("Offer Action Log")
        log.offer_letter = offer_name
        log.action = action
        log.performed_by = frappe.session.user  
        log.timestamp = now_datetime()
        log.notes = notes
        log.reason = reason
        log.insert(ignore_permissions=True)

    @staticmethod
    def sync_seat_allocation_status(offer, status):
        """
        Synchronizes offer status back to the Seat Allocation child table.
        Uses Document API to trigger audit logs and waitlist promotions.
        """
        if not offer or not status:
            return

        # Find the specific Seat Allocation parent
        seat_allocation_name = frappe.db.get_value(
            "Seat Selection Applicant",
            {
                "applicant_id": offer.applicant,
                "program": offer.program,
                "parenttype": "Seat Allocation"
            },
            "parent"
        )

        if not seat_allocation_name:
            return

        try:
            alloc_doc = frappe.get_doc("Seat Allocation", seat_allocation_name)
            
            # Security check: Ensure campus and cycle match (handles multi-program/multi-campus edge cases)
            if alloc_doc.campus != offer.campus or alloc_doc.admission_cycle != offer.admission_cycle:
                # Find matching allocation if the first one wasn't correct
                match = frappe.db.sql("""
                    SELECT parent FROM `tabSeat Selection Applicant`
                    WHERE applicant_id = %s AND program = %s AND parenttype = 'Seat Allocation'
                    AND parent IN (SELECT name FROM `tabSeat Allocation` WHERE campus = %s AND admission_cycle = %s)
                """, (offer.applicant, offer.program, offer.campus, offer.admission_cycle))
                if match:
                    alloc_doc = frappe.get_doc("Seat Allocation", match[0][0])
                else:
                    return

            updated = False
            for row in alloc_doc.selection_applicant:
                if row.applicant_id == offer.applicant and row.program == offer.program:
                    row.selection_status = status
                    updated = True
                    break
            
            if updated:
                # Saving triggers before_save/on_update which handles Waitlist Promotion
                alloc_doc.save(ignore_permissions=True)
                frappe.db.commit()
                
        except Exception as e:
            frappe.log_error(f"Sync Seat Allocation Status Failed for {offer.name}: {str(e)}", "Offer Service")

    @staticmethod
    def create_fee_assignment_from_offer(offer):
        return FeeService.create_fee_assignment_from_offer(offer)

    @staticmethod
    def get_online_payment_url(offer_name, gateway=None):
        return FeeService.get_online_payment_url(offer_name, gateway)

    @staticmethod
    def create_offer_razorpay_order(offer_name):
        return FeeService.create_offer_razorpay_order(offer_name)

    @staticmethod
    def verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name):
        return FeeService.verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name)

    @staticmethod
    @frappe.whitelist()
    def get_pending_offers_list():
        """
        Fetches all Offers with 'Issued' status that haven't passed their deadline.
        """
        offers = frappe.db.sql("""
            SELECT 
                ol.name,
                app.candidate_name as applicant_name,
                ol.program,
                ol.payment_deadline
            FROM `tabOffer Letter` ol
            JOIN `tabApplicant` app ON ol.applicant = app.name
            WHERE ol.offer_status = 'Issued'
              AND (ol.payment_deadline >= CURDATE() OR ol.payment_deadline IS NULL)
            ORDER BY ol.payment_deadline ASC
        """, as_dict=1)
        return offers

    @staticmethod
    @frappe.whitelist()
    def send_bulk_reminders(offer_names=None, message=None, send_email=True, send_notification=True, sender_email=None):
        """
        Sends emails and system notifications for selected pending offers.
        """
        from frappe.utils import cint
        
        # Cast to bool in case strings like "1" or "0" are passed from client
        send_email = bool(cint(send_email))
        send_notification = bool(cint(send_notification))

        if not offer_names:
            frappe.throw(_("Please select at least one offer to send reminders."))

        if isinstance(offer_names, str):
            try:
                offer_names = frappe.parse_json(offer_names)
            except:
                offer_names = [o.strip() for o in offer_names.split(',')]
            
        if not isinstance(offer_names, list):
            offer_names = [offer_names]

        if not message:
            frappe.throw(_("Message content is required for reminders."))

        success_count = 0
        for offer_name in offer_names:
            if not frappe.db.exists("Offer Letter", offer_name):
                continue
                
            offer = frappe.get_doc("Offer Letter", offer_name)
            
            # Context-aware message formatting
            final_message = message
            if "[Program]" in final_message:
                final_message = final_message.replace("[Program]", offer.program or "")
            if "[Deadline]" in final_message:
                deadline_str = str(offer.payment_deadline) if offer.payment_deadline else "N/A"
                final_message = final_message.replace("[Deadline]", deadline_str)
            
            # Email Delivery
            if send_email and offer.applicant:
                applicant_email = frappe.db.get_value("Applicant", offer.applicant, "email")
                if applicant_email:
                    frappe.sendmail(
                        recipients=[applicant_email],
                        subject=_("Admission Reminder: Pending Offer Letter for {0}").format(offer.program),
                        message=final_message,
                        reference_doctype="Offer Letter",
                        reference_name=offer.name,
                        sender=sender_email
                    )
                    frappe.logger().info(f"Offer Reminder Email sent to {applicant_email} for {offer_name}")
                else:
                    frappe.logger().warning(f"Skipped Email Reminder for {offer_name}: Applicant has no email.")
            
            # System Notification Delivery
            if send_notification:
                receiver = offer.notification_receiver
                
                # Fallback: Try to find user from applicant email if receiver is not set
                if not receiver and offer.applicant:
                    email = frappe.db.get_value("Applicant", offer.applicant, "email")
                    if email:
                        receiver = frappe.db.get_value("User", {"email": email}, "name")
                
                if receiver:
                    frappe.get_doc({
                        "doctype": "Notification Log",
                        "subject": _("Reminder: Offer Letter for {0} is pending").format(offer.program),
                        "email_content": final_message,
                        "for_user": receiver,
                        "document_type": "Offer Letter",
                        "document_name": offer.name
                    }).insert(ignore_permissions=True)
                    frappe.logger().info(f"Offer Reminder Notification sent to {receiver} for {offer_name}")
                else:
                    frappe.logger().warning(f"Skipped System Notification for {offer_name}: No corresponding User found.")
            
            success_count += 1
                
        return {
            "status": "success",
            "message": _("Processed {0} reminders successfully.").format(success_count)
        }




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
    # Set a flag so reject_applicant_other_offer knows which offer was just accepted
    frappe.flags.current_offer = offer_name
    return OfferService.accept_offer(offer_name)

@frappe.whitelist()
def reject_applicant_other_offer(applicant, reason):
    return OfferService.reject_applicant_other_offer(applicant, reason)

@frappe.whitelist()
def process_fee_payment(offer_name, payment_mode="Cash", reference_number=None):
    from slcm.api.service.fee_service import FeeService
    return FeeService.process_fee_payment(offer_name, payment_mode, reference_number)

@frappe.whitelist()
def reject_offer(offer_name, reason=None):
    return OfferService.reject_offer(offer_name, reason)

@frappe.whitelist()
def expire_offers():
    return OfferService.expire_offers()

@frappe.whitelist()
def get_online_payment_url(offer_name, gateway=None):
    return OfferService.get_online_payment_url(offer_name, gateway)

@frappe.whitelist()
def create_offer_razorpay_order(offer_name):
    from slcm.api.service.fee_service import FeeService
    return FeeService.create_offer_razorpay_order(offer_name)

@frappe.whitelist()
def verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name):
    from slcm.api.service.fee_service import FeeService
    return FeeService.verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name)

@frappe.whitelist()
def get_pending_offers_list():
    return OfferService.get_pending_offers_list()

@frappe.whitelist()
def send_bulk_reminders(offer_names=None, message=None, send_email=True, send_notification=True, sender_email=None):
    return OfferService.send_bulk_reminders(offer_names, message, send_email, send_notification, sender_email)

def expire_offers():
    return OfferService.expire_offers()
