import frappe
from slcm.admission.doctype.eligibility_result.eligibility_result import get_applicant_data
from slcm.admission.utils.portal import get_portal_config
from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard, get_applied_scholarships_for_dashboard

no_cache = 1

def get_context(context):
    context.portal_config = get_portal_config()
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.unauthorized = True
        return context

    # ── Application cards (new) ──────────────────────────────────
    STATUS_STYLE = {
        "Draft":          {"color": "#6b7280", "bg": "#f3f4f6"},
        "Submitted":      {"color": "#1d4ed8", "bg": "#dbeafe"},
        "Merit Published": {"color": "#0369a1", "bg": "#e0f2fe"},
        "Under Review":   {"color": "#d97706", "bg": "#fef3c7"},
        "Shortlisted":    {"color": "#059669", "bg": "#d1fae5"},
        "Waitlisted":     {"color": "#7c3aed", "bg": "#ede9fe"},
        "Offer Issued":   {"color": "#0369a1", "bg": "#e0f2fe"},
        "Offer Accepted": {"color": "#065f46", "bg": "#d1fae5"},
        "Rejected":       {"color": "#dc2626", "bg": "#fee2e2"},
        "Selected":       {"color": "#065f46", "bg": "#d1fae5"},
    }

    applicants = frappe.get_all(
        "Applicant",
        filters=[["owner", "=", frappe.session.user]],
        fields=["name", "candidate_name", "program", "admission_cycle",
                "application_status", "creation", "current_stage"],
        order_by="creation desc"
    )

    cards = []
    for a in applicants:
        program_name = frappe.db.get_value(
            "Program", a.program, "program_name"
        ) or a.program or "—"

        intake = frappe.db.get_value(
            "Program", a.program, "intake_type"
        ) or "All"

        # Get current active stage from cycle
        curr_stage = a.current_stage or ""
        if not curr_stage and a.admission_cycle:
            try:
                from slcm.admission.utils.stage_control import get_current_stage
                s = get_current_stage(a.admission_cycle, intake)
                curr_stage = s.stage_name if s else "—"
            except Exception:
                curr_stage = "—"

        status = a.application_status or "Draft"
        sc = STATUS_STYLE.get(status, STATUS_STYLE["Draft"])

        cards.append({
            "name":         a.name,
            "program_name": program_name,
            "cycle":        a.admission_cycle or "—",
            "status":       status,
            "color":        sc["color"],
            "bg":           sc["bg"],
            "intake_type":  intake,
            "stage":        curr_stage,
            "submitted_on": frappe.utils.formatdate(a.creation, "dd MMM yyyy"),
        })

    context.application_cards = cards
    context.has_applications = len(cards) > 0

    # ── Existing merit/scholarship data ─────────────────────────
    data = get_applicant_data()
    if isinstance(data, dict) and "error" in data:
        context.error = data["error"]
    else:
        context.applicant_data = data

    # ── Current user info ─────────────────────────────────────────
    context.nav_user     = frappe.session.user or ''
    context.is_guest     = context.nav_user == 'Guest' or not context.nav_user
    context.user_display = frappe.db.get_value(
        "User", context.nav_user, "full_name"
    ) or context.nav_user.split("@")[0] if context.nav_user else ''
    context.user_first   = (context.user_display or 'U')[0].upper()

    # ── All applicant records for this user (all cycles) ──────────
    try:
        _user = context.nav_user
        # Query by owner
        apps_by_owner = frappe.get_all(
            "Applicant",
            filters={"owner": _user},
            fields=[
                "name", "candidate_name as applicant_name", "program",
                "application_status", "current_stage",
                "admission_cycle", "creation", "modified", "campus"
            ],
            ignore_permissions=True
        )
        
        # Query by email
        apps_by_email = frappe.get_all(
            "Applicant",
            filters={"email": _user},
            fields=[
                "name", "candidate_name as applicant_name", "program",
                "application_status", "current_stage",
                "admission_cycle", "creation", "modified", "campus"
            ],
            ignore_permissions=True
        )
        
        # Combine and deduplicate
        combined = {a.name: a for a in (apps_by_owner + apps_by_email)}
        context.my_applications = sorted(
            combined.values(), 
            key=lambda x: x.modified, 
            reverse=True
        )[:10]

        for app in context.my_applications:
            app["program_name"] = frappe.db.get_value("Program", app.program, "program_name") or app.program
            # Fetch current stage name if current_stage is a link/ID
            if app.current_stage:
                app["current_stage_name"] = frappe.db.get_value("Stage Master", app.current_stage, "stage_name") or app.current_stage
            else:
                app["current_stage_name"] = ""
    except Exception as e:
        frappe.log_error(f"Dashboard applications query failed: {e}", "Dashboard Fix")
        context.my_applications = []

    # ── Scholarship Schemes (show if any active schemes exist) ─────
    try:
        available_scholarships = []
        applied_scholarships = []
        entrance_tests = []
        seen_schemes = set()
        seen_applications = set()
        
        for app in context.my_applications:
            # Get Entrance Test details
            try:
                etrows = frappe.get_all(
                    "Entrance Test Seat Allocation",
                    filters={"applicant": app.name},
                    fields=["entrance_test_name", "center_name",
                            "center_address", "seat_number",
                            "allocation_status", "name"],
                    order_by="creation desc", limit=1,
                    ignore_permissions=True
                )
                if etrows:
                    et = etrows[0]
                    test_name = et.get("entrance_test_name") or ""
                    test_date = ""
                    test_time = ""
                    if test_name:
                        try:
                            td = frappe.get_doc("Entrance Test List", test_name, ignore_permissions=True)
                            test_date = frappe.utils.format_date(str(td.get("test_date") or "")[:10], "MMMM d, yyyy") if td.get("test_date") else ""
                            test_time = str(td.get("test_time") or "")
                        except Exception: pass
                    
                    entrance_tests.append({
                        "app_id": app.name,
                        "program_name": app.program_name,
                        "test_name": test_name,
                        "test_date": test_date,
                        "test_time": test_time,
                        "center_name": et.get("center_name") or "",
                        "center_address": et.get("center_address") or "",
                        "seat_number": et.get("seat_number") or "",
                        "admit_status": et.get("allocation_status") or "",
                        "admit_card_url": f"/api/method/slcm.admission.utils.web.download_admit_card?admit_card={et.get('name')}"
                    })
            except Exception: pass

            # Get Applied Scholarships
            apps = get_applied_scholarships_for_dashboard(app.name)
            for a in apps:
                if a.name not in seen_applications:
                    # Enrich with scheme name
                    a["scheme_name"] = frappe.db.get_value("Scholarship Scheme", a.scholarship_scheme, "scheme_name") or a.scholarship_scheme
                    applied_scholarships.append(a)
                    seen_applications.add(a.name)

            if not all([app.admission_cycle, app.campus, app.program]):
                continue
                
            schemes = get_available_scholarships_for_dashboard(
                app.name, 
                app.admission_cycle, 
                app.campus, 
                app.program, 
                [app.application_status] if app.application_status else []
            )
            for s in schemes:
                if s.name not in seen_schemes:
                    available_scholarships.append(s)
                    seen_schemes.add(s.name)
        
        context.scholarships = available_scholarships[:5]
        context.applied_scholarships = sorted(applied_scholarships, key=lambda x: x.creation, reverse=True)
        context.entrance_tests = entrance_tests
    except Exception as e:
        frappe.log_error(f"Scholarship/ET fetch failed: {e}", "Dashboard Fix")
        context.scholarships = []
        context.applied_scholarships = []
        context.entrance_tests = []

    # ── Portal config extras ───────────────────────────────────────
    try:
        _pc = context.portal_config  # already fetched above
        context.portal_mission = (
            _pc.get("portal_mission") if _pc and _pc.get else
            getattr(_pc, "portal_mission", "")
        ) or ""
        context.value_cards = (
            _pc.get("value_cards") if _pc and _pc.get else
            getattr(_pc, "value_cards", [])
        ) or []
    except Exception:
        context.portal_mission = ""
        context.value_cards    = []

    # ── Unread messages count (placeholder — Messages not built) ───
    context.unread_messages = 0

    # ── Hero image from portal config ─────────────────────────────
    try:
        context.dashboard_hero_image = (
            _pc.get("hero_image") if _pc and _pc.get else
            getattr(_pc, "hero_image", "")
        ) or ""
    except Exception:
        context.dashboard_hero_image = ""

    # ── Profile data ─────────────────────────────────────────────────
    try:
        _user = frappe.session.user
        if _user and _user != 'Guest':
            _ap = frappe.get_all(
                'Applicant',
                filters={'email': _user},
                fields=[
                    'name', 'candidate_name', 'email', 'mobile_number',
                    'date_of_birth', 'gender', 'nationality', 'religion',
                    'father_name', 'mother_name',
                    'correspondence_address', 'city', 'state', 'pincode',
                    'application_status', 'candidate_photo',
                    'reservation_category', 'pwd',
                ],
                limit=1,
                order_by='creation desc'
            )
            if not _ap:
                _ap = frappe.get_all(
                    'Applicant',
                    filters={'owner': _user},
                    fields=[
                        'name', 'candidate_name', 'email', 'mobile_number',
                        'date_of_birth', 'gender', 'nationality', 'religion',
                        'father_name', 'mother_name',
                        'correspondence_address', 'city', 'state', 'pincode',
                        'application_status', 'candidate_photo',
                        'reservation_category', 'pwd',
                    ],
                    limit=1,
                    order_by='creation desc'
                )
            context.profile_data = _ap[0] if _ap else {}
            context.profile_data_json = frappe.as_json(context.profile_data)
        else:
            context.profile_data = {}
            context.profile_data_json = "{}"
    except Exception:
        context.profile_data = {}
        context.profile_data_json = "{}"

    # ── Derive first name for navbar ──────────────────────────────────
    try:
        _fullname = context.profile_data.get('candidate_name', '') if context.profile_data else ''
        context.first_name = _fullname.split()[0] if _fullname else ''
    except Exception:
        context.first_name = ''

    # ── Documents Logic (Mirror index.py logic - Strictly Applicant fields) ──
    context.app_documents = []
    if context.profile_data and context.profile_data.get("name"):
        try:
            doc_lookup_name = context.profile_data.get("name")
            target_applicant = frappe.get_doc("Applicant", doc_lookup_name, ignore_permissions=True)

            standard_checklist = [
                {"label": "10th Certificate", "field": "class_x_marksheet", "required": True},
                {"label": "12th Certificate", "field": "class_xii_marksheet", "required": True},
                {"label": "ID Proof", "field": "id_proof", "required": True},
                {"label": "Photo", "field": "candidate_photo", "required": True},
            ]

            if target_applicant.reservation_category and target_applicant.reservation_category != "NA":
                standard_checklist.append({"label": "Category Certificate", "field": "caste_certificate", "required": True})
                
            if target_applicant.pwd == "Yes":
                standard_checklist.append({"label": "PwD Certificate", "field": "pwd_certificate", "required": True})
                
            if target_applicant.program_level == "Research Course":
                standard_checklist.append({"label": "Research Proposal", "field": "phd_proposal", "required": True})
                standard_checklist.append({"label": "CV", "field": "cv", "required": True})
            
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
            frappe.log_error(f"Admission Dashboard doc error: {e}")

    # ── Active panel from URL param ───────────────────────────────────
    context.active_panel = frappe.form_dict.get('panel', 'applications')

    # ── States and Districts ─────────────────────────────────────────
    try:
        context.states = frappe.get_all("State", fields=["name"], order_by="name asc")
        # Pre-load districts if state is already set
        if context.profile_data and context.profile_data.get("state"):
            context.districts = frappe.get_all("District", 
                filters={"state": context.profile_data.get("state")},
                fields=["name"], order_by="name asc")
        else:
            context.districts = []
    except Exception:
        context.states = []
        context.districts = []

    return context
