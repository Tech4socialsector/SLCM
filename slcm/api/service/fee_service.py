import frappe
import json
from frappe import _, throw
from frappe.utils import add_days, getdate, now_datetime, get_datetime, flt

from slcm.api.service.application_fee_service import get_payment_receipt_template_for_policy

class FeeService:
    """
    Fee and Payment Service Layer.
    Handles fee calculation, fee assignments, and payment gateway integration.
    """

    @staticmethod
    def _calculate_deadline(fee_structure_name):
        """Determines payment deadline based on Fee Structure."""
        if not fee_structure_name:
            return None
            
        valid_until = frappe.db.get_value("Fee Structure", fee_structure_name, "valid_until")
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
        
        offers = frappe.get_all("Offer Letter", filters={
            "fee_structure": fee_structure_name,
            "offer_status": ["in", ["Draft", "Issued"]]
        }, fields=["name"])
        
        for entry in offers:
            doc = frappe.get_doc("Offer Letter", entry.name)
            if doc.payment_deadline != new_deadline:
                doc.payment_deadline = new_deadline
                doc.ignore_lock = True
                doc.edit_reason = _("Bulk extension due to Fee Structure ({0}) update.").format(fee_structure_name)
                doc.add_comment("Comment", _("Payment deadline automatically syncronized to {0} due to Fee Structure update.").format(
                    frappe.utils.format_datetime(new_deadline)
                ))
                doc.save(ignore_permissions=True)

    @staticmethod
    def _calculate_and_freeze_fees(fee_structure_name):
        """
        Financial Logic: Calculates fees and returns a structured dict.
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
            "scholarship_amount": 0,
            "tax_amount": tax_amount,
            "total_payable": fs_doc.total_amount,
            "breakdown": breakdown,
            "components": components,
            "payment_gateway": fs_doc.payment_gateway,
            "online_payment": fs_doc.online_payment
        }

    @staticmethod
    def create_fee_assignment_from_offer(offer):
        """
        Creates an Applicant Fee Assignment record from an accepted offer letter.
        - Copies only the actual fee component rows (no scholarship link row).
        - Fetches total approved scholarship from Scholarship Application
          and stores it in scholarship_amount field directly.
        """
        if frappe.db.exists("Applicant Fee Assignment", {"offer_letter": offer.name, "status": ["!=", "Cancelled"]}):
            return

        snapshot_name = frappe.db.get_value("Offer Fee Snapshot", {"offer_id": offer.name})
        if not snapshot_name:
            # Fallback: Try to recreate snapshot from current Fee Structure if missing
            # This handles offers generated before snapshotting was introduced or failed snapshots.
            if offer.fee_structure:
                from slcm.api.service.offer_service import OfferService
                fee_data = FeeService._calculate_and_freeze_fees(offer.fee_structure)
                OfferService._create_snapshot_record(offer.name, fee_data)
                snapshot_name = frappe.db.get_value("Offer Fee Snapshot", {"offer_id": offer.name})
            
            if not snapshot_name:
                throw(_("Fee Snapshot not found for Offer {0}. Cannot create Fee Assignment.").format(offer.name))

        snapshot = frappe.get_doc("Offer Fee Snapshot", snapshot_name)

        admission_cycle = offer.admission_cycle or frappe.db.get_value("Applicant", offer.applicant, "admission_cycle")

        # Fetch total approved scholarship for this applicant + cycle directly
        total_scholarship = frappe.db.sql("""
            SELECT SUM(calculated_benefit)
            FROM `tabScholarship Application`
            WHERE applicant_id = %s AND admission_cycle = %s AND status = 'Approved'
        """, (offer.applicant, admission_cycle))[0][0] or 0
        total_scholarship = flt(total_scholarship)

        assignment = frappe.new_doc("Applicant Fee Assignment")
        assignment.applicant = offer.applicant
        assignment.offer_letter = offer.name
        assignment.program = offer.program
        assignment.academic_year = offer.academic_year or frappe.db.get_value("Applicant", offer.applicant, "academic_year")
        assignment.admission_cycle = admission_cycle
        assignment.assignment_date = frappe.utils.today()

        # Copy fee rows — skip any legacy "Scholarship" link row from snapshot
        for row in snapshot.fee_component:
            if (row.fee_component or "").lower() == "scholarship":
                continue
            assignment.append("fee_components", {
                "fee_component": row.fee_component,
                "component_name": row.component_name,
                "amount": row.amount,
                "is_taxable": row.is_taxable,
                "tax_rate": row.tax_rate,
                "tax_amount": row.tax_amount,
                "total_amount": row.total_amount
            })

        # Store scholarship in the dedicated field (no Fee Component record needed)
        assignment.scholarship_amount = total_scholarship
        assignment.scholarship_applied = 1 if total_scholarship > 0 else 0

        assignment.insert(ignore_permissions=True)
        assignment.submit()

        return assignment.name

    @staticmethod
    def process_fee_payment(offer_name, payment_mode="Cash", reference_number=None, 
                           bank_name=None, cheque_number=None, cheque_date=None, 
                           upi_id=None, remarks=None):
        """
        Processes the fee payment for an accepted offer.
        """
        offer_doc = frappe.get_doc("Offer Letter", offer_name)
        
        # Security: Prevent duplicate payments
        if offer_doc.offer_status == "Payment Completed":
            throw(_("Payment has already been recorded for this offer ({0}).").format(offer_name))

        assignment_name = frappe.db.get_value("Applicant Fee Assignment", 
            {"offer_letter": offer_name, "status": ["!=", "Cancelled"]}, "name")
        
        if not assignment_name:
            if offer_doc.offer_status != "Accepted":
                throw(_("Offer must be 'Accepted' before paying fees."))
            assignment_name = FeeService.create_fee_assignment_from_offer(offer_doc)
        
        if not assignment_name:
            throw(_("Fee Assignment not found for offer {0}").format(offer_name))

        assignment = frappe.get_doc("Applicant Fee Assignment", assignment_name)
        assignment.db_set("status", "Paid")
        
        # Update Offer Letter status directly
        offer_doc.offer_status = "Payment Completed"
        offer_doc.db_set("offer_status", "Payment Completed")

        # Sync Payment Request if it exists
        # For manual payments, we check if "Manual Payment" gateway exists, otherwise use a generic label
        gateway = "Manual Payment" if payment_mode != "Online" else (frappe.db.get_value("Fee Structure", offer_doc.fee_structure, "payment_gateway") or "Online")
        
        if gateway == "Manual Payment" and not frappe.db.exists("Payment Gateway", "Manual Payment"):
            gateway = None # Don't set non-existent link
            
        FeeService._update_payment_request(offer_doc, gateway, reference_number or "N/A", "Paid", payment_id=reference_number)

        from slcm.api.service.offer_service import OfferService
        OfferService.update_applicant_status(assignment.applicant, application_status="Fee Paid")
        OfferService.sync_seat_allocation_status(offer_doc, status="Fee Paid")
        OfferService.log_action(offer_name, "Fee Paid", _("Fee status updated to Paid via {0}").format(payment_mode))

        from slcm.admission.utils.notifications import log_communication
        log_communication(
            applicant=assignment.applicant,
            communication_type="Portal Notification",
            category="Fee",
            subject=_("Admission Fee Payment Completed"),
            content=_("Your payment of {0} for {1} has been received successfully.").format(
                frappe.format_value(offer_doc.payable_amount, offer_doc.meta.get_field("payable_amount"), offer_doc),
                offer_doc.program
            ),
            reference_doctype="Offer Letter",
            reference_name=offer_doc.name
        )

        # Generate Receipt
        return FeeService.generate_receipt(
            offer_doc, 
            reference_number or "N/A", 
            payment_mode,
            bank_name=bank_name,
            cheque_number=cheque_number,
            cheque_date=cheque_date,
            upi_id=upi_id,
            remarks=remarks
        )


    @staticmethod
    @frappe.whitelist()
    def create_offer_razorpay_order(offer_name):
        """
        Creates a Razorpay order directly and returns details for the frontend modal.
        """
        try:
            offer = frappe.get_doc("Offer Letter", offer_name)
            
            # Validation
            if not offer.payable_amount or flt(offer.payable_amount) <= 0:
                frappe.throw(_("Payable amount must be greater than zero."))
            
            if offer.offer_status == "Payment Completed":
                frappe.throw(_("Payment has already been completed."))

            # Block if a Payment Request for this offer is already Paid (gateway truth)
            existing_paid_pr = frappe.db.get_value(
                "Payment Request",
                {"reference_doctype": "Offer Letter", "reference_name": offer.name, "status": "Paid"},
                "name",
            )
            if existing_paid_pr:
                frappe.throw(_("Payment has already been completed for this offer. You cannot pay again."))

            # Block if Applicant Fee Assignment for this offer is already Paid or Converted
            afa_status = frappe.db.get_value(
                "Applicant Fee Assignment",
                {"offer_letter": offer.name, "docstatus": ["!=", 2]},
                "status",
            )
            if afa_status in ("Paid", "Converted"):
                frappe.throw(_("Fee for this offer has already been paid or the applicant has been converted. You cannot pay again."))
            
            if offer.offer_status in ["Rejected", "Expired", "Withdrawn"]:
                frappe.throw(_("Cannot initiate payment. The offer is currently {0}.").format(offer.offer_status))
            
            if offer.offer_status in ["Draft", "Issued"]:
                frappe.throw(_("Please accept the offer before proceeding to fee payment."))

            # 2. Get Dynamic Gateway from Fee Structure
            gateway = frappe.db.get_value("Fee Structure", offer.fee_structure, "payment_gateway")
            if not gateway:
                # Fallback to system default if not set on Fee Structure
                gateway = frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"

            from payments.utils import get_payment_gateway_controller
            controller = get_payment_gateway_controller(gateway)
            
            # 3. Prepare Order Details
            # Use the scholarship-adjusted amount if applicable
            actual_payable = flt(offer.payable_amount)
            afa = frappe.db.get_value("Applicant Fee Assignment",
                {"offer_letter": offer.name, "docstatus": ["!=", 2]},
                ["final_payable_amount", "scholarship_applied", "scholarship_amount"],
                as_dict=True)
            if afa and afa.scholarship_applied and flt(afa.scholarship_amount) > 0:
                actual_payable = flt(afa.final_payable_amount)
            
            payment_details = {
                "amount": actual_payable,
                "title": _("Admission Fee"),
                "description": _("Admission Fee for {0}").format(offer.program),
                "reference_doctype": "Offer Letter",
                "reference_docname": offer.name,
                "payer_email": frappe.db.get_value("Applicant", offer.applicant, "email"),
                "payer_name": frappe.db.get_value("Applicant", offer.applicant, "candidate_name"),
                "currency": frappe.defaults.get_global_default("currency") or "INR",
                # Razorpay receipt limit is 40 characters
                "receipt": (offer.name[:40]) if offer.name else None
            }
            
            # 4. Create Order via Controller
            order = controller.create_order(**payment_details)
            
            if not order or not order.get("id"):
                frappe.throw(_("Order creation failed. Please check gateway logs."))

            # Update Payment Request with Pending Status
            FeeService._update_payment_request(offer, gateway, order.get("id"), "Requested", response_data=order)

            return {
                "order_id": order.get("id"),
                "key_id": controller.api_key,
                "amount": order.get("amount"),
                "currency": order.get("currency"),
                "gateway": gateway
            }
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Offer Payment Order Creation Failed")
            raise

    @staticmethod
    @frappe.whitelist()
    def verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name):
        """
        Verifies the Razorpay signature and updates the offer status.
        """
        try:
            # Get common data
            offer = frappe.get_doc("Offer Letter", offer_name)
            gateway = frappe.db.get_value("Fee Structure", offer.fee_structure, "payment_gateway")
            if not gateway:
                gateway = frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"

            from payments.utils import get_payment_gateway_controller
            controller = get_payment_gateway_controller(gateway)
            
            # 1. Verify Signature
            body = razorpay_order_id + "|" + razorpay_payment_id
            api_secret = controller.get_password("api_secret")
            
            try:
                controller.verify_signature(body, razorpay_signature, api_secret)
                
                # Success Logic
                offer.on_payment_authorized("Completed")
                FeeService._update_payment_request(offer, gateway, razorpay_order_id, "Paid", razorpay_payment_id, 
                    response_data={"payment_id": razorpay_payment_id, "signature": razorpay_signature})
                
                # Generate Receipt
                FeeService.generate_receipt(offer, razorpay_payment_id, "Online")

                return {"status": "success"}

            except Exception as sig_err:
                FeeService._update_payment_request(offer, gateway, razorpay_order_id, "Failed", razorpay_payment_id, str(sig_err))
                raise sig_err

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Offer Payment Verification Failed")
            return {"status": "failed", "message": str(e)}

    @staticmethod
    def _resolve_payment_receipt_print_format(applicant_name, campus=None):
        """
        Print Format name from Program Reservation Policy (same rules as portal download_receipt).
        """
        if not applicant_name:
            return None
        try:
            app = frappe.get_doc("Applicant", applicant_name)
        except Exception:
            return None
        if not app.admission_cycle or not app.program:
            return None
        campus = campus or app.campus
        policy_name = None
        if campus:
            policy_name = frappe.db.get_value(
                "Admission Cycle Program",
                {
                    "parent": app.admission_cycle,
                    "program": app.program,
                    "campus": campus,
                    "is_active": 1,
                },
                "reservation_policy",
            )
        if not policy_name:
            policy_name = frappe.db.get_value(
                "Admission Cycle Program",
                {
                    "parent": app.admission_cycle,
                    "program": app.program,
                    "is_active": 1,
                },
                "reservation_policy",
            )
        if not policy_name:
            return None
        return frappe.db.get_value("Program Reservation Policy", policy_name, "payment_receipt_template")

    @staticmethod
    def generate_receipt(offer_doc, transaction_id, payment_mode, 
                        bank_name=None, cheque_number=None, cheque_date=None, 
                        upi_id=None, remarks=None):
        """
        Generates a Payment Receipt based on the current Offer and Fee Snapshot.
        """
        try:
            import json
            # 1. Fetch Snapshot for components
            snapshot = frappe.get_all("Offer Fee Snapshot", 
                filters={"offer_id": offer_doc.name}, 
                fields=["name", "total_payable"],
                order_by="creation desc", limit=1)
            
            if not snapshot:
                # Fallback to Fee Structure if no snapshot
                snapshot_data = frappe.get_doc("Fee Structure", offer_doc.fee_structure)
                total_payable = snapshot_data.total_amount if hasattr(snapshot_data, 'total_amount') else offer_doc.payable_amount
                components = snapshot_data.get("components") or []
            else:
                snapshot_doc = frappe.get_doc("Offer Fee Snapshot", snapshot[0].name)
                total_payable = snapshot_doc.total_payable
                components = list(snapshot_doc.fee_component or [])

            # 2. Create Receipt
            receipt = frappe.new_doc("Applicant Payment Receipt")
            receipt.applicant = offer_doc.applicant
            receipt.offer_letter = offer_doc.name
            receipt.program = offer_doc.program

            receipt.academic_year = offer_doc.academic_year
            receipt.campus = offer_doc.campus
            receipt.payment_date = frappe.utils.today()
            receipt.transaction_id = transaction_id
            receipt.payment_mode = payment_mode
            # Temporarily set; will recompute from components (including scholarship) below
            receipt.total_amount = total_payable
            receipt.currency = frappe.defaults.get_global_default("currency") or "INR"

            # Manual Details
            receipt.bank_name = bank_name
            receipt.cheque_number = cheque_number
            receipt.cheque_date = cheque_date
            receipt.upi_id = upi_id
            receipt.remarks = remarks
            
            # Link to existing Payment Request if possible
            pr = frappe.db.get_value("Payment Request", {"transaction_id": transaction_id}, "name")
            if pr:
                receipt.payment_reference = pr

            # 3. Copy Components
            from frappe.utils import flt as _flt
            
            # If scholarship is applied on the Applicant Fee Assignment
            try:
                afa = frappe.db.get_value(
                    "Applicant Fee Assignment",
                    {"offer_letter": offer_doc.name, "docstatus": ["!=", 2]},
                    ["scholarship_applied", "scholarship_amount"],
                    as_dict=True,
                )
            except Exception:
                afa = None

            # Append all components and then recompute the total from their amounts
            total_from_components = 0
            for comp in components:
                # Use total_amount if available, fallback to amount
                comp_total = _flt(getattr(comp, "total_amount", 0)) or _flt(getattr(comp, "amount", 0))
                total_from_components += comp_total

                receipt.append("fee_components", {
                    "fee_component": comp.fee_component,
                    "component_name": comp.component_name,
                    "amount": comp.amount,
                    "is_taxable": comp.is_taxable,
                    "tax_rate": comp.tax_rate,
                    "tax_amount": comp.tax_amount,
                    "total_amount": comp.total_amount
                })

            # Store scholarship in dedicated header fields (no Fee Component record needed)
            receipt.scholarship_applied = 0
            receipt.scholarship_amount = 0
            
            if afa and afa.scholarship_applied:
                receipt.scholarship_applied = 1
                receipt.scholarship_amount = _flt(afa.scholarship_amount)

            # Ensure health header amounts reflect the breakdown
            receipt.total_amount = total_from_components
            receipt.net_amount = receipt.total_amount - receipt.scholarship_amount

            tpl = FeeService._resolve_payment_receipt_print_format(
                offer_doc.applicant, getattr(offer_doc, "campus", None)
            )
            if tpl:
                receipt.payment_receipt_template = tpl

            receipt.insert(ignore_permissions=True)
            receipt.submit()
            
            from slcm.api.service.offer_service import OfferService
            OfferService.log_action(offer_doc.name, "Payment Received", 
                frappe._("Payment Receipt {0} generated for transaction {1}").format(receipt.name, transaction_id))
            
            return receipt.name
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Receipt Generation Failed")
            return None

    @staticmethod

    @frappe.whitelist()
    def log_payment_failure(offer_name, order_id, error_data):
        """
        Logs a payment failure reported by the frontend.
        """
        try:
            offer = frappe.get_doc("Offer Letter", offer_name)
            gateway = frappe.db.get_value("Fee Structure", offer.fee_structure, "payment_gateway")
            
            if isinstance(error_data, str):
                try:
                    error_data = json.loads(error_data)
                except:
                    pass
            
            error_message = ""
            if isinstance(error_data, dict):
                error_message = error_data.get("description") or error_data.get("message") or str(error_data)
            else:
                error_message = str(error_data)

            FeeService._update_payment_request(
                offer, 
                gateway, 
                order_id, 
                "Failed", 
                failure_reason=error_message,
                response_data=error_data
            )
            
            # Log in Offer Action Log as well
            from slcm.api.service.offer_service import OfferService
            OfferService.log_action(
                offer.name, 
                "Payment Failed", 
                notes=_("Payment attempt failed: {0}").format(error_message)
            )
            
            return {"status": "success"}
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Log Payment Failure Failed")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _update_payment_request(offer, gateway, transaction_id, status, payment_id=None, failure_reason=None, response_data=None):
        """
        Creates or updates a Payment Request doc to store gateway response.
        We find by order_id (transaction_id) to allow multiple attempts per offer.
        """
        # Try to find an existing payment request for this offer first
        pr_name = frappe.db.get_value("Payment Request", 
            {
                "reference_doctype": "Offer Letter", 
                "reference_name": offer.name,
                "status": ["!=", "Cancelled"]
            }, "name", order_by="creation desc")
        
        if not pr_name and transaction_id:
             # Fallback to finding by transaction id if specifically provided
             pr_name = frappe.db.get_value("Payment Request", 
                {"transaction_id": transaction_id}, "name")

        if pr_name:
            pr = frappe.get_doc("Payment Request", pr_name)
            # Update gateway if it's a manual override and it exists
            if gateway and frappe.db.exists("Payment Gateway", gateway):
                pr.db_set("payment_gateway", gateway)
        else:
            pr = frappe.new_doc("Payment Request")
            pr.reference_doctype = "Offer Letter"
            pr.reference_name = offer.name
            pr.amount = offer.payable_amount
            pr.currency = frappe.defaults.get_global_default("currency") or "INR"
            pr.email_to = frappe.db.get_value("Applicant", offer.applicant, "email")
            if gateway and frappe.db.exists("Payment Gateway", gateway):
                pr.payment_gateway = gateway
            pr.transaction_id = transaction_id

        # Gateway fields: razorpay_order_id and gateway_status for webhook and audit
        if transaction_id and status == "Requested":
            try:
                pr.razorpay_order_id = transaction_id
                pr.gateway_status = "created"
            except AttributeError:
                pass

        if pr.name and pr.docstatus > 0:
            # If doc is already submitted, we use db_set/set_value for direct DB update
            frappe.logger().debug(f"Updating submitted Payment Request {pr.name} to status {status}")
            frappe.flags.payment_request_status_from_backend = True

            update_data = {"status": status}
            if status == "Paid":
                update_data["failure_message"] = None
                update_data["gateway_status"] = "captured"
            elif failure_reason:
                update_data["status"] = "Failed"
                update_data["failure_message"] = failure_reason

            if payment_id:
                update_data["transaction_id"] = payment_id
                if status == "Paid":
                    update_data["razorpay_payment_id"] = payment_id
            if transaction_id and status == "Requested":
                update_data["razorpay_order_id"] = transaction_id
                update_data["gateway_status"] = "created"

            if response_data:
                update_data["gateway_response"] = json.dumps(response_data, indent=4)

            if gateway and frappe.db.exists("Payment Gateway", gateway):
                update_data["payment_gateway"] = gateway

            frappe.db.set_value("Payment Request", pr.name, update_data, update_modified=True)
            frappe.db.commit()
            if hasattr(frappe.flags, "payment_request_status_from_backend"):
                del frappe.flags.payment_request_status_from_backend
        else:
            # Draft or New
            pr.status = status
            if payment_id:
                pr.transaction_id = payment_id
            if transaction_id and status == "Requested":
                pr.razorpay_order_id = transaction_id
                pr.gateway_status = "created"

            if response_data:
                pr.gateway_response = json.dumps(response_data, indent=4)

            if status == "Paid":
                pr.failure_message = None
                pr.gateway_status = "captured"

            if failure_reason:
                pr.status = "Failed"
                pr.failure_message = failure_reason

            frappe.flags.payment_request_status_from_backend = True
            if pr.name:
                pr.save(ignore_permissions=True)
            else:
                pr.insert(ignore_permissions=True)

            if status in ["Paid", "Requested"]:
                pr.submit()
            if hasattr(frappe.flags, "payment_request_status_from_backend"):
                del frappe.flags.payment_request_status_from_backend





    @staticmethod
    def cancel_linked_fee_assignment(offer_name, reason=None):
        """
        Policy: If an offer is terminated (Rejected, Expired, Withdrawn), 
        any unpaid fee assignment must be cancelled to prevent 'ghost' revenue.
        """
        # Find any non-terminal Fee Assignment
        afa_list = frappe.get_all("Applicant Fee Assignment", 
            filters={
                "offer_letter": offer_name,
                "status": ["not in", ["Cancelled", "Paid", "Converted"]]
            }, fields=["name", "docstatus"])
        
        for entry in afa_list:
            try:
                doc = frappe.get_doc("Applicant Fee Assignment", entry.name)
                # If assigned (submitted), we must use cancel()
                if doc.docstatus == 1:
                    # The on_cancel method in AFA handles validation (preventing cancel if paid)
                    doc.cancel()
                else:
                    # Draft or other
                    doc.db_set("status", "Cancelled")
                
                frappe.logger().info(f"Auto-cancelled linked Fee Assignment {entry.name} for Offer {offer_name}")
            except Exception as e:
                # We don't want to block the offer status change, but we log the failure
                frappe.log_error(f"Failed to auto-cancel AFA {entry.name}: {str(e)}", "Fee Service")

    @staticmethod
    def _update_payment_request_for_applicant(applicant_doc, gateway, transaction_id, status,
            payment_id=None, failure_reason=None, response_data=None):
        """Creates or updates Payment Request for Applicant (application fee).

        Keeps ``razorpay_order_id`` + ``gateway_status`` in sync (same as offer-letter flow)
        so webhooks can resolve the doc and the desk form shows ``captured`` after pay.
        """
        pr_name = frappe.db.get_value("Payment Request", {
            "reference_doctype": "Applicant",
            "reference_name": applicant_doc.name,
            "status": ["!=", "Cancelled"]
        }, "name", order_by="creation desc")

        if not pr_name and transaction_id:
            pr_name = frappe.db.get_value("Payment Request", {"transaction_id": transaction_id}, "name")
        if not pr_name and transaction_id:
            pr_name = frappe.db.get_value("Payment Request", {"razorpay_order_id": transaction_id}, "name")

        amount = flt(applicant_doc.application_fee_amount)
        email_to = applicant_doc.email

        if pr_name:
            pr = frappe.get_doc("Payment Request", pr_name)
            if gateway and frappe.db.exists("Payment Gateway", gateway):
                pr.db_set("payment_gateway", gateway)
        else:
            pr = frappe.new_doc("Payment Request")
            pr.reference_doctype = "Applicant"
            pr.reference_name = applicant_doc.name
            pr.amount = amount
            pr.currency = frappe.defaults.get_global_default("currency") or "INR"
            pr.email_to = email_to
            if gateway and frappe.db.exists("Payment Gateway", gateway):
                pr.payment_gateway = gateway
            pr.transaction_id = transaction_id
            pr.insert(ignore_permissions=True)

        if pr.docstatus > 0:
            frappe.flags.payment_request_status_from_backend = True
            update_data = {"status": status}
            if status == "Requested" and transaction_id:
                update_data["razorpay_order_id"] = transaction_id
                update_data["gateway_status"] = "created"
                update_data["transaction_id"] = transaction_id
            if status == "Paid":
                update_data["failure_message"] = None
                update_data["gateway_status"] = "captured"
                update_data["paid_on"] = now_datetime()
                if transaction_id:
                    prev_oid = frappe.db.get_value("Payment Request", pr.name, "razorpay_order_id")
                    if not prev_oid or str(transaction_id).startswith("order_"):
                        update_data["razorpay_order_id"] = transaction_id
                if payment_id:
                    update_data["transaction_id"] = payment_id
                    update_data["razorpay_payment_id"] = payment_id
            elif failure_reason:
                update_data["status"] = "Failed"
                update_data["failure_message"] = failure_reason
                update_data["gateway_status"] = "failed"
            if response_data:
                update_data["gateway_response"] = json.dumps(response_data, indent=4)
            if gateway and frappe.db.exists("Payment Gateway", gateway):
                update_data["payment_gateway"] = gateway
            frappe.db.set_value("Payment Request", pr.name, update_data, update_modified=True)
            frappe.db.commit()
            if frappe.flags.get("payment_request_status_from_backend"):
                del frappe.flags.payment_request_status_from_backend
        else:
            frappe.flags.payment_request_status_from_backend = True
            try:
                pr.status = status
                if status == "Requested" and transaction_id:
                    pr.razorpay_order_id = transaction_id
                    pr.gateway_status = "created"
                    pr.transaction_id = transaction_id
                if payment_id:
                    pr.transaction_id = payment_id
                    pr.razorpay_payment_id = payment_id
                if response_data:
                    pr.gateway_response = json.dumps(response_data, indent=4)
                if status == "Paid":
                    pr.failure_message = None
                    pr.gateway_status = "captured"
                    pr.paid_on = now_datetime()
                    if transaction_id:
                        if not getattr(pr, "razorpay_order_id", None) or str(transaction_id).startswith(
                            "order_"
                        ):
                            pr.razorpay_order_id = transaction_id
                    if payment_id:
                        pr.razorpay_payment_id = payment_id
                if failure_reason:
                    pr.status = "Failed"
                    pr.failure_message = failure_reason
                    pr.gateway_status = "failed"
                pr.save(ignore_permissions=True)
                if status in ["Paid", "Requested"]:
                    pr.submit()
            finally:
                if frappe.flags.get("payment_request_status_from_backend"):
                    del frappe.flags.payment_request_status_from_backend

    @staticmethod
    @frappe.whitelist()
    def create_application_fee_razorpay_order(applicant_name):
        """Creates Razorpay order for application fee payment."""
        try:
            from slcm.api.service.application_fee_service import sync_application_fee_assignment_for_applicant
            applicant = frappe.get_doc("Applicant", applicant_name)
            if applicant.application_fee_status == "Paid":
                frappe.throw(_("Application fee has already been paid."))
            if applicant.application_fee_status == "Waived":
                frappe.throw(_("Application fee has been waived."))

            fee_amount = flt(applicant.application_fee_amount)
            if fee_amount <= 0:
                from slcm.api.service.application_fee_service import get_application_fee_for_category, _get_applicant_category
                category = _get_applicant_category(applicant_name)
                fee_amount = get_application_fee_for_category(applicant.program, applicant.admission_cycle, category)
                if fee_amount > 0:
                    frappe.db.set_value("Applicant", applicant_name, "application_fee_amount", fee_amount)
                    applicant.application_fee_amount = fee_amount
            
            if fee_amount <= 0:
                frappe.throw(_("Application fee amount is zero. No payment required."))

            actual_payable = fee_amount

            from slcm.api.service.application_fee_service import get_payment_gateway_for_application_fee
            gateway = (
                get_payment_gateway_for_application_fee(applicant.program, applicant.admission_cycle)
                or frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name")
                or "Razorpay"
            )
            try:
                from payments.utils import get_payment_gateway_controller
                controller = get_payment_gateway_controller(gateway)
            except ImportError as e:
                frappe.log_error(frappe.get_traceback(), "Application Fee Order Creation Failed")
                frappe.throw(_("Payment gateway is not available. Please install the Payments app and configure a Payment Gateway (e.g. Razorpay)."))
            if not controller:
                frappe.throw(_("Payment Gateway '{0}' not found or not configured. Please set up Razorpay (or your gateway) in Payment Gateway doctype.").format(gateway))

            payment_details = {
                "amount": actual_payable,
                "title": _("Application Fee"),
                "description": _("Application Fee for {0}").format(applicant.program or ""),
                "reference_doctype": "Applicant",
                "reference_docname": applicant_name,
                "payer_email": applicant.email or "",
                "payer_name": applicant.candidate_name,
                "currency": frappe.defaults.get_global_default("currency") or "INR",
                "receipt": (applicant_name[:40]) if applicant_name else None
            }
            try:
                order = controller.create_order(**payment_details)
            except Exception as order_err:
                frappe.log_error(frappe.get_traceback(), "Application Fee Order Creation Failed")
                err_msg = str(order_err) if order_err else _("Unknown error")
                frappe.throw(_("Payment gateway could not create order: {0}").format(err_msg))
            if not order or not order.get("id"):
                frappe.throw(_("Order creation failed. Please check gateway logs."))

            FeeService._update_payment_request_for_applicant(
                applicant, gateway, order.get("id"), "Requested", response_data=order
            )
            frappe.db.set_value("Applicant", applicant_name, "application_fee_status", "Requested")
            frappe.db.commit()
            sync_application_fee_assignment_for_applicant(applicant_name)
            frappe.db.commit()

            return {
                "order_id": order.get("id"),
                "key_id": controller.api_key,
                "amount": order.get("amount"),
                "currency": order.get("currency"),
                "gateway": gateway
            }
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Application Fee Order Creation Failed")
            raise

    @staticmethod
    @frappe.whitelist()
    def verify_application_fee_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, applicant_name):
        """Verifies Razorpay payment for application fee and marks as paid."""
        try:
            applicant = frappe.get_doc("Applicant", applicant_name)
            # Use gateway from Payment Request (created with order), else from Program Reservation Policy, else default
            pr_gateway = frappe.db.get_value(
                "Payment Request",
                {"reference_doctype": "Applicant", "reference_name": applicant_name, "transaction_id": razorpay_order_id},
                "payment_gateway"
            )
            if not pr_gateway:
                from slcm.api.service.application_fee_service import get_payment_gateway_for_application_fee
                pr_gateway = get_payment_gateway_for_application_fee(applicant.program, applicant.admission_cycle)
            gateway = pr_gateway or frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"
            from payments.utils import get_payment_gateway_controller
            controller = get_payment_gateway_controller(gateway)

            body = razorpay_order_id + "|" + razorpay_payment_id
            api_secret = controller.get_password("api_secret")
            controller.verify_signature(body, razorpay_signature, api_secret)

            FeeService._update_payment_request_for_applicant(
                applicant, gateway, razorpay_order_id, "Paid",
                payment_id=razorpay_payment_id,
                response_data={"payment_id": razorpay_payment_id, "signature": razorpay_signature}
            )

            frappe.db.set_value("Applicant", applicant_name, "application_fee_status", "Paid")
            frappe.db.commit()

            FeeService._generate_application_fee_receipt(applicant, razorpay_payment_id, "Online")
            from slcm.api.service.application_fee_service import sync_application_fee_assignment_for_applicant
            sync_application_fee_assignment_for_applicant(applicant_name)
            frappe.db.commit()
            return {"status": "success"}
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Application Fee Verification Failed")
            return {"status": "failed", "message": str(e)}

    @staticmethod
    def _generate_application_fee_receipt(applicant_doc, transaction_id, payment_mode,
            bank_name=None, cheque_number=None, cheque_date=None, upi_id=None, remarks=None):
        """Generates Applicant Payment Receipt for application fee."""
        try:
            existing = frappe.db.sql(
                """
                SELECT name FROM `tabApplicant Payment Receipt`
                WHERE applicant = %s AND docstatus = 1 AND IFNULL(offer_letter, '') = ''
                ORDER BY creation DESC LIMIT 1
                """,
                applicant_doc.name,
            )
            if existing:
                return existing[0][0]

            from slcm.api.service.application_fee_service import get_application_fee_for_category, _get_applicant_category
            category = _get_applicant_category(applicant_doc.name)
            fee_amount = flt(
                get_application_fee_for_category(applicant_doc.program, applicant_doc.admission_cycle, category)
            )
            if fee_amount <= 0:
                fee_amount = flt(applicant_doc.application_fee_amount or 0)

            receipt = frappe.new_doc("Applicant Payment Receipt")
            receipt.applicant = applicant_doc.name
            receipt.program = applicant_doc.program
            receipt.academic_year = getattr(applicant_doc, "academic_year", None) or None
            tpl = get_payment_receipt_template_for_policy(
                applicant_doc.program, applicant_doc.admission_cycle
            )
            if tpl:
                receipt.payment_receipt_template = tpl
            receipt.payment_date = frappe.utils.today()
            receipt.transaction_id = transaction_id
            receipt.payment_mode = payment_mode
            receipt.total_amount = flt(fee_amount)
            receipt.currency = frappe.defaults.get_global_default("currency") or "INR"
            receipt.bank_name = bank_name
            receipt.cheque_number = cheque_number
            receipt.cheque_date = cheque_date
            receipt.upi_id = upi_id
            receipt.remarks = remarks

            pr = frappe.db.get_value("Payment Request", {"transaction_id": transaction_id}, "name")
            if not pr:
                pr = frappe.db.get_value(
                    "Payment Request",
                    {
                        "reference_doctype": "Applicant",
                        "reference_name": applicant_doc.name,
                        "status": "Paid",
                    },
                    "name",
                    order_by="modified desc",
                )
            if pr:
                receipt.payment_reference = pr
                
            receipt.append("fee_components", {
                "fee_component": "Application Fee",
                "component_name": "Application Fee",
                "amount": fee_amount,
                "is_taxable": 0,
                "tax_rate": 0,
                "tax_amount": 0,
                "total_amount": fee_amount
            })

            receipt.insert(ignore_permissions=True)
            receipt.submit()
            return receipt.name
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Application Fee Receipt Generation Failed")
            return None

    @staticmethod
    def sync_application_fee_after_gateway_capture(pr_name):
        """
        Razorpay webhook marks Payment Request Paid before client verify runs.
        For application fee (reference Applicant), set applicant paid and create receipt. Idempotent.
        """
        if not pr_name:
            return
        pr = frappe.get_doc("Payment Request", pr_name)
        if pr.reference_doctype != "Applicant" or not pr.reference_name:
            return
        if (pr.status or "").strip() != "Paid":
            return
        applicant_name = pr.reference_name
        dup = frappe.db.sql(
            """
            SELECT name FROM `tabApplicant Payment Receipt`
            WHERE applicant = %s AND docstatus = 1 AND IFNULL(offer_letter, '') = ''
            LIMIT 1
            """,
            applicant_name,
        )
        if dup:
            return
        applicant = frappe.get_doc("Applicant", applicant_name)
        if (applicant.application_fee_status or "").strip() != "Paid":
            frappe.db.set_value("Applicant", applicant_name, "application_fee_status", "Paid")
        pay_ref = (getattr(pr, "razorpay_payment_id", None) or pr.transaction_id or "").strip() or pr.name
        FeeService._generate_application_fee_receipt(applicant, pay_ref, "Online")
        from slcm.api.service.application_fee_service import sync_application_fee_assignment_for_applicant
        sync_application_fee_assignment_for_applicant(applicant_name)

    @staticmethod
    @frappe.whitelist()
    def process_application_fee_payment(applicant_name, payment_mode="Cash", reference_number=None,
            bank_name=None, cheque_number=None, cheque_date=None, upi_id=None, remarks=None):
        """Records offline/manual application fee payment."""
        applicant = frappe.get_doc("Applicant", applicant_name)
        if applicant.application_fee_status == "Paid":
            frappe.throw(_("Application fee has already been paid."))

        gateway = "Manual Payment"
        FeeService._update_payment_request_for_applicant(
            applicant, gateway, reference_number or "N/A", "Paid", payment_id=reference_number
        )
        frappe.db.set_value("Applicant", applicant_name, "application_fee_status", "Paid")
        frappe.db.commit()

        out = FeeService._generate_application_fee_receipt(
            applicant, reference_number or "N/A", payment_mode,
            bank_name=bank_name, cheque_number=cheque_number, cheque_date=cheque_date,
            upi_id=upi_id, remarks=remarks
        )
        from slcm.api.service.application_fee_service import sync_application_fee_assignment_for_applicant
        sync_application_fee_assignment_for_applicant(applicant_name)
        frappe.db.commit()
        return out

    @staticmethod
    @frappe.whitelist()
    def log_application_fee_payment_failure(applicant_name, order_id, error_data):
        """Logs application fee payment failure."""
        try:
            applicant = frappe.get_doc("Applicant", applicant_name)
            gateway = frappe.db.get_value("Payment Gateway", {"is_default": 1}, "name") or "Razorpay"
            if isinstance(error_data, str):
                try:
                    error_data = json.loads(error_data)
                except Exception:
                    pass
            err_msg = ""
            if isinstance(error_data, dict):
                err_msg = error_data.get("description") or error_data.get("message") or str(error_data)
            else:
                err_msg = str(error_data)
            FeeService._update_payment_request_for_applicant(
                applicant, gateway, order_id, "Failed", failure_reason=err_msg, response_data=error_data
            )
            return {"status": "success"}
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Log Application Fee Failure Failed")
            return {"status": "error", "message": str(e)}


@frappe.whitelist()
def create_offer_razorpay_order(offer_name):
    return FeeService.create_offer_razorpay_order(offer_name)

@frappe.whitelist()
def verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name):
    return FeeService.verify_offer_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, offer_name)

@frappe.whitelist()
def process_fee_payment(offer_name, payment_mode="Cash", reference_number=None, 
                       bank_name=None, cheque_number=None, cheque_date=None, 
                       upi_id=None, remarks=None):
    return FeeService.process_fee_payment(
        offer_name, payment_mode, reference_number, 
        bank_name, cheque_number, cheque_date, upi_id, remarks
    )
@frappe.whitelist()
def log_payment_failure(offer_name, order_id, error_data):
    return FeeService.log_payment_failure(offer_name, order_id, error_data)

@frappe.whitelist()
def create_application_fee_razorpay_order(applicant_name):
    return FeeService.create_application_fee_razorpay_order(applicant_name)

@frappe.whitelist()
def verify_application_fee_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, applicant_name):
    return FeeService.verify_application_fee_payment(razorpay_payment_id, razorpay_order_id, razorpay_signature, applicant_name)

@frappe.whitelist()
def process_application_fee_payment(applicant_name, payment_mode="Cash", reference_number=None,
        bank_name=None, cheque_number=None, cheque_date=None, upi_id=None, remarks=None):
    return FeeService.process_application_fee_payment(
        applicant_name, payment_mode, reference_number,
        bank_name, cheque_number, cheque_date, upi_id, remarks
    )

@frappe.whitelist()
def log_application_fee_payment_failure(applicant_name, order_id, error_data):
    return FeeService.log_application_fee_payment_failure(applicant_name, order_id, error_data)
