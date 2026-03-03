import frappe

login_required = True

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config

    context.portal_config = get_portal_config()

    user = frappe.session.user

    # All applicant records for this user
    applicants = frappe.get_all(
        "Applicant",
        filters={"email": user},
        fields=["name", "program", "admission_cycle", "application_status",
                "applicant_id", "candidate_name", "program_level",
                "application_fee_status"]
    )

    result = []
    for a in applicants:
        program_name = frappe.db.get_value(
            "Program", a.program, "program_full_name"
        ) or frappe.db.get_value("Program", a.program, "name") or a.program

        # Stage trackers
        stages = frappe.get_all(
            "Applicant Stage Tracker",
            filters={"applicant": a.name},
            fields=["stage_name", "stage_type", "sequence",
                    "status", "score", "is_published"],
            order_by="sequence asc"
        )

        current_stage = next(
            (s for s in stages if s.status == "In Progress"), None
        )
        last_passed = next(
            (s for s in reversed(stages) if s.status == "Passed"), None
        )

        fee_status = a.get("application_fee_status") or ""
        show_pay = (
            fee_status not in ["Paid", "Waived"]
            and a.application_status in ["Applied", "Draft"]
            and not context.portal_config.get("skip_fee_check_for_testing")
        )

        result.append({
            "applicant":           a.name,
            "program":             a.program,
            "program_name":        program_name,
            "admission_cycle":     a.admission_cycle,
            "application_status":  a.application_status or "Draft",
            "applicant_id":        a.applicant_id or a.name,
            "candidate_name":      a.candidate_name or user,
            "stages":              stages,
            "current_stage_name":  current_stage.stage_name if current_stage
                                   else (last_passed.stage_name if last_passed else ""),
            "fee_status":          fee_status,
            "show_pay_fee":        show_pay,
            "allow_pdf_download":  context.portal_config.get("allow_pdf_download", 1),
            "show_stage_progress": context.portal_config.get("show_stage_progress", 1),
            "progress_style":      context.portal_config.get("progress_style", "Steps"),
        })

    # Applicant Notifications
    notifications = []
    if context.portal_config.get("enable_portal_notifications"):
        try:
            # Get the applicant names for this user
            applicant_names = [a["applicant"] for a in result]
            if applicant_names:
                # Field names from JSON: applicant, notification_type, is_read, created_on, message
                notifications = frappe.get_all(
                    "Applicant Notification",
                    filters={
                        "applicant": ["in", applicant_names],
                        "is_read": 0
                    },
                    fields=["name", "applicant", "message",
                            "notification_type", "created_on", "is_read"],
                    order_by="created_on desc",
                    limit=20
                )
                # Ensure each notification has a 'title' for the template
                for n in notifications:
                    n["title"] = n.get("notification_type", "Update")
                    n["creation"] = n.get("created_on")
        except Exception as e:
            frappe.log_error(f"get notifications failed: {e}", "Portal")
            notifications = []

    context.applications    = result
    context.notifications   = notifications
    context.unread_count    = len(notifications)
    context.candidate_name  = frappe.db.get_value("User", user, "full_name") or user
    context.no_cache        = 1
    context.title           = "My Applications"
