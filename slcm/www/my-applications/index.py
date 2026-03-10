import frappe
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.doctype.eligibility_result.eligibility_result import get_applicant_data

login_required = True

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/my-applications"
        raise frappe.Redirect

    # ── Detail mode: if ?app= param provided, load that specific application ──
    _app_name = frappe.form_dict.get("app") or ""

    # ── Auto-open application from ?program= param (from admission cards) ──
    program_filter = frappe.form_dict.get("program") or ""
    context.program_filter = program_filter

    if not _app_name and program_filter:
        _found = frappe.db.sql("""
            SELECT a.name FROM `tabApplicant` a
            JOIN `tabProgram` p ON a.program = p.name
            WHERE a.owner = %s AND (p.program_slug = %s OR p.name = %s)
            LIMIT 1
        """, (frappe.session.user, program_filter, program_filter))
        if _found:
            _app_name = _found[0][0]

    # ── Portal config (required for theme vars) ──────────────────
    try:
        from slcm.admission.utils.portal import get_portal_config
        portal_config = get_portal_config()
        context.portal_config = portal_config
    except Exception:
        portal_config = None
        context.portal_config = None

    if _app_name:
        # Security: verify ownership
        try:
            applicant = frappe.get_doc("Applicant", _app_name, ignore_permissions=True)
        except frappe.DoesNotExistError:
            context.app_not_found = True
            context.selected_app = None
            return

        # Check access (robust check: owner or email)
        _session_user = frappe.session.user
        if applicant.owner != _session_user and applicant.email != _session_user and \
           "Admission Admin" not in frappe.get_roles():
            context.access_denied = True
            context.selected_app = None
            return

        context.selected_app = applicant

        # ── Stage tracker ──────────────────────────────────────────────
        try:
            cycle_stages = frappe.get_all(
                "Admission Cycle Stage",
                filters={"parent": applicant.admission_cycle},
                fields=["stage_name", "idx"],
                order_by="idx asc",
                ignore_permissions=True
            ) or []
            # Note: The prompt says Admission Stage Config, but I'll check what exists.
            # I'll use a safer check for cycle stages.
        except Exception:
            cycle_stages = []

        # Determine current stage index
        current = (applicant.get("current_stage_name") or 
                   applicant.get("current_stage") or 
                   applicant.get("application_status") or "")
        
        # Check if current stage is a link/ID, fetch name
        if current and frappe.db.exists("Stage Master", current):
            current = frappe.db.get_value("Stage Master", current, "stage_name") or current

        stages_with_state = []
        found_active = False
        
        # Try to get stages from Admission Stage Config if Admission Cycle Stage failed
        if not cycle_stages:
            try:
                cycle_stages = frappe.get_all(
                    "Admission Stage Config",
                    filters={"admission_cycle": applicant.admission_cycle},
                    fields=["stage_name", "sequence as idx"],
                    order_by="sequence asc",
                    ignore_permissions=True
                )
            except Exception: pass

        for s in cycle_stages:
            sname = (s.get("stage_name") if hasattr(s,"get") else s.stage_name) or ""
            if sname == current and not found_active:
                state = "active"
                found_active = True
            elif not found_active:
                state = "completed"
            else:
                state = "pending"
            stages_with_state.append({"name": sname, "state": state})

        # Fallback: if no cycle stages, build from application_status
        if not stages_with_state:
            statuses = ["Submitted", "Under Review", "Interview", "Decision"]
            current_lower = str(current).lower()
            found = False
            for st in statuses:
                if st.lower() == current_lower and not found:
                    state = "active"; found = True
                elif not found:
                    state = "completed"
                else:
                    state = "pending"
                stages_with_state.append({"name": st, "state": state})

        context.stage_tracker = stages_with_state

        # ── Documents ────────────────────────────────────────────────
        try:
            context.app_documents = frappe.get_all(
                "Applicant Document",
                filters={"applicant": _app_name},
                fields=[
                    "name", "document_type", "document_name",
                    "file_url", "verification_status",
                    "upload_date", "creation", "remarks"
                ],
                order_by="creation asc",
                ignore_permissions=True
            ) or []
        except Exception:
            context.app_documents = []

        # ── Next steps for current stage ─────────────────────────────
        try:
            _pc = frappe.get_doc("Applicant Portal Config")
            _next_steps = []
            if _pc:
                all_steps = (_pc.get("stage_next_steps") or 
                             getattr(_pc, "stage_next_steps", []) or [])
                for step in all_steps:
                    sn = (step.get("stage_name") if hasattr(step,"get") 
                          else step.stage_name) or ""
                    if sn.lower() == str(current).lower():
                        _next_steps.append({
                            "text":       (step.get("step_text") if hasattr(step,"get") 
                                           else step.step_text) or "",
                            "is_link":    (step.get("is_link") if hasattr(step,"get") 
                                           else step.is_link) or 0,
                            "link_url":   (step.get("link_url") if hasattr(step,"get") 
                                           else step.link_url) or "",
                            "link_label": (step.get("link_label") if hasattr(step,"get") 
                                           else step.link_label) or "",
                        })

            # Hardcoded fallback if no config
            if not _next_steps:
                fallback = {
                    "submitted":    ["Ensure all documents are uploaded to the checklist.",
                                     "Check your email for confirmation of receipt."],
                    "under review": ["Await evaluation results — you will be notified.",
                                     "Ensure your contact details are up to date."],
                    "entrance test":["Download your admit card from the Documents section.",
                                     "Check the test center location and reporting time."],
                    "interview":    ["Confirm your interview slot as soon as possible.",
                                     "Prepare your original documents for verification."],
                    "merit list":   ["Monitor the portal for merit list publication.",
                                     "Check your rank and category seat availability."],
                    "offer":        ["Review your offer letter carefully.",
                                     "Pay the acceptance fee before the deadline.",
                                     "Complete document verification to confirm your seat."],
                }
                key = str(current).lower()
                for k, v in fallback.items():
                    if k in key or key in k:
                        _next_steps = [{"text": t, "is_link": 0, 
                                        "link_url": "", "link_label": ""} for t in v]
                        break

            context.next_steps = _next_steps

            # ── Support contact ───────────────────────────────────────
            context.support_name  = (
                _pc.get("support_name") if _pc and hasattr(_pc,"get") 
                else getattr(_pc,"support_name","")) or ""
            context.support_role  = (
                _pc.get("support_role") if _pc and hasattr(_pc,"get") 
                else getattr(_pc,"support_role","")) or ""
            context.support_email = (
                _pc.get("support_email") if _pc and hasattr(_pc,"get") 
                else getattr(_pc,"support_email","")) or ""
            context.campus_image  = (
                _pc.get("hero_image") if _pc and hasattr(_pc,"get") 
                else getattr(_pc,"hero_image","")) or ""

        except Exception as ex:
            frappe.log_error(str(ex), "my_applications detail context")
            context.next_steps    = []
            context.support_name  = ""
            context.support_role  = ""
            context.support_email = ""
            context.campus_image  = ""

        # ── Narrative / remarks ───────────────────────────────────────
        try:
            context.app_narrative = (
                applicant.get("remarks") or 
                applicant.get("notes") or 
                applicant.get("application_notes") or ""
            )
        except Exception:
            context.app_narrative = ""

        # ── Submission date ────────────────────────────────────────────
        try:
            context.submission_date = frappe.utils.format_date(
                applicant.get("creation") or applicant.creation, "MMMM d, yyyy"
            )
        except Exception:
            context.submission_date = ""

        context.app_name_param = _app_name

        # ── Fetch full combined results using the API ────────────
        context.all_results = []
        context.all_merit   = []
        try:
            # Try API first
            combined_data = get_applicant_data()
            if isinstance(combined_data, list):
                for entry in combined_data:
                    if entry.get("profile", {}).get("applicant_id") == _app_name:
                        context.all_results = entry.get("results") or []
                        context.all_merit   = entry.get("merit") or []
                        break
            
            # If still empty, direct fetch as fallback (only if user has access)
            if not context.all_merit:
                mrows = frappe.get_all("Merit List Applicant",
                    filters={"applicant_id": _app_name},
                    fields=["total_score", "overall_rank", "status", "parent"]
                )
                for m in mrows:
                    if frappe.db.get_value("Merit List", m.parent, "status") == "Published":
                        context.all_merit.append(m)
            
            if not context.all_results:
                srows = frappe.get_all("Seat Selection Applicant",
                    filters={"applicant_id": _app_name},
                    fields=["selection_status", "overall_rank", "allocation_type", "parent", "total_score"]
                )
                for s in srows:
                    if frappe.db.get_value("Seat Allocation", s.parent, "status") == "Published":
                        context.all_results.append(s)
        except Exception:
            pass

        # ── fee_payment_status ────────────────────────────────────
        context.fee_payment_status = (
            applicant.get("application_fee_status") or ""
        )

        # ── interview_status (from Interview Seat Allocation) ─────
        context.interview_status = ""
        try:
            irows = frappe.get_all(
                "Interview Seat Allocation",
                filters={"applicant": _app_name},
                fields=["interview_date", "interview_time",
                        "interview_slot_status"],
                order_by="creation desc", limit=1,
                ignore_permissions=True
            )
            if irows:
                ir      = irows[0]
                slot_st = ir.get("interview_slot_status") or ""
                idate   = str(ir.get("interview_date") or "")[:10]
                itime   = str(ir.get("interview_time") or "")[:5]
                if idate:
                    fmt = frappe.utils.format_date(idate, "MMM d, yyyy")
                    context.interview_status = (
                        f"{slot_st} · {fmt}" if slot_st else fmt
                    )
                    if itime:
                        context.interview_status += f", {itime}"
                elif slot_st:
                    context.interview_status = slot_st
            elif "interview" in str(
                applicant.get("application_status") or ""
            ).lower():
                context.interview_status = "To be Scheduled"
        except Exception:
            pass

        # ── merit (from Applicant Merit DocType) ──────────────────
        context.merit_rank       = ""
        context.merit_percentile = ""
        context.merit_score_val  = ""
        context.merit_cat_rank   = ""
        try:
            mrows = frappe.get_all(
                "Applicant Merit",
                filters={"applicant": _app_name},
                fields=["overall_rank", "merit_score",
                        "percentile", "category_rank"],
                order_by="creation desc", limit=1,
                ignore_permissions=True
            )
            if mrows:
                m = mrows[0]
                context.merit_rank       = str(m.get("overall_rank") or "").strip()
                context.merit_percentile = str(m.get("percentile") or "").strip()
                context.merit_score_val  = str(m.get("merit_score") or "").strip()
                context.merit_cat_rank   = str(m.get("category_rank") or "").strip()
            else:
                ms = applicant.get("merit_score") or ""
                if ms:
                    context.merit_score_val = str(ms)
        except Exception:
            ms = applicant.get("merit_score") or ""
            if ms:
                context.merit_score_val = str(ms)

        # ── seat allocation (from Seat Allocation DocType) ────────
        context.seat_allocation = None
        context.seat_status     = ""
        try:
            srows = frappe.get_all(
                "Seat Allocation",
                filters={"applicant": _app_name},
                fields=["program", "campus", "category",
                        "status", "allocation_type"],
                order_by="creation desc", limit=1,
                ignore_permissions=True
            )
            if srows:
                context.seat_allocation = srows[0]
                context.seat_status = (srows[0].get("status") or "").strip()
        except Exception:
            pass

        # ── payment details (from Fee Payment DocType) ────────────
        context.payment_details = None
        try:
            prows = frappe.get_all(
                "Fee Payment",
                filters={"applicant": _app_name},
                fields=["fee_type", "amount", "transaction_id",
                        "payment_date", "status"],
                order_by="creation desc", limit=1,
                ignore_permissions=True
            )
            if prows:
                p = prows[0]
                context.payment_details = {
                    "fee_label":      p.get("fee_type") or "Application Fee",
                    "amount":         p.get("amount") or "",
                    "transaction_id": p.get("transaction_id") or "",
                    "payment_date":   frappe.utils.format_date(
                        str(p.get("payment_date") or "")[:10],
                        "MMM d, yyyy"
                    ) if p.get("payment_date") else "",
                    "status": p.get("status") or context.fee_payment_status or "",
                }
            elif context.fee_payment_status:
                context.payment_details = {
                    "fee_label": "Application Fee",
                    "amount": "", "transaction_id": "",
                    "payment_date": "",
                    "status": context.fee_payment_status,
                }
        except Exception:
            pass

        # ── entrance test (Entrance Test Seat Allocation) ─────────
        context.entrance_test  = None
        context.admit_card_url = ""
        try:
            etrows = frappe.get_all(
                "Entrance Test Seat Allocation",
                filters={"applicant": _app_name},
                fields=["entrance_test_name", "center_name",
                        "center_address", "seat_number",
                        "allocation_status", "admit_card", "name"],
                order_by="creation desc", limit=1,
                ignore_permissions=True
            )
            if etrows:
                et        = etrows[0]
                test_name = et.get("entrance_test_name") or ""
                test_date = ""
                test_time = ""
                if test_name:
                    try:
                        td = frappe.get_doc(
                            "Entrance Test List", test_name,
                            ignore_permissions=True
                        )
                        test_date = frappe.utils.format_date(
                            str(td.get("test_date") or "")[:10],
                            "MMMM d, yyyy"
                        ) if td.get("test_date") else ""
                        test_time = str(td.get("test_time") or "")
                    except Exception:
                        pass
                context.entrance_test = {
                    "test_name":      test_name,
                    "test_date":      test_date,
                    "test_time":      test_time,
                    "center_name":    et.get("center_name") or "",
                    "center_address": et.get("center_address") or "",
                    "seat_number":    et.get("seat_number") or "",
                    "admit_status":   et.get("allocation_status") or "",
                    "admit_name":     et.get("name") or "",
                }
                context.admit_card_url = (
                    f"/api/method/slcm.admission.utils.web.download_admit_card"
                    f"?admit_card={et.get('name')}"
                )
        except Exception as ex:
            frappe.log_error(title="my_app_et", message=str(ex))

        # ── offer letter URL (from Offer Letter DocType) ──────────
        context.offer_letter_url = ""
        try:
            orows = frappe.get_all(
                "Offer Letter",
                filters={"applicant": _app_name},
                fields=["name", "pdf_file"],
                order_by="creation desc", limit=1,
                ignore_permissions=True
            )
            if orows:
                context.offer_letter_url = (
                    orows[0].get("pdf_file") or
                    f"/api/method/slcm.admission.utils.web.download_offer_letter"
                    f"?offer_letter={orows[0].get('name')}"
                )
        except Exception:
            pass

        context.show_detail    = True
        context.title = f"Application Details: {_app_name}"
        return  # ← exit early; template will render detail view

    # If no ?app= param, fall through to existing list view logic
    context.show_detail = False

    # Status styling
    STATUS_STYLE = {
        "Draft":          {"color": "#6b7280", "bg": "#f3f4f6"},
        "Submitted":      {"color": "#1d4ed8", "bg": "#dbeafe"},
        "Under Review":   {"color": "#d97706", "bg": "#fef3c7"},
        "Shortlisted":    {"color": "#059669", "bg": "#d1fae5"},
        "Waitlisted":     {"color": "#7c3aed", "bg": "#ede9fe"},
        "Offer Issued":   {"color": "#0369a1", "bg": "#e0f2fe"},
        "Offer Accepted": {"color": "#065f46", "bg": "#d1fae5"},
        "Offer Declined": {"color": "#991b1b", "bg": "#fee2e2"},
        "Rejected":       {"color": "#991b1b", "bg": "#fee2e2"},
        "Selected":       {"color": "#065f46", "bg": "#d1fae5"},
        "Fee Paid":       {"color": "#065f46", "bg": "#d1fae5"},
    }

    # 1. Fetch all applicant data using the API
    data_list = get_applicant_data()
    if isinstance(data_list, dict) and "error" in data_list:
        context.error = data_list["error"]
        context.applications = []
        return context

    # 2. Determine which application to show
    target_app_id = frappe.form_dict.get('app')
    
    applications = []
    active_app_summary = None
    
    for entry in data_list:
        prof = entry.get("profile", {})
        app_id = prof.get("applicant_id")
        if not app_id: continue
        
        # Load the full doc for detail sections
        app_doc = frappe.get_doc("Applicant", app_id)
        
        status = app_doc.application_status or "Draft"
        style = STATUS_STYLE.get(status, STATUS_STYLE["Draft"])
        
        program_name = frappe.db.get_value("Program", app_doc.program, "program_name") or app_doc.program or "Application"
        program_slug = frappe.db.get_value("Program", app_doc.program, "program_slug") or ""

        summary = {
            "name": app_doc.name,
            "header": {
                "name": app_doc.name,
                "program_name": program_name,
                "program_slug": program_slug,
                "cycle": app_doc.admission_cycle or "—",
                "status": status,
                "status_color": style["color"],
                "status_bg": style["bg"],
                "submitted_on": frappe.utils.formatdate(app_doc.creation, "dd MMM yyyy"),
                "current_stage": app_doc.current_stage or "Pending",
                "applicant_id": app_doc.applicant_id or app_doc.name,
                "merit_score": prof.get("merit_score") or (entry.get("merit")[0].get("total_score") if entry.get("merit") else None)
            },
            "personal": [
                {"label": "Full Name", "value": app_doc.candidate_name},
                {"label": "Date of Birth", "value": frappe.utils.formatdate(app_doc.date_of_birth, "dd MMM yyyy") if app_doc.date_of_birth else None},
                {"label": "Gender", "value": app_doc.gender},
                {"label": "Nationality", "value": app_doc.nationality},
                {"label": "Email", "value": app_doc.email},
                {"label": "Mobile", "value": app_doc.mobile_number},
                {"label": "Religion", "value": app_doc.religion},
                {"label": "Annual Income", "value": app_doc.annual_house_hold_income},
            ],
            "academic": [
                {"label": "10th Percentage", "value": app_doc.class_x_percentage},
                {"label": "10th Board", "value": app_doc.class_x_board},
                {"label": "10th Year", "value": app_doc.class_x_year_of_completion},
                {"label": "12th Percentage", "value": app_doc.hsc_percentage or app_doc.percentage},
                {"label": "12th Board", "value": app_doc.class_xii_board},
                {"label": "12th Year", "value": app_doc.class_xii_year_of_completion},
                {"label": "HSC Group", "value": app_doc.hsc_group},
            ],
            "application": [
                {"label": "Application ID", "value": app_doc.applicant_id or app_doc.name},
                {"label": "Program", "value": app_doc.program},
                {"label": "Admission Cycle", "value": app_doc.admission_cycle},
                {"label": "Fee Status", "value": app_doc.application_fee_status},
                {"label": "Reservation Category", "value": app_doc.reservation_category},
            ],
            "admission_results": entry.get("results", []),
            "merit_list": entry.get("merit", []),
            "can_edit": (status == "Draft"),
            "active_stage": app_doc.current_stage
        }
        
        # Build action buttons for this summary
        actions = []
        if status == "Draft":
            actions.append({"label": "Continue Application", "url": "/application_form/" + app_doc.name, "type": "primary"})
        elif status == "Offer Issued":
            actions.append({"label": "Accept Offer", "url": "/application_form/" + app_doc.name, "type": "success"})
            if program_slug:
                actions.append({"label": "View Program", "url": "/admission/" + program_slug, "type": "outline"})
        else:
            if program_slug:
                actions.append({"label": "View Program", "url": "/admission/" + program_slug, "type": "outline"})
        summary["action_buttons"] = actions

        applications.append(summary)
        
        # Set active app if it matches target or if it's the first one
        if target_app_id == app_doc.name or not active_app_summary:
            active_app_summary = summary

    context.applications = applications
    context.active_app = active_app_summary
    context.no_cache = 1
    context.title = "My Applications"
