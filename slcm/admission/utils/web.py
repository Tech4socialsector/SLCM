import frappe

@frappe.whitelist(methods=["POST", "GET"])
def check_existing_application(admission_cycle=None):
    """
    Returns existing application name if user already applied in this cycle.
    Called from /admission page before showing Apply Now.
    """
    if frappe.session.user == "Guest":
        return {"exists": False, "name": ""}

    filters = {"owner": frappe.session.user}
    if admission_cycle:
        filters["admission_cycle"] = admission_cycle

    existing = frappe.get_all(
        "Applicant",
        filters=filters,
        fields=["name", "admission_cycle", "application_status"],
        order_by="creation desc",
        limit=1
    )
    if existing:
        return {
            "exists":  True,
            "name":    existing[0].name,
            "status":  existing[0].application_status,
            "cycle":   existing[0].admission_cycle,
        }
    return {"exists": False, "name": ""}

@frappe.whitelist(methods=["POST", "GET"])
def mark_notifications_read(names=None):
    """Marks unread notifications as read. If names provided, only those."""
    user = frappe.session.user
    if user == "Guest":
        return

    try:
        if not names: return
        if isinstance(names, str):
            import json as _json
            try:
                names = _json.loads(names)
            except Exception:
                names = [names]

        # Get applicant records for this user to ensure they own these notifications
        applicant_names = frappe.get_all(
            "Applicant",
            filters={"email": user},
            pluck="name"
        )
        if not applicant_names:
            return
            
        filters = {
            "applicant": ["in", applicant_names],
            "name": ["in", names]
        }

        frappe.db.set_value(
            "Applicant Notification",
            filters,
            "is_read", 1
        )
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(f"mark_notifications_read failed: {e}", "Portal")
        return {"success": False}

@frappe.whitelist(methods=["POST", "GET"])
def get_portal_notifications():
    try:
        user = frappe.session.user
        if user == "Guest":
            return {"notifications": [], "announcements": []}

        # Get applicant records for this user
        applicant_names = frappe.get_all(
            "Applicant",
            filters={"email": user},
            pluck="name"
        )

        notifications = []
        if applicant_names:
            notifications = frappe.get_all(
                "Applicant Notification",
                filters={"applicant": ["in", applicant_names]},
                fields=["name", "notification_type as title", "message", "is_read",
                        "created_on as creation", "owner", "announcement"],
                order_by="created_on desc",
                limit=15
            )
            for n in notifications:
                try:
                    n["owner_fullname"] = frappe.db.get_value("User", n.owner, "full_name") or n.owner
                    if n.announcement:
                        n["image"] = frappe.db.get_value("Portal Announcement", n.announcement, "featured_image")
                except:
                    n["owner_fullname"] = ""

        announcements = frappe.get_all(
            "Portal Announcement",
            filters={"is_active": 1},
            fields=["name", "title", "publish_date", "announcement_type",
                    "summary as content", "featured_image as image", "owner"],
            order_by="publish_date desc",
            limit=10
        )
        for a in announcements:
            try:
                a["owner_fullname"] = frappe.db.get_value("User", a.owner, "full_name") or a.owner
            except:
                a["owner_fullname"] = ""

        return {"notifications": notifications, "announcements": announcements}
    except Exception as e:
        frappe.log_error(f"get_portal_notifications failed: {e}", "Portal")
        return {"notifications": [], "announcements": []}

@frappe.whitelist(allow_guest=True)
def get_public_announcements():
    """Returns announcements visible without login"""
    try:
        ann = frappe.get_all("Portal Announcement",
            filters={"is_active": 1, "status": "Published"},
            fields=["name", "title", "publish_date",
                    "announcement_type", "summary as content",
                    "featured_image", "owner"],
            order_by="publish_date desc",
            limit=10)
        
        for a in ann:
            try:
                a["owner_fullname"] = frappe.db.get_value("User", a.owner, "full_name") or a.owner
            except:
                a["owner_fullname"] = ""
                
        return ann or []
    except Exception as e:
        frappe.log_error(f"get_public_announcements failed: {e}", "Portal")
        return []

@frappe.whitelist(methods=["POST", "GET"])
def get_user_type():
    """Returns user_type for the currently logged-in user"""
    try:
        user_type = frappe.db.get_value("User", frappe.session.user, "user_type")
        return {"user_type": user_type or "Website User"}
    except Exception as e:
        frappe.log_error(f"get_user_type failed: {e}", "Portal")
        return {"user_type": "Website User"}

def _get_stage_seq(stages, stage_name):
    """Returns sequence number of a stage by name."""
    for s in stages:
        if s.stage_name == stage_name:
            return getattr(s, "sequence", None) or getattr(s, "sequence_no", None) or 0
    return 0

@frappe.whitelist(allow_guest=False)
def get_stage_tracker_data(applicant_name: str) -> dict:
    """
    Returns stage tracker data for the portal progress bar.
    Directly matches Applicant.application_status with Admission Cycle Stage.application_status.
    Filters stages based on Applicant.intake_type.
    """
    applicant = frappe.db.get_value(
        "Applicant", applicant_name,
        ["owner", "email", "admission_cycle", "intake_type", "application_status"],
        as_dict=True
    )
    if not applicant:
        frappe.throw("Not found", frappe.DoesNotExistError)

    user     = frappe.session.user
    is_admin = "Admission Admin" in frappe.get_roles(user)
    if not is_admin and applicant.owner != user and applicant.email != user:
        frappe.throw("Not permitted", frappe.PermissionError)

    if not applicant.admission_cycle:
        return {"stages": [], "progress_pct": 0, "current_status": applicant.application_status}

    # Load all enabled stages for this cycle
    all_stages = frappe.get_all(
        "Admission Cycle Stage",
        filters={
            "parent": applicant.admission_cycle,
            "is_enabled": 1
        },
        fields=[
            "name", "stage_name", "stage_type", "stage_code",
            "sequence_no", "start_date", "end_date", "applicable_workflow",
            "action_label", "action_url", "requires_applicant_action",
            "activate_status", "completed_status", "closed_status"
        ],
        order_by="sequence_no asc"
    )

    # Filter stages by intake_type
    # Admission Cycle Stage.applicable_workflow matches Applicant.intake_type
    # If applicable_workflow is "All", it shows for everyone.
    intake = applicant.intake_type or "External Test"
    filtered_stages = [
        s for s in all_stages
        if s.applicable_workflow == "All" or s.applicable_workflow == intake
    ]

    if not filtered_stages:
        return {"stages": [], "progress_pct": 0, "current_status": applicant.application_status}

    # Find the active stage by matching application_status
    # We look for the furthest stage that matches the current status.
    current_status = applicant.application_status
    active_index = -1
    is_terminal_stop = False
    is_completed_stop = False
    
    for i, s in enumerate(filtered_stages):
        if s.activate_status == current_status:
            active_index = i
            is_terminal_stop = False
            is_completed_stop = False
        elif s.completed_status == current_status:
            active_index = i
            is_terminal_stop = False
            is_completed_stop = True
        elif s.closed_status == current_status:
            active_index = i
            is_terminal_stop = True
            is_completed_stop = False

    # If no exact match, we might need a fallback. 
    # For now, if no match, assume it's before the first stage or past the last.
    
    stages_out = []
    found_active = False

    for i, s in enumerate(filtered_stages):
        state = "pending"
        if active_index != -1:
            if i < active_index:
                state = "completed"
            elif i == active_index:
                if is_terminal_stop:
                    state = "closed"
                elif is_completed_stop:
                    state = "completed"
                else:
                    state = "active"
                found_active = True
            else:
                state = "pending"
        else:
            # Fallback logic if no status match: 
            # This part is tricky. If status doesn't match, maybe it's Draft or something else.
            state = "pending"

        stages_out.append({
            "name":                      s.get("name"),
            "stage_name":                s.get("stage_name") or s.get("stage_type"),
            "stage_type":                s.get("stage_type"),
            "stage_code":                s.get("stage_code") or "",
            "sequence":                  s.get("sequence_no") or 0,
            "state":                     state,
            "status":                    state, # Added for JS compatibility
            "start_date":                str(s.start_date) if s.get("start_date") else None,
            "end_date":                  str(s.end_date)   if s.get("end_date")   else None,
            "action_label":              s.get("action_label") or "",
            "action_url":                s.get("action_url") or "",
            "requires_applicant_action": s.get("requires_applicant_action") or 0,
            "show_action": bool(
                state == "active" and
                s.get("action_url") and
                s.get("requires_applicant_action")
            ),
        })

    # Calculate progress percentage based on active index
    total_stages = len(filtered_stages)
    if active_index != -1:
        # Progress is (index + 1) / total
        progress_pct = round(((active_index + 1) / total_stages) * 100, 1)
    else:
        progress_pct = 0.0

    return {
        "stages":         stages_out,
        "progress_pct":   progress_pct,
        "current_status": applicant.application_status,
        "intake_type":    applicant.intake_type
    }




@frappe.whitelist(methods=["POST", "GET"])
def get_edit_permission(applicant_name):
    """
    Returns whether the current applicant can edit their application.
    Two-layer check:
      Layer 1: Portal Config master switch (allow_edit_after_submit)
      Layer 2: Current stage is_editable flag
    """
    import frappe

    # Load applicant
    applicant = frappe.get_doc("Applicant", applicant_name)

    # Only owner can check own permissions
    allowed_roles = {"Admission Admin", "System Manager", "Applicant"}
    is_owner = frappe.session.user == applicant.owner
    has_role = bool(allowed_roles & set(frappe.get_roles()))
    if not is_owner and not has_role:
        return {"editable": False, "reason": "Not permitted"}

    # Draft is always editable
    if applicant.docstatus == 0:
        return {"editable": True, "reason": "draft", "editable_sections": []}

    # Layer 1: Portal Config master switch
    try:
        portal_config = frappe.get_single("Admission Portal Config")
        if not portal_config.allow_edit_after_submit:
            return {
                "editable": False,
                "reason": "Editing is currently disabled by the administrator."
            }
    except Exception:
        # If Portal Config not found, deny by default
        return {"editable": False, "reason": "Portal config not found"}

    # Layer 2: Current stage is_editable flag
    if not applicant.admission_cycle or not applicant.current_stage:
        return {"editable": False, "reason": "No active stage found"}

    cycle_doc = frappe.get_doc("Admission Cycle", applicant.admission_cycle)
    current_stage_row = next(
        (s for s in cycle_doc.stages
         if s.stage_name == applicant.current_stage),
        None
    )

    if not current_stage_row:
        return {"editable": False, "reason": "Current stage not configured"}

    if not current_stage_row.is_editable:
        return {
            "editable": False,
            "reason": f"Editing is not allowed during the {applicant.current_stage} stage."
        }

    return {
        "editable":          True,
        "reason":            "stage_allows",
        "editable_sections": [],   # empty = all sections editable
    }

@frappe.whitelist()
def get_offer_list(limit_start=0, limit_page_length=10):
    """
    Fetches offer letters with pagination. 
    If admin, fetches all. If applicant, fetches only theirs.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Authentication required", frappe.PermissionError)

    roles = frappe.get_roles(user)
    is_admin = "Administrator" in roles or "System Manager" in roles or "Admission Admin" in roles
    
    filters = {}
    applicant_name = "System View"
    
    if not is_admin:
        # User is an applicant, filter by their record
        applicant = frappe.db.get_value("Applicant", {"email": user}, "name")
        if not applicant:
            if frappe.db.exists("Applicant", user):
                applicant = user
            else:
                frappe.throw(f"Applicant record not found for user {user}")
        
        filters["applicant"] = applicant
        applicant_name = frappe.db.get_value("Applicant", applicant, "candidate_name") or applicant
    
    # Fetch total count for pagination
    total_count = frappe.db.count("Offer Letter", filters=filters)

    # Fetch offers
    fields = [
        "name", "program", "issued_on", "offer_status", 
        "payment_deadline", "payable_amount", "campus", "applicant"
    ]
    
    # Ensure integer types for pagination
    limit_start = int(limit_start)
    limit_page_length = int(limit_page_length)

    offers = frappe.get_all(
        "Offer Letter", 
        filters=filters, 
        fields=fields, 
        order_by="creation desc",
        limit_start=limit_start,
        limit_page_length=limit_page_length,
        ignore_permissions=True
    )

    for offer in offers:
        if offer.campus:
            offer.campus_name = frappe.db.get_value("Campus", offer.campus, "campus_name") or offer.campus
        else:
            offer.campus_name = ""
            
        # Fetch scholarship info from Applicant Fee Assignment
        afa = frappe.db.get_value("Applicant Fee Assignment", 
            {"offer_letter": offer.name, "fee_type": "Admission Fee"}, 
            ["scholarship_amount", "final_payable_amount"], as_dict=True)
        
        if afa:
            offer.scholarship_amount = afa.scholarship_amount or 0
            offer.final_payable_amount = afa.final_payable_amount or offer.payable_amount
        else:
            offer.scholarship_amount = 0
            offer.final_payable_amount = offer.payable_amount

    return {
        "offers": offers,
        "total_count": total_count,
        "applicant_name": applicant_name,
        "is_admin": is_admin,
        "currency": frappe.defaults.get_global_default("currency") or "INR"
    }

@frappe.whitelist(methods=["POST", "GET"])
def download_admit_card(admit_card):
    """
    Custom download function for Admit Card that bypasses standard print permissions
    after verifying that the current user owns the application.
    """
    user = frappe.session.user
    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    
    try:
        doc = frappe.get_doc("Entrance Test Seat Allocation", admit_card, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Admit Card not found")

    if not applicant_name or doc.applicant != applicant_name:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not authorized", frappe.PermissionError)

    is_rescheduled = (doc.is_rescheduled == 1 or doc.entrance_test_status == "Rescheduled")
    status = doc.re_allocation_status if is_rescheduled else doc.allocation_status
    
    if status not in ["Allocated", "Reallocated"]:
        frappe.throw("Admit Card is only available after seat allocation is confirmed.")

    field_to_check = "reschedule_admit_card" if is_rescheduled else "admit_card"
    stored_file_url = getattr(doc, field_to_check)

    if not stored_file_url:
        from slcm.admission.doctype.entrance_test_list.entrance_test_list import generate_and_store_admit_card
        stored_file_url = generate_and_store_admit_card(doc.name, is_rescheduled=is_rescheduled)
        if stored_file_url:
            doc.reload()

    if stored_file_url:
        file_doc = frappe.get_doc("File", {"file_url": stored_file_url})
        frappe.local.response.filename = f"Admit_Card_{doc.applicant}.pdf"
        frappe.local.response.filecontent = file_doc.get_content()
        frappe.local.response.type = "download"
    else:
        frappe.throw("Admit Card generation failed. Please contact the admission office.")

@frappe.whitelist(methods=["POST", "GET"])
def download_application(applicant_name):
    """
    Generates and downloads the Applicant PDF for the owner.
    Prefers Chrome PDF generator to avoid wkhtmltopdf issues (unpatched Qt, network errors).
    Falls back to wkhtmltopdf if Chrome is not available.
    """
    user = frappe.session.user
    try:
        applicant = frappe.get_doc("Applicant", applicant_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Application not found")

    if applicant.owner != user and applicant.email != user:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)

    frappe.flags.ignore_print_permissions = True
    pdf_content = None
    last_error = None

    # Prefer Chrome to avoid wkhtmltopdf "unpatched qt" and "network error: InternalServerError"
    for generator in ("chrome", "wkhtmltopdf"):
        try:
            pdf_content = frappe.get_print(
                "Applicant",
                applicant_name,
                "Applicant Application Form",
                as_pdf=True,
                doc=applicant,
                pdf_generator=generator,
            )
            if pdf_content:
                break
        except Exception as e:
            last_error = e
            # Log error for each attempt to help debugging
            frappe.log_error(
                title=f"Application Download failed with {generator}",
                message=f"Applicant: {applicant_name}\nError: {str(e)}\n{frappe.get_traceback()}"
            )
            if generator == "chrome":
                continue
            # Do not raise here, let it reach the throw below if both fail
            break

    if not pdf_content:
        error_msg = f"PDF generation failed. Try: Print Format 'Applicant Application Form' → PDF generator = Chrome, or run: bench setup chromium. Error: {str(last_error)}"
        frappe.throw(_(error_msg))

    frappe.local.response.filename = f"Application_{applicant_name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"

@frappe.whitelist(methods=["POST", "GET"])
def download_receipt(receipt_name):
    """
    Generates and downloads the Applicant Payment Receipt PDF for the owner.

    Uses Program Reservation Policy.payment_receipt_template (if configured)
    as the print format, falling back to the default format.
    """
    user = frappe.session.user
    try:
        receipt = frappe.get_doc("Applicant Payment Receipt", receipt_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Receipt not found")

    # Check if this user owns the receipt (via the Applicant record)
    applicant_name = receipt.applicant
    applicant_email = frappe.db.get_value("Applicant", applicant_name, "email")

    if receipt.owner != user and applicant_email != user:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)

    # Resolve print format from Program Reservation Policy if possible
    print_format = "Applicant Payment Receipt Format"  # Fallback
    try:
        if applicant_name:
            app = frappe.get_doc("Applicant", applicant_name)
            if app.admission_cycle and app.program:
                # Prefer campus-specific policy; fall back to generic program+cycle
                policy_name = None
                if app.campus:
                    policy_name = frappe.db.get_value(
                        "Admission Cycle Program",
                        {
                            "parent": app.admission_cycle,
                            "program": app.program,
                            "campus": app.campus,
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
                if policy_name:
                    template = frappe.db.get_value(
                        "Program Reservation Policy",
                        policy_name,
                        "payment_receipt_template",
                    )
                    if template:
                        print_format = template
    except Exception:
        # On any lookup error, quietly fall back to default format
        pass

    frappe.flags.ignore_print_permissions = True
    pdf_content = frappe.get_print(
        "Applicant Payment Receipt",
        receipt_name,
        print_format,
        as_pdf=True,
        doc=receipt,
    )

    frappe.local.response.filename = f"Receipt_{receipt_name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"


@frappe.whitelist()
def get_latest_application_fee_receipt(applicant_name: str):
    """
    Returns the latest Applicant Payment Receipt name for the given applicant
    for Application Fee payments (receipts not linked to an Offer Letter).
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    applicant_name = (applicant_name or "").strip()
    if not applicant_name:
        return {"receipt_name": None}

    # Ownership check
    applicant_email = frappe.db.get_value("Applicant", applicant_name, "email")
    if applicant_email not in (user, frappe.db.get_value("User", user, "email")):
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)

    receipt_name = frappe.db.get_value(
        "Applicant Payment Receipt",
        {"applicant": applicant_name, "offer_letter": ["is", "not set"], "docstatus": 1},
        "name",
        order_by="creation desc",
    )
    return {"receipt_name": receipt_name}

@frappe.whitelist(methods=["POST", "GET"])
def download_offer_letter(offer_letter):
    """
    Generates and downloads the Offer Letter PDF for the owner.
    """
    user = frappe.session.user
    try:
        ol = frappe.get_doc("Offer Letter", offer_letter, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Offer Letter not found")

    applicant_name = ol.applicant
    applicant = frappe.get_doc("Applicant", applicant_name, ignore_permissions=True)
    
    if applicant.owner != user and applicant.email != user:
        if "Admission Admin" not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
            frappe.throw("Not permitted", frappe.PermissionError)
    
    # Check if PDF already stored
    if ol.offer_letter_pdf:
        try:
            file_doc = frappe.get_doc("File", {"file_url": ol.offer_letter_pdf})
            frappe.local.response.filename = f"Offer_Letter_{applicant_name}.pdf"
            frappe.local.response.filecontent = file_doc.get_content()
            frappe.local.response.type = "download"
            return
        except Exception:
            pass

    # Generate PDF
    frappe.flags.ignore_print_permissions = True
    pdf_content = frappe.get_print("Offer Letter", offer_letter, as_pdf=True, doc=ol)
    
    frappe.local.response.filename = f"Offer_Letter_{applicant_name}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"

