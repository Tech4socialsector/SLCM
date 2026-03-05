import frappe

login_required = True


def get_context(context):
    frappe.log_error("my-applications start", "Portal Debug")

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect=/my-applications"
        )
        raise frappe.Redirect

    # Portal config — plain dict for Jinja .get()
    try:
        from slcm.admission.utils.portal import get_portal_config
        cfg = get_portal_config()
        context.portal_config = (
            cfg.as_dict() if hasattr(cfg, "as_dict") else dict(cfg)
        )
        frappe.log_error(
            "portal_config primary=" +
            str(context.portal_config.get("primary_color")),
            "Portal Debug"
        )
    except Exception as e:
        frappe.log_error("portal_config failed: " + str(e), "Portal Debug")
        context.portal_config = {}

    context.candidate_name = (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user.split("@")[0].replace(".", " ").title()
    )

    apps = []

    # 1. Fetch structured applications (Admission Application)
    try:
        struct_apps = frappe.get_all(
            "Admission Application",
            filters={"owner": frappe.session.user},
            fields=["name", "program", "program_name", "status",
                    "application_date", "admission_cycle",
                    "eligibility_status", "merit_score"],
            order_by="creation desc"
        )
        for a in struct_apps:
            a["_doctype"] = "Admission Application"
            apps.append(a)
    except Exception as e:
        frappe.log_error("struct_apps failed: " + str(e), "Portal Debug")

    # 2. Fetch legacy/direct applications (Applicant)
    try:
        legacy_apps = frappe.get_all(
            "Applicant",
            filters={"owner": frappe.session.user},
            fields=["name", "program", "application_status as status",
                    "creation as application_date", "admission_cycle",
                    "current_stage as eligibility_status", "applicant_id"],
            order_by="creation desc"
        )
        # If email strategy needed
        if not legacy_apps:
            legacy_apps = frappe.get_all(
                "Applicant",
                filters={"email": frappe.session.user},
                fields=["name", "program", "application_status as status",
                        "creation as application_date", "admission_cycle",
                        "current_stage as eligibility_status", "applicant_id"],
                order_by="creation desc"
            )

        for a in legacy_apps:
            # Avoid duplicates if they exist in both (unlikely but safe)
            if not any(x["name"] == a["name"] for x in apps):
                a["_doctype"] = "Applicant"
                a["applicant_id"] = a.get("applicant_id") or a["name"]
                apps.append(a)
    except Exception as e:
        frappe.log_error("legacy_apps failed: " + str(e), "Portal Debug")

    STATUS_STYLE = {
        "Draft":        {"color": "#6b7280", "bg": "#f3f4f6"},
        "Submitted":    {"color": "#1d4ed8", "bg": "#dbeafe"},
        "Under Review": {"color": "#d97706", "bg": "#fef3c7"},
        "Shortlisted":  {"color": "#059669", "bg": "#d1fae5"},
        "Waitlisted":   {"color": "#7c3aed", "bg": "#ede9fe"},
        "Offered":      {"color": "#0369a1", "bg": "#e0f2fe"},
        "Accepted":     {"color": "#065f46", "bg": "#d1fae5"},
        "Rejected":     {"color": "#991b1b", "bg": "#fee2e2"},
        "Withdrawn":    {"color": "#6b7280", "bg": "#f3f4f6"},
    }

    for app in apps:
        if not app.get("program_name") and app.get("program"):
            app["program_name"] = (
                frappe.db.get_value(
                    "Program", app.program, "program_name"
                ) or app.program
            )
        sc = STATUS_STYLE.get(
            app.get("status", "Draft"), STATUS_STYLE["Draft"]
        )
        app["status_color"] = sc["color"]
        app["status_bg"]    = sc["bg"]
        app["formatted_date"] = (
            frappe.utils.formatdate(
                app.application_date, "dd MMM yyyy"
            ) if app.get("application_date") else "—"
        )
        app["program_slug"] = (
            frappe.db.get_value(
                "Program", app.program, "program_slug"
            ) or ""
        ) if app.get("program") else ""

    notifications = []
    try:
        applicant_names = frappe.get_all(
            "Applicant",
            filters={"email": frappe.session.user},
            pluck="name"
        )
        if applicant_names:
            notifications = frappe.get_all(
                "Applicant Notification",
                filters={"applicant": ["in", applicant_names],
                         "is_read": 0},
                fields=["name", "applicant",
                        "message", "notification_type",
                        "is_read", "created_on as creation"],
                order_by="created_on desc",
                limit=20
            )
    except Exception as e:
        frappe.log_error("notifications: " + str(e), "Portal Debug")

    context.applications  = apps
    context.notifications = notifications
    context.unread_count  = len(notifications)
    context.active_cycle  = frappe.db.get_value(
        "Admission Cycle", {"status": "Active"}, "name"
    ) or ""
    context.no_cache = 1
    context.title    = "My Applications"

    frappe.log_error(
        "my-applications done. apps=" + str(len(apps)) +
        " candidate=" + str(context.candidate_name),
        "Portal Debug"
    )
