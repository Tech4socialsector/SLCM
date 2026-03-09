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
                "application_status", "intake_type", "creation", "current_stage"],
        order_by="creation desc"
    )

    cards = []
    for a in applicants:
        program_name = frappe.db.get_value(
            "Program", a.program, "program_name"
        ) or a.program or "—"

        # Get current active stage from cycle
        curr_stage = a.current_stage or ""
        if not curr_stage and a.admission_cycle:
            try:
                from slcm.admission.utils.stage_control import get_current_stage
                intake = a.intake_type or frappe.db.get_value(
                    "Program", a.program, "intake_type"
                ) or "All"
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
            "intake_type":  a.intake_type or "—",
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

    return context
