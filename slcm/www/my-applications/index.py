import frappe
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.doctype.eligibility_result.eligibility_result import get_applicant_data

login_required = True


def _set_offer_letter_entries(context):
    """Populate context.offer_letter_entries for list view from Offer Letter doctype."""
    context.offer_letter_entries = []
    try:
        applicant_names = [a.get("name") for a in (context.applications or []) if a.get("name")]
        if not applicant_names:
            applicant_names = [
                r["name"] for r in frappe.get_all(
                    "Applicant",
                    filters={"email": frappe.session.user},
                    fields=["name"],
                    ignore_permissions=True
                )
            ]
        if not applicant_names and frappe.db.exists("Applicant", frappe.session.user):
            applicant_names = [frappe.session.user]
        if applicant_names:
            offers = frappe.get_all(
                "Offer Letter",
                filters={"applicant": ["in", applicant_names]},
                fields=["name", "applicant", "program", "campus", "offer_status", "payable_amount"],
                order_by="creation desc",
                ignore_permissions=True
            )
            for o in offers:
                program_name = frappe.db.get_value("Program", o.get("program"), "program_name") or o.get("program") or ""
                campus_name = frappe.db.get_value("Campus", o.get("campus"), "campus_name") or o.get("campus") or ""
                context.offer_letter_entries.append({
                    "offer_name": o.get("name"),
                    "applicant_name": o.get("applicant"),
                    "program": o.get("program"),
                    "program_name": program_name,
                    "campus": o.get("campus"),
                    "campus_name": campus_name,
                    "offer_status": o.get("offer_status") or "Issued",
                    "payable_amount": o.get("payable_amount"),
                })
    except Exception:
        context.offer_letter_entries = []

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect=/my-applications"
        raise frappe.Redirect

    context.no_cache     = 1
    context.title        = "My Application"
    context.show_detail  = False
    context.applicant    = None

    # ── Tab routing ───────────────────────────────────────────────
    _tab = frappe.request.args.get("tab") if frappe.request else None
    context.show_profile = (_tab == "profile")

    # ── Profile context (always loaded for the sidebar avatar) ───
    _user = frappe.session.user
    _user_doc = frappe.db.get_value("User", _user,
                    ["full_name", "user_image"], as_dict=True) or {}
    context.prof_candidate_name  = _user_doc.get("full_name") or ""
    context.prof_user_image      = _user_doc.get("user_image") or ""

    # Try to load personal details from first Applicant record
    _prof_app = None
    try:
        _prof_apps = frappe.get_all("Applicant",
            filters=[["owner","=",_user]],
            fields=["name","candidate_name","date_of_birth","gender","nationality",
                    "religion","mobile_number","alternate_contact","id_proof",
                    "correspondence_address","city","state","pincode",
                    "application_status", "intake_type", "reservation_category",
                    "pwd", "program_level"],
            limit=1, order_by="creation desc")
        if not _prof_apps:
            _prof_apps = frappe.get_all("Applicant",
                filters=[["email","=",_user]],
                fields=["name","candidate_name","date_of_birth","gender","nationality",
                        "religion","mobile_number","alternate_contact","id_proof",
                        "correspondence_address","city","state","pincode",
                        "application_status", "intake_type", "reservation_category",
                        "pwd", "program_level"],
                limit=1, order_by="creation desc")
        if _prof_apps:
            _prof_app = _prof_apps[0]
    except Exception:
        pass

    if _prof_app:
        context.prof_candidate_name  = _prof_app.candidate_name or context.prof_candidate_name
        context.prof_dob             = _prof_app.date_of_birth
        context.prof_gender          = _prof_app.gender
        context.prof_nationality     = _prof_app.nationality
        context.prof_religion        = _prof_app.religion
        context.prof_mobile          = _prof_app.mobile_number
        context.prof_alternate_contact = _prof_app.alternate_contact
        context.prof_id_proof        = _prof_app.id_proof
        context.prof_address         = _prof_app.correspondence_address
        context.prof_city            = _prof_app.city
        context.prof_state           = _prof_app.state
        context.prof_pincode         = _prof_app.pincode
        context.prof_app_status      = _prof_app.application_status
        context.prof_app_name        = _prof_app.name
    else:
        context.prof_dob             = None
        context.prof_gender          = None
        context.prof_nationality     = None
        context.prof_religion        = None
        context.prof_mobile          = None
        context.prof_alternate_contact = None
        context.prof_id_proof        = None
        context.prof_address         = None
        context.prof_city            = None
        context.prof_state           = None
        context.prof_pincode         = None
        context.prof_app_status      = None
        context.prof_app_name        = None

    # ── Detail mode: if ?app= param provided, load that specific application ──
    _app_name = frappe.form_dict.get("app") or ""

    # ── Auto-open application from ?program= param (from admission cards) ──
    program_filter = frappe.form_dict.get("program") or ""
    context.program_filter = program_filter

    if not _app_name and program_filter:
        _found = frappe.db.sql("""
            SELECT a.name FROM `tabApplicant` a
            JOIN `tabProgram` p ON a.program = p.name
            WHERE (a.owner = %s OR a.email = %s) AND (p.program_slug = %s OR p.name = %s)
            LIMIT 1
        """, (frappe.session.user, frappe.session.user, program_filter, program_filter))
        if _found:
            _app_name = _found[0][0]

    # ── Determine active application name for document checklist ──
    doc_lookup_name = _app_name or context.prof_app_name

    # ── Documents Logic (Strictly using Applicant fields) ──────────
    context.app_documents = []
    if doc_lookup_name:
        try:
            # Fetch the actual applicant doc for fields
            target_applicant = frappe.get_doc("Applicant", doc_lookup_name, ignore_permissions=True)

            # Standard fields in Applicant DocType
            standard_checklist = [
                {"label": "10th Certificate", "field": "class_x_marksheet", "required": True},
                {"label": "12th Certificate", "field": "class_xii_marksheet", "required": True},
                {"label": "ID Proof", "field": "id_proof", "required": True},
                {"label": "Photo", "field": "candidate_photo", "required": True},
            ]

            # Optional / Conditional fields
            if target_applicant.reservation_category and target_applicant.reservation_category != "NA":
                standard_checklist.append({"label": "Category Certificate", "field": "caste_certificate", "required": True})
                
            if target_applicant.pwd == "Yes":
                standard_checklist.append({"label": "PwD Certificate", "field": "pwd_certificate", "required": True})
                
            if target_applicant.program_level == "Research Course":
                standard_checklist.append({"label": "Research Proposal", "field": "phd_proposal", "required": True})
                standard_checklist.append({"label": "CV", "field": "cv", "required": True})
            
            # Special case for Karnataka category
            if target_applicant.ka_study_7yrs:
                standard_checklist.append({"label": "Karnataka Study Certificate", "field": "ka_study_7yrs_certificate", "required": True})

            for item in standard_checklist:
                field = item["field"]
                val = target_applicant.get(field)
                
                context.app_documents.append({
                    "document_name": item["label"],
                    "document_type": item["label"],
                    "is_uploaded": bool(val),
                    "file_url": val,
                    "field": field,
                    "source": "field",
                    "required": item["required"]
                })
        except Exception as e:
            frappe.log_error(f"Document checklist error: {e}")

    # ── Portal config (required for theme vars) ──────────────────
    try:
        portal_config = get_portal_config()
        context.portal_config = portal_config
    except Exception:
        portal_config = None
        context.portal_config = None

    if context.show_profile:
        # ── States and Districts ─────────────────────────────────────────
        try:
            context.states = frappe.get_all("State", fields=["name"], order_by="name asc")
            if context.prof_state:
                context.districts = frappe.get_all("District", 
                    filters={"state": context.prof_state},
                    fields=["name"], order_by="name asc")
            else:
                context.districts = []
        except Exception:
            context.states = []
            context.districts = []
        return

    if _app_name:
        # Security: verify ownership
        try:
            applicant = frappe.get_doc("Applicant", _app_name, ignore_permissions=True)
        except frappe.DoesNotExistError:
            context.app_not_found = True
            context.selected_app = None
            return

        # Check access
        _session_user = frappe.session.user
        if applicant.owner != _session_user and applicant.email != _session_user and \
           "Admission Admin" not in frappe.get_roles():
            context.access_denied = True
            context.selected_app = None
            return

        context.selected_app = applicant

        # ── Stage tracker ──────────────────────────────────────────────
        stages_with_state = []
        try:
            all_cycle_stages = frappe.get_all(
                "Admission Cycle Stage",
                filters={
                    "parent": applicant.admission_cycle,
                    "is_enabled": 1
                },
                fields=[
                    "stage_name", "stage_type", "applicable_workflow",
                    "sequence_no", "activate_status", "completed_status", "closed_status"
                ],
                order_by="sequence_no asc",
                ignore_permissions=True
            )

            if all_cycle_stages:
                intake = applicant.intake_type or "External Test"
                filtered_stages = [
                    s for s in all_cycle_stages
                    if s.applicable_workflow == "All" or s.applicable_workflow == intake
                ]
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
                    
                    stages_with_state.append({
                        "name": s.stage_name or s.stage_type,
                        "state": state
                    })
        except Exception as e:
            frappe.log_error(f"Stage tracker context error: {e}")

        if not stages_with_state:
            # Fallback based on common statuses
            statuses = [
                {"name": "Submitted", "activate": "Submitted", "closed": "Rejected"},
                {"name": "Under Review", "activate": "Under Review", "closed": "Rejected"},
                {"name": "Interview", "activate": "Interview Scheduled", "closed": "Interview Rejected"},
                {"name": "Decision", "activate": "Selected", "closed": "Rejected"}
            ]
            current = applicant.get("application_status") or "Draft"
            stop_found = False
            for st in statuses:
                state = "pending"
                if not stop_found:
                    if st["activate"] == current:
                        state = "active"
                        stop_found = True
                    elif st["closed"] == current:
                        state = "closed"
                        stop_found = True
                    else:
                        state = "completed"
                stages_with_state.append({"name": st["name"], "state": state})

        context.stage_tracker = stages_with_state

        # ── Next steps ─────────────────────────────────────────────
        try:
            _pc = frappe.get_doc("Applicant Portal Config")
            _next_steps = []
            if _pc:
                all_steps = (_pc.get("stage_next_steps") or [])
                for step in all_steps:
                    sn = (step.get("stage_name") if hasattr(step,"get") else step.stage_name) or ""
                    if sn.lower() == str(current).lower():
                        _next_steps.append({
                            "text":       (step.get("step_text") if hasattr(step,"get") else step.step_text) or "",
                            "is_link":    (step.get("is_link") if hasattr(step,"get") else step.is_link) or 0,
                            "link_url":   (step.get("link_url") if hasattr(step,"get") else step.link_url) or "",
                            "link_label": (step.get("link_label") if hasattr(step,"get") else step.link_label) or "",
                        })
            if not _next_steps:
                _next_steps = [{"text": "Complete all steps before your cycle deadline", "is_link": 0}]
            context.next_steps = _next_steps
            context.support_name  = _pc.get("support_name") or ""
            context.support_role  = _pc.get("support_role") or ""
            context.support_email = _pc.get("support_email") or ""
            context.campus_image  = _pc.get("hero_image") or ""
        except Exception as ex:
            frappe.log_error(str(ex), "my_applications detail context next steps")

        context.app_narrative = applicant.get("remarks") or ""
        context.submission_date = frappe.utils.format_date(applicant.creation, "MMMM d, yyyy")
        context.app_name_param = _app_name

        # Combined results
        context.all_results = []
        context.all_merit   = []
        try:
            combined_data = get_applicant_data()
            if isinstance(combined_data, list):
                for entry in combined_data:
                    if entry.get("profile", {}).get("applicant_id") == _app_name:
                        context.all_results = entry.get("results") or []
                        context.all_merit   = entry.get("merit") or []
                        context.eligibility_result = entry.get("profile")
                        break
        except Exception: pass

        context.fee_payment_status = applicant.get("application_fee_status") or ""

        # Interview
        context.interview_status = ""
        context.interview_date = ""
        try:
            irows = frappe.get_all("Interview Seat Allocation",
                filters={"applicant": _app_name},
                fields=["interview_date", "interview_time", "interview_slot_status", "re_interview_date", "is_rescheduled"],
                order_by="creation desc", limit=1, ignore_permissions=True)
            if irows:
                ir = irows[0]
                context.interview_status = ir.get("interview_slot_status") or "Scheduled"
                _idate = ir.get("re_interview_date") if (ir.get("is_rescheduled") or ir.get("interview_slot_status") == "Rescheduled") else ir.get("interview_date")
                if _idate:
                    context.interview_date = frappe.utils.format_date(_idate, "d MMM yyyy")
        except Exception: pass

        # Merit
        context.merit_rank = ""
        try:
            mrows = frappe.get_all("Applicant Merit", filters={"applicant": _app_name},
                fields=["overall_rank"], limit=1, ignore_permissions=True)
            if mrows: context.merit_rank = str(mrows[0].get("overall_rank") or "")
        except Exception: pass

        # Seat
        context.seat_status = ""
        try:
            srows = frappe.get_all("Seat Allocation", filters={"applicant": _app_name},
                fields=["status"], limit=1, ignore_permissions=True)
            if srows: context.seat_status = (srows[0].get("status") or "").strip()
        except Exception: pass

        # Entrance test
        try:
            et_rows = frappe.get_all("Entrance Test Seat Allocation",
                filters={"applicant": _app_name}, fields=["*"], limit=1, ignore_permissions=True)
            if et_rows:
                et_doc = frappe.get_doc("Entrance Test Seat Allocation", et_rows[0].name, ignore_permissions=True)
                context.et_doc = et_doc
                context.et_is_rescheduled = (et_doc.is_rescheduled == 1 or et_doc.entrance_test_status == "Rescheduled")
                context.et_show_result = (et_doc.entrance_test_status in ["Attended", "Absent"] and et_doc.result_published == 1)
                context.et_preferences = [{"provider": p.provider, "center_name": p.center_name, "center_address": p.center_address} for p in (et_doc.re_assigned_preferences if context.et_is_rescheduled else et_doc.assigned_preferences)]
                context.et_doc_json = frappe.as_json(et_doc.as_dict())
        except Exception: pass

        # Interview details
        try:
            i_rows = frappe.get_all("Interview Seat Allocation",
                filters={"applicant": _app_name}, fields=["*"], limit=1, ignore_permissions=True)
            if i_rows:
                i_doc = frappe.get_doc("Interview Seat Allocation", i_rows[0].name, ignore_permissions=True)
                context.interview_doc = i_doc
                context.interview_is_rescheduled = (i_doc.is_rescheduled == 1 or i_doc.interview_slot_status == "Rescheduled")
                context.interview_show_result = (i_doc.interview_status in ["Attended", "Absent", "Selected", "Rejected"] and i_doc.result_published == 1)
        except Exception: pass

        context.show_detail = True
        context.title = f"Application Details: {_app_name}"
        return

    # Default List View
    # Status styling
    STATUS_STYLE = {
        "Draft":          {"color": "#6b7280", "bg": "#f3f4f6"},
        "Submitted":      {"color": "#1d4ed8", "bg": "#dbeafe"},
        "Merit Published": {"color": "#0369a1", "bg": "#e0f2fe"},
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

    data_list = get_applicant_data()
    if isinstance(data_list, dict) and "error" in data_list:
        context.error = data_list["error"]
        context.applications = []
        # Still fetch offer letters so they show even when API returns error
        _set_offer_letter_entries(context)
        return context

    applications = []
    for entry in data_list:
        prof = entry.get("profile", {})
        app_id = prof.get("applicant_id")
        if not app_id: continue
        app_doc = frappe.get_doc("Applicant", app_id)
        
        status = app_doc.application_status or "Draft"
        style = STATUS_STYLE.get(status, STATUS_STYLE["Draft"])
        
        program_name = frappe.db.get_value("Program", app_doc.program, "program_name") or app_doc.program
        program_slug = frappe.db.get_value("Program", app_doc.program, "program_slug") or ""

        summary = {
            "name": app_doc.name,
            "header": {
                "program_name": program_name,
                "applicant_id": app_doc.name,
                "status": status,
                "status_color": style["color"],
                "status_bg": style["bg"],
                "submitted_on": frappe.utils.formatdate(app_doc.creation, "dd MMM yyyy"),
                "cycle": app_doc.admission_cycle
            },
            "personal": [
                {"label": "Full Name", "value": app_doc.candidate_name}
            ]
        }
        applications.append(summary)

    context.applications = applications
    return context
