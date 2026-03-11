import frappe
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.doctype.eligibility_result.eligibility_result import get_applicant_data

login_required = True

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
            WHERE a.owner = %s AND (p.program_slug = %s OR p.name = %s)
            LIMIT 1
        """, (frappe.session.user, program_filter, program_filter))
        if _found:
            _app_name = _found[0][0]

    # ── Determine active application name for document checklist ──
    doc_lookup_name = _app_name or context.prof_app_name

    # ── Documents Logic (Reusable for Detail and Profile) ──────────
    if doc_lookup_name:
        try:
            uploaded_docs = frappe.get_all(
                "Applicant Document",
                filters={"applicant": doc_lookup_name},
                fields=["name", "document_type", "file", "is_verified"],
                ignore_permissions=True
            )
            doc_record_map = {d.document_type: d for d in uploaded_docs}

            # Fetch the actual applicant doc for fields
            target_applicant = frappe.get_doc("Applicant", doc_lookup_name, ignore_permissions=True)

            checklist_items = [
                {"label": "10th Certificate", "field": "class_x_marksheet", "required": True},
                {"label": "12th Certificate", "field": "class_xii_marksheet", "required": True},
                {"label": "ID Proof", "field": "id_proof", "required": True},
                {"label": "Photo", "field": "candidate_photo", "required": True},
            ]

            if target_applicant.intake_type == "CLAT":
                checklist_items.append({"label": "CLAT Scorecard", "field": None, "required": True, "type": "CLAT Scorecard"})
            
            if target_applicant.reservation_category and target_applicant.reservation_category != "NA":
                checklist_items.append({"label": "Category Certificate", "field": "caste_certificate", "required": True})
                
            if target_applicant.pwd == "Yes":
                checklist_items.append({"label": "PwD Certificate", "field": "pwd_certificate", "required": True})
                
            if target_applicant.program_level == "Research Course":
                checklist_items.append({"label": "Research Proposal", "field": "phd_proposal", "required": True})
                checklist_items.append({"label": "CV", "field": "cv", "required": True})
            elif target_applicant.program_level == "PG":
                checklist_items.append({"label": "Degree Certificate", "field": None, "required": True, "type": "Degree Certificate"})

            context.app_documents = []
            seen_types = set()

            for item in checklist_items:
                dtype = item.get("type") or item["label"]
                field = item.get("field")
                is_uploaded = False
                file_url = None
                source = "field"
                doc_name = None

                if field and target_applicant.get(field):
                    is_uploaded = True
                    file_url = target_applicant.get(field)
                elif doc_record_map.get(dtype):
                    is_uploaded = True
                    file_url = doc_record_map[dtype].file
                    source = "record"
                    doc_name = doc_record_map[dtype].name
                
                context.app_documents.append({
                    "document_name": item["label"],
                    "document_type": dtype,
                    "is_uploaded": is_uploaded,
                    "file_url": file_url,
                    "field": field,
                    "doc_name": doc_name,
                    "source": source,
                    "required": item.get("required", False)
                })
                seen_types.add(dtype)

            for dtype, doc in doc_record_map.items():
                if dtype not in seen_types:
                    context.app_documents.append({
                        "document_name": dtype,
                        "document_type": dtype,
                        "is_uploaded": True,
                        "file_url": doc.file,
                        "field": None,
                        "doc_name": doc.name,
                        "source": "record",
                        "required": False
                    })
        except Exception as e:
            frappe.log_error(f"Document checklist error: {e}")
            context.app_documents = []

    # ── Portal config (required for theme vars) ──────────────────
    try:
        from slcm.admission.utils.portal import get_portal_config
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
                    "sequence_no", "application_status"
                ],
                order_by="sequence_no asc",
                ignore_permissions=True
            )

            if all_cycle_stages:
                intake = applicant.intake_type or "CLAT"
                filtered_stages = [
                    s for s in all_cycle_stages
                    if s.applicable_workflow == "All" or s.applicable_workflow == intake
                ]
                current_status = applicant.application_status
                active_index = -1
                for i, s in enumerate(filtered_stages):
                    if s.application_status == current_status:
                        active_index = i
                        break
                for i, s in enumerate(filtered_stages):
                    state = "pending"
                    if active_index != -1:
                        if i < active_index: state = "completed"
                        elif i == active_index: state = "active"
                    stages_with_state.append({
                        "name": s.stage_name or s.stage_type,
                        "state": state
                    })
        except Exception as e:
            frappe.log_error(f"Stage tracker context error: {e}")

        if not stages_with_state:
            statuses = ["Submitted", "Under Review", "Interview", "Decision"]
            current = applicant.get("application_status") or "Draft"
            found = False
            for st in statuses:
                if st.lower() == current.lower() and not found:
                    state = "active"; found = True
                elif not found: state = "completed"
                else: state = "pending"
                stages_with_state.append({"name": st, "state": state})

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
                        break
        except Exception: pass

        context.fee_payment_status = applicant.get("application_fee_status") or ""

        # Interview
        context.interview_status = ""
        try:
            irows = frappe.get_all("Interview Seat Allocation",
                filters={"applicant": _app_name},
                fields=["interview_date", "interview_time", "interview_slot_status"],
                order_by="creation desc", limit=1, ignore_permissions=True)
            if irows:
                ir = irows[0]
                context.interview_status = ir.get("interview_slot_status") or "Scheduled"
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
    data_list = get_applicant_data()
    if isinstance(data_list, dict) and "error" in data_list:
        context.error = data_list["error"]
        context.applications = []
        return context

    applications = []
    for entry in data_list:
        prof = entry.get("profile", {})
        app_id = prof.get("applicant_id")
        if not app_id: continue
        app_doc = frappe.get_doc("Applicant", app_id)
        program_name = frappe.db.get_value("Program", app_doc.program, "program_name") or app_doc.program
        applications.append({
            "name": app_doc.name,
            "header": {
                "program_name": program_name,
                "applicant_id": app_doc.name,
                "status": app_doc.application_status or "Draft",
                "submitted_on": frappe.utils.formatdate(app_doc.creation, "dd MMM yyyy"),
                "cycle": app_doc.admission_cycle
            },
            "personal": [{"label": "Full Name", "value": app_doc.candidate_name}]
        })
    context.applications = applications
    return context
