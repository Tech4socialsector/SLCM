import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        context.is_guest = True
        return context

    context.is_guest = False
    context.active_page = "support"

    student_name = _get_student_name()
    if not student_name:
        context.no_student = True
        _set_nav_defaults(context)
        context.past_tickets = []
        return context

    context.no_student = False

    try:
        student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
        _set_student_nav(context, student)

        # ── Past support tickets ───────────────────────────────
        try:
            tickets = frappe.get_all(
                "Communication",
                filters=[
                    ["reference_doctype", "=", "Student Master"],
                    ["reference_name", "=", student_name],
                    ["communication_type", "=", "Communication"],
                ],
                fields=["name", "subject", "status", "communication_date", "creation"],
                order_by="creation desc",
                limit=20,
                ignore_permissions=True,
            )
            # Enrich status display
            for t in tickets:
                st = t.status or "Open"
                t["status_color"] = {
                    "Open":     "var(--sp-warning)",
                    "Replied":  "var(--sp-info)",
                    "Resolved": "var(--sp-success)",
                    "Closed":   "var(--sp-text-4)",
                }.get(st, "var(--sp-warning)")
                t["status_bg"] = {
                    "Open":     "var(--sp-warning-bg)",
                    "Replied":  "var(--sp-info-bg)",
                    "Resolved": "var(--sp-success-bg)",
                    "Closed":   "var(--sp-bg)",
                }.get(st, "var(--sp-warning-bg)")
                # Strip category prefix from display subject
                t["display_subject"] = t.subject or "—"
                t["category"] = ""
                if t.subject and t.subject.startswith("[") and "]" in t.subject:
                    end = t.subject.index("]")
                    t["category"] = t.subject[1:end]
                    t["display_subject"] = t.subject[end + 2:].strip()
            context.past_tickets = tickets
        except Exception:
            context.past_tickets = []

    except Exception as e:
        frappe.log_error(f"Student Portal Support error: {e}", "Student Portal")
        context.portal_error = str(e)
        _set_nav_defaults(context)
        context.past_tickets = []

    return context


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_student_name():
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


def _set_student_nav(context, student):
    full_name = " ".join(
        filter(None, [student.first_name, student.middle_name, student.last_name])
    )
    context.student_name = full_name or student.name
    context.student_id = student.registration_id or student.name
    context.student_photo = student.passport_size_photo or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = (
        frappe.db.get_value("Cohort", student.programme, "cohort_name")
        or student.programme
        or ""
    )
    context.department = student.department or ""
    context.batch_year = student.batch_year or ""


def _set_nav_defaults(context):
    user = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
    context.student_name = (user_doc.full_name if user_doc else "") or user.split("@")[0]
    context.student_id = ""
    context.student_photo = (user_doc.user_image if user_doc else "") or ""
    context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
    context.programme_name = ""
    context.department = ""
    context.batch_year = ""
