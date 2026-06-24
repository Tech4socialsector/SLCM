import frappe
from slcm.utils.faculty_portal import get_faculty_name


@frappe.whitelist()
def get_faculty_notifications():
    """Return notifications for the logged-in faculty member."""
    user = frappe.session.user
    if user == "Guest":
        return {"notifications": [], "count": 0, "urgent_count": 0}

    notifications = []

    # ── Portal Announcements ────────────────────────────────────────
    try:
        announcements = frappe.get_all(
            "Portal Announcement",
            filters={"is_published": 1},
            fields=["name", "title", "category", "priority"],
            order_by="creation desc",
            limit=10,
            ignore_permissions=True,
        )
        for ann in announcements:
            notifications.append({
                "type": "announcement",
                "title": ann.title,
                "category": ann.category or "Announcement",
                "priority": ann.priority or "Normal",
                "icon": "priority_high" if ann.priority == "Urgent" else "campaign",
                "link": "/faculty-portal/communication",
                "subtitle": "",
            })
    except Exception:
        pass

    # ── Pending attendance sessions ─────────────────────────────────
    try:
        faculty_name = get_faculty_name()
        if faculty_name:
            today = frappe.utils.today()
            co_names = frappe.get_all(
                "Course Offering",
                filters={"faculty": faculty_name, "status": ["in", ["Open", "Active"]]},
                pluck="name",
                ignore_permissions=True,
            )
            if co_names:
                pending = frappe.db.count(
                    "Attendance Session",
                    filters={
                        "course_offering": ["in", co_names],
                        "attendance_marked": 0,
                        "session_date": ["<=", today],
                        "session_status": "Scheduled",
                    },
                )
                if pending:
                    notifications.append({
                        "type": "attendance",
                        "title": f"{pending} attendance session{'s' if pending > 1 else ''} pending",
                        "category": "Attendance",
                        "priority": "Important" if pending > 2 else "Normal",
                        "icon": "pending_actions",
                        "link": "/faculty-portal/attendance",
                        "subtitle": "Click to mark attendance",
                    })
    except Exception:
        pass

    # ── Pending condonation requests ────────────────────────────────
    try:
        faculty_name = faculty_name if 'faculty_name' in dir() else get_faculty_name()
        if faculty_name:
            co_names = co_names if 'co_names' in dir() else []
            if co_names:
                cond_pending = frappe.db.count(
                    "Student Attendance Condonation",
                    filters={
                        "course_offering": ["in", co_names],
                        "final_status": "Pending",
                        "faculty_recommendation": ["in", ["", None, "Pending"]],
                    },
                )
                if cond_pending:
                    notifications.append({
                        "type": "condonation",
                        "title": f"{cond_pending} condonation request{'s' if cond_pending > 1 else ''} pending",
                        "category": "Condonation",
                        "priority": "Important",
                        "icon": "rate_review",
                        "link": "/faculty-portal/attendance",
                        "subtitle": "Awaiting your recommendation",
                    })
    except Exception:
        pass

    count = len(notifications)
    urgent_count = sum(1 for n in notifications if n.get("priority") == "Urgent")

    # Pending attendance sessions count (used by sidebar quick-stat)
    pending_sessions = 0
    try:
        fn = get_faculty_name()
        if fn:
            _co = frappe.get_all(
                "Course Offering",
                filters={"faculty": fn, "status": ["in", ["Open", "Active"]]},
                pluck="name",
                ignore_permissions=True,
            )
            if _co:
                pending_sessions = frappe.db.count(
                    "Attendance Session",
                    filters={
                        "course_offering": ["in", _co],
                        "attendance_marked": 0,
                        "session_date": ["<=", frappe.utils.today()],
                        "session_status": "Scheduled",
                    },
                )
    except Exception:
        pass

    return {
        "notifications": notifications[:15],
        "count": count,
        "urgent_count": urgent_count,
        "pending_sessions": pending_sessions,
    }


def _assert_session_owned_by_faculty(session, faculty_name):
    """Raise PermissionError if the session's course offering does not belong to this faculty."""
    faculty_co_names = frappe.get_all(
        "Course Offering",
        filters={"faculty": faculty_name},
        pluck="name",
        ignore_permissions=True,
    )
    if session.course_offering and session.course_offering not in faculty_co_names:
        frappe.throw("Not permitted", frappe.PermissionError)


@frappe.whitelist()
def get_session_students(session_name):
    """Return students in an attendance session with their current status."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    session = frappe.get_doc("Attendance Session", session_name, ignore_permissions=True)
    _assert_session_owned_by_faculty(session, faculty_name)

    students = []
    for row in session.get("students", []):
        student_doc = frappe.db.get_value(
            "Student Master",
            row.student,
            ["first_name", "last_name", "registration_id"],
            as_dict=True,
        ) or frappe._dict()
        full_name = " ".join(filter(None, [student_doc.get("first_name"), student_doc.get("last_name")]))
        students.append({
            "student": row.student,
            "student_name": full_name or row.student,
            "reg_id": student_doc.get("registration_id") or row.student,
            "status": row.status or "Absent",
        })

    return {"students": students, "session_name": session_name}


@frappe.whitelist()
def save_attendance(session_name, attendance):
    """Save attendance for an attendance session."""
    import json

    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    session = frappe.get_doc("Attendance Session", session_name, ignore_permissions=True)
    _assert_session_owned_by_faculty(session, faculty_name)

    if isinstance(attendance, str):
        attendance = json.loads(attendance)

    # Build a lookup of submitted statuses
    att_map = {row["student"]: row["status"] for row in attendance}

    present_count = 0
    absent_count = 0

    for row in session.get("students", []):
        status = att_map.get(row.student, "Absent")
        row.status = status
        if status == "Present":
            present_count += 1
        else:
            absent_count += 1

    total = len(session.get("students", []))
    pct = round((present_count / total) * 100, 2) if total else 0
    session.present_count = present_count
    session.absent_count = absent_count
    session.total_students = total
    session.attendance_percentage = pct
    session.attendance_marked = 1
    session.flags.ignore_validate = True

    session.save(ignore_permissions=True)

    # Force the aggregate counters in DB in case the controller overrides them
    frappe.db.sql("""
        UPDATE `tabAttendance Session`
        SET present_count=%s, absent_count=%s, total_students=%s,
            attendance_percentage=%s, attendance_marked=1
        WHERE name=%s
    """, (present_count, absent_count, total, pct, session_name))

    frappe.db.commit()

    return {"success": True, "present": present_count, "absent": absent_count, "total": total}


@frappe.whitelist()
def save_condonation_recommendation(doc_name, recommendation):
    """Save faculty recommendation on a condonation request."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    allowed = ["Recommended", "Not Recommended"]
    if recommendation not in allowed:
        frappe.throw("Invalid recommendation value")

    doc = frappe.get_doc("Student Attendance Condonation", doc_name, ignore_permissions=True)

    # Verify ownership: the condonation's course offering must belong to this faculty.
    # Use the same co_names list approach used throughout the portal so that empty/None
    # faculty fields on Course Offering don't cause a false permission denial.
    faculty_co_names = frappe.get_all(
        "Course Offering",
        filters={"faculty": faculty_name},
        pluck="name",
        ignore_permissions=True,
    )
    if doc.course_offering and doc.course_offering not in faculty_co_names:
        frappe.throw("Not permitted", frappe.PermissionError)

    doc.faculty_recommendation = recommendation
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def create_venue_booking(event_name, venue_type, room, start_datetime, end_datetime,
                         expected_attendees=0, reason=""):
    """Create a Venue Booking record on behalf of the logged-in faculty."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    if not event_name or not venue_type or not room or not start_datetime or not end_datetime:
        frappe.throw("Event name, venue type, room, start and end date/time are all required")

    # Resolve the faculty's full display name from the Faculty record
    faculty_doc = frappe.db.get_value(
        "Faculty", faculty_name, ["first_name", "last_name"], as_dict=True
    )
    if faculty_doc:
        requester_display = " ".join(filter(None, [faculty_doc.first_name, faculty_doc.last_name]))
    else:
        requester_display = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user

    doc = frappe.new_doc("Venue Booking")
    doc.event_name = event_name
    doc.venue_type = venue_type
    doc.room = room
    doc.start_datetime = start_datetime
    doc.end_datetime = end_datetime
    doc.expected_attendees = int(expected_attendees or 0)
    doc.reason = reason
    doc.requester_type = "Faculty"
    doc.requester_name = requester_display or str(faculty_name)
    doc.status = "Pending"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "name": doc.name}


@frappe.whitelist()
def update_profile(phone="", qualification="", specialization="", experience_years=None,
                   highlights="", institution=""):
    """Update editable fields on the Faculty record for the logged-in user."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    doc = frappe.get_doc("Faculty", faculty_name, ignore_permissions=True)

    if phone is not None:
        doc.phone = phone.strip()
    if qualification is not None:
        doc.qualification = qualification.strip()
    if specialization is not None:
        doc.specialization = specialization.strip()
    if experience_years is not None and str(experience_years).strip() != "":
        try:
            doc.experience_years = int(experience_years)
        except (ValueError, TypeError):
            frappe.throw("Experience years must be a number")
    if highlights is not None:
        doc.highlights = highlights.strip()
    if institution is not None:
        doc.institution = institution.strip()

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def change_password(old_password, new_password):
    """Change the logged-in user's password after verifying the current one."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    if not old_password or not new_password:
        frappe.throw("Both current and new password are required")

    if len(new_password) < 8:
        frappe.throw("New password must be at least 8 characters")

    from frappe.utils.password import check_password, update_password

    try:
        check_password(frappe.session.user, old_password)
    except Exception:
        frappe.throw("Current password is incorrect. Please try again.")

    try:
        update_password(frappe.session.user, new_password)
        frappe.db.commit()
    except Exception as e:
        frappe.throw(f"Could not update password: {e}")

    return {"success": True}


@frappe.whitelist()
def get_reset_password_url():
    """Generate a password reset key for the logged-in user and return the
    /update-password URL built from the actual request host — bypassing
    Frappe's host_name site config which may not match the dev server port."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    import hashlib, secrets

    key = secrets.token_hex(32)
    hashed_key = hashlib.sha256(key.encode()).hexdigest()

    frappe.db.set_value("User", user, {
        "reset_password_key": hashed_key,
        "last_reset_password_key_generated_on": frappe.utils.now_datetime(),
    })
    frappe.db.commit()

    # Build URL from the actual incoming request host so it always works
    # regardless of the site config host_name (fixes local dev port issues).
    request = getattr(frappe.local, "request", None)
    if request and getattr(request, "host", None):
        proto = "https://" if frappe.get_request_header("X-Forwarded-Proto", "") == "https" else "http://"
        base = proto + request.host
    else:
        base = frappe.utils.get_url()

    return {"url": base + "/update-password?key=" + key}


@frappe.whitelist()
def save_preferences(
    font_size_pref="Normal",
    layout_density_pref="Normal",
    notify_assignment_submission=1,
    notify_attendance_discrepancy=1,
    notify_student_query=1,
    notify_leave_request_update=1,
    notify_marks_due=1,
    email_digest_frequency="Realtime",
    hide_today_schedule=0,
    hide_pending_evaluations=0,
    hide_class_statistics=0,
    hide_workload_summary=0,
    hide_leave_status=0,
    default_course_view="Grid",
):
    """Create or update Faculty Portal User Preferences for the logged-in user."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    user = frappe.session.user

    try:
        doc = frappe.get_doc("Faculty Portal User Preferences", user)
    except frappe.DoesNotExistError:
        doc = frappe.new_doc("Faculty Portal User Preferences")
        doc.faculty_user = user

    doc.font_size_pref              = font_size_pref or "Normal"
    doc.layout_density_pref         = layout_density_pref or "Normal"
    doc.notify_assignment_submission = _int(notify_assignment_submission)
    doc.notify_attendance_discrepancy= _int(notify_attendance_discrepancy)
    doc.notify_student_query         = _int(notify_student_query)
    doc.notify_leave_request_update  = _int(notify_leave_request_update)
    doc.notify_marks_due             = _int(notify_marks_due)
    doc.email_digest_frequency       = email_digest_frequency or "Realtime"
    doc.hide_today_schedule          = _int(hide_today_schedule)
    doc.hide_pending_evaluations     = _int(hide_pending_evaluations)
    doc.hide_class_statistics        = _int(hide_class_statistics)
    doc.hide_workload_summary        = _int(hide_workload_summary)
    doc.hide_leave_status            = _int(hide_leave_status)
    doc.default_course_view          = default_course_view or "Grid"

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def get_dashboard_stats():
    """Return faculty dashboard statistics."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found for this user", frappe.DoesNotExistError)

    today = frappe.utils.today()

    co_names = frappe.get_all(
        "Course Offering",
        filters={"faculty": faculty_name, "status": ["in", ["Open", "Active"]]},
        pluck="name",
        ignore_permissions=True,
    )

    today_classes = frappe.db.count(
        "Attendance Session",
        filters={
            "course_offering": ["in", co_names] if co_names else ["in", ["__none__"]],
            "session_date": today,
        },
    ) if co_names else 0

    pending_att = frappe.db.count(
        "Attendance Session",
        filters={
            "course_offering": ["in", co_names] if co_names else ["in", ["__none__"]],
            "attendance_marked": 0,
            "session_date": ["<=", today],
            "session_status": "Scheduled",
        },
    ) if co_names else 0

    return {
        "total_subjects": len(co_names),
        "todays_class_count": today_classes,
        "attendance_pending": pending_att,
    }


# ── Drill-down helpers ─────────────────────────────────────────────────────

def _get_faculty_co_names(faculty_name):
    """Return list of active course offering names for the faculty."""
    return frappe.get_all(
        "Course Offering",
        filters={"faculty": faculty_name, "status": ["in", ["Open", "Active"]]},
        pluck="name",
        ignore_permissions=True,
    )


@frappe.whitelist()
def drilldown_subjects():
    """Drill-down: all course offerings assigned to this faculty."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    offerings = frappe.get_all(
        "Course Offering",
        filters={"faculty": faculty_name, "status": ["in", ["Open", "Active"]]},
        fields=["name", "course_name", "term_name", "academic_year",
                "credit_value", "maximum_students", "status"],
        order_by="academic_year desc, term_name asc, course_name asc",
        ignore_permissions=True,
    )

    rows = []
    for co in offerings:
        try:
            enr = frappe.db.sql(
                """SELECT COUNT(DISTINCT se.student) AS cnt
                   FROM `tabStudent Enrollment Course` sec
                   JOIN `tabStudent Enrollment` se ON se.name = sec.parent
                   WHERE sec.course_offering = %s AND sec.status = 'Enrolled'""",
                co.name, as_dict=True,
            )
            students = (enr[0].cnt or 0) if enr else 0
        except Exception:
            students = 0

        try:
            att = frappe.db.sql(
                """SELECT AVG(attendance_percentage) AS avg_pct, COUNT(*) AS sess
                   FROM `tabAttendance Session`
                   WHERE course_offering = %s AND attendance_marked = 1""",
                co.name, as_dict=True,
            )
            avg_pct = round(float((att[0].avg_pct or 0) if att else 0), 1)
            sessions = (att[0].sess or 0) if att else 0
        except Exception:
            avg_pct = 0.0
            sessions = 0

        rows.append({
            "course_offering": co.name,
            "course_name": co.course_name or co.name,
            "term": co.term_name or "—",
            "academic_year": co.academic_year or "—",
            "credits": co.credit_value or 0,
            "students": students,
            "sessions": sessions,
            "avg_attendance": avg_pct,
            "status": co.status or "Active",
        })

    return {
        "title": "My Subjects",
        "columns": [
            {"key": "course_name",    "label": "Course Name",      "type": "text"},
            {"key": "term",           "label": "Term",             "type": "text"},
            {"key": "academic_year",  "label": "Academic Year",    "type": "text"},
            {"key": "credits",        "label": "Credits",          "type": "number"},
            {"key": "students",       "label": "Students",         "type": "number"},
            {"key": "sessions",       "label": "Sessions Held",    "type": "number"},
            {"key": "avg_attendance", "label": "Avg Attendance %", "type": "percent"},
            {"key": "status",         "label": "Status",           "type": "badge"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_students():
    """Drill-down: all enrolled students across this faculty's courses."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    co_names = _get_faculty_co_names(faculty_name)
    if not co_names:
        return {"title": "Total Students", "columns": [], "rows": [], "count": 0}

    try:
        raw = frappe.db.sql(
            """
            SELECT DISTINCT
                se.student,
                sm.first_name, sm.last_name,
                sm.registration_id,
                sm.gender,
                se.program,
                sec.course_offering,
                co.course_name,
                co.term_name,
                co.academic_year
            FROM `tabStudent Enrollment Course` sec
            JOIN `tabStudent Enrollment` se ON se.name = sec.parent
            JOIN `tabCourse Offering` co ON co.name = sec.course_offering
            LEFT JOIN `tabStudent Master` sm ON sm.name = se.student
            WHERE sec.course_offering IN %s
              AND sec.status = 'Enrolled'
            ORDER BY co.course_name, sm.last_name, sm.first_name
            """,
            (tuple(co_names),),
            as_dict=True,
        )
    except Exception:
        raw = []

    rows = []
    for r in raw:
        full_name = " ".join(filter(None, [r.get("first_name"), r.get("last_name")])) or r.get("student", "")
        rows.append({
            "student_id": r.get("registration_id") or r.get("student", ""),
            "student_name": full_name,
            "gender": r.get("gender") or "—",
            "program": r.get("program") or "—",
            "course_name": r.get("course_name") or r.get("course_offering", ""),
            "term": r.get("term_name") or "—",
            "academic_year": r.get("academic_year") or "—",
        })

    return {
        "title": "Enrolled Students",
        "columns": [
            {"key": "student_id",   "label": "Student ID",    "type": "text"},
            {"key": "student_name", "label": "Name",          "type": "text"},
            {"key": "gender",       "label": "Gender",        "type": "text"},
            {"key": "program",      "label": "Program",       "type": "text"},
            {"key": "course_name",  "label": "Course",        "type": "text"},
            {"key": "term",         "label": "Term",          "type": "text"},
            {"key": "academic_year","label": "Academic Year", "type": "text"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_todays_classes():
    """Drill-down: today's scheduled sessions."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    co_names = _get_faculty_co_names(faculty_name)
    today = frappe.utils.today()

    if not co_names:
        return {"title": "Today's Classes", "columns": [], "rows": [], "count": 0}

    raw = frappe.get_all(
        "Attendance Session",
        filters=[
            ["course_offering", "in", co_names],
            ["session_date", "=", today],
        ],
        fields=["name", "course_offering", "session_date",
                "session_start_time", "session_end_time",
                "room", "session_status", "total_students",
                "present_count", "absent_count", "attendance_percentage", "attendance_marked"],
        order_by="session_start_time asc",
        ignore_permissions=True,
    )

    co_map = {co: frappe.db.get_value("Course Offering", co, "course_name") or co
              for co in co_names}

    from slcm.utils.faculty_portal import fmt_time

    rows = []
    for s in raw:
        rows.append({
            "session": s.name,
            "course_name": co_map.get(s.course_offering, s.course_offering),
            "date": frappe.utils.formatdate(s.session_date, "dd MMM yyyy"),
            "start_time": fmt_time(s.session_start_time),
            "end_time": fmt_time(s.session_end_time),
            "venue": s.room or "—",
            "total_students": s.total_students or 0,
            "present": s.present_count or 0,
            "absent": s.absent_count or 0,
            "attendance_pct": round(float(s.attendance_percentage or 0), 1),
            "status": "Marked" if s.attendance_marked else "Pending",
        })

    return {
        "title": "Today's Classes",
        "columns": [
            {"key": "course_name",    "label": "Course",        "type": "text"},
            {"key": "date",           "label": "Date",          "type": "text"},
            {"key": "start_time",     "label": "Start Time",    "type": "text"},
            {"key": "end_time",       "label": "End Time",      "type": "text"},
            {"key": "venue",          "label": "Venue",         "type": "text"},
            {"key": "total_students", "label": "Students",      "type": "number"},
            {"key": "present",        "label": "Present",       "type": "number"},
            {"key": "absent",         "label": "Absent",        "type": "number"},
            {"key": "attendance_pct", "label": "Attendance %",  "type": "percent"},
            {"key": "status",         "label": "Status",        "type": "badge"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_pending_attendance():
    """Drill-down: all unmarked (pending) attendance sessions."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    co_names = _get_faculty_co_names(faculty_name)
    today = frappe.utils.today()

    if not co_names:
        return {"title": "Pending Attendance", "columns": [], "rows": [], "count": 0}

    raw = frappe.get_all(
        "Attendance Session",
        filters={
            "course_offering": ["in", co_names],
            "attendance_marked": 0,
            "session_date": ["<=", today],
            "session_status": "Scheduled",
        },
        fields=["name", "course_offering", "session_date",
                "session_start_time", "session_end_time",
                "room", "total_students"],
        order_by="session_date asc",
        ignore_permissions=True,
    )

    co_map = {co: frappe.db.get_value("Course Offering", co, "course_name") or co
              for co in co_names}

    from slcm.utils.faculty_portal import fmt_time

    rows = []
    for s in raw:
        date_obj = frappe.utils.getdate(s.session_date)
        today_obj = frappe.utils.getdate(today)
        days_overdue = (today_obj - date_obj).days
        rows.append({
            "session": s.name,
            "course_name": co_map.get(s.course_offering, s.course_offering),
            "date": frappe.utils.formatdate(s.session_date, "dd MMM yyyy"),
            "start_time": fmt_time(s.session_start_time),
            "venue": s.room or "—",
            "total_students": s.total_students or 0,
            "days_overdue": days_overdue,
            "action_link": f"/faculty-portal/attendance?session={s.name}",
        })

    return {
        "title": "Pending Attendance Sessions",
        "columns": [
            {"key": "course_name",    "label": "Course",          "type": "text"},
            {"key": "date",           "label": "Session Date",    "type": "text"},
            {"key": "start_time",     "label": "Time",            "type": "text"},
            {"key": "venue",          "label": "Venue",           "type": "text"},
            {"key": "total_students", "label": "Students",        "type": "number"},
            {"key": "days_overdue",   "label": "Days Overdue",    "type": "overdue"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_venue_bookings():
    """Drill-down: pending venue bookings by this faculty."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    faculty_doc = frappe.db.get_value(
        "Faculty", faculty_name, ["first_name", "last_name", "email"], as_dict=True
    ) or frappe._dict()
    display_name = " ".join(filter(None, [faculty_doc.first_name, faculty_doc.last_name]))
    email = faculty_doc.email or ""

    name_filters = list(filter(None, [faculty_name, display_name, email]))

    try:
        raw = frappe.get_all(
            "Venue Booking",
            filters={"requester_name": ["in", name_filters], "status": "Pending"},
            fields=["name", "event_name", "venue_type", "room",
                    "start_datetime", "end_datetime", "expected_attendees",
                    "status", "creation"],
            order_by="start_datetime asc",
            ignore_permissions=True,
        )
    except Exception:
        raw = []

    rows = []
    for b in raw:
        rows.append({
            "booking_id": b.name,
            "event_name": b.event_name or "—",
            "venue_type": b.venue_type or "—",
            "room": b.room or "—",
            "start": frappe.utils.format_datetime(b.start_datetime, "dd MMM yyyy HH:mm") if b.start_datetime else "—",
            "end": frappe.utils.format_datetime(b.end_datetime, "dd MMM yyyy HH:mm") if b.end_datetime else "—",
            "attendees": b.expected_attendees or 0,
            "status": b.status or "Pending",
        })

    return {
        "title": "Pending Venue Bookings",
        "columns": [
            {"key": "booking_id",  "label": "Booking ID",   "type": "text"},
            {"key": "event_name",  "label": "Event",        "type": "text"},
            {"key": "venue_type",  "label": "Venue Type",   "type": "text"},
            {"key": "room",        "label": "Room",         "type": "text"},
            {"key": "start",       "label": "Start",        "type": "text"},
            {"key": "end",         "label": "End",          "type": "text"},
            {"key": "attendees",   "label": "Attendees",    "type": "number"},
            {"key": "status",      "label": "Status",       "type": "badge"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_condonation():
    """Drill-down: pending condonation requests for this faculty's courses."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    co_names = _get_faculty_co_names(faculty_name)
    if not co_names:
        return {"title": "Condonation Requests", "columns": [], "rows": [], "count": 0}

    try:
        raw = frappe.get_all(
            "Student Attendance Condonation",
            filters={
                "course_offering": ["in", co_names],
                "final_status": "Pending",
                "faculty_recommendation": ["in", ["", None, "Pending"]],
            },
            fields=["name", "student", "course_offering",
                    "reason", "faculty_recommendation", "final_status", "creation"],
            order_by="creation desc",
            ignore_permissions=True,
        )
    except Exception:
        raw = []

    co_map = {co: frappe.db.get_value("Course Offering", co, "course_name") or co
              for co in co_names}

    rows = []
    for r in raw:
        student_name = frappe.db.get_value(
            "Student Master", r.student,
            "concat(first_name, ' ', last_name)"
        ) or r.student

        rows.append({
            "request_id": r.name,
            "student": r.student,
            "student_name": student_name,
            "course_name": co_map.get(r.course_offering, r.course_offering),
            "reason": (r.reason or "—")[:80],
            "faculty_recommendation": r.faculty_recommendation or "Pending",
            "status": r.final_status or "Pending",
            "submitted": frappe.utils.formatdate(r.creation, "dd MMM yyyy"),
        })

    return {
        "title": "Condonation Requests",
        "columns": [
            {"key": "request_id",            "label": "Request ID",          "type": "text"},
            {"key": "student_name",          "label": "Student",             "type": "text"},
            {"key": "course_name",           "label": "Course",              "type": "text"},
            {"key": "reason",                "label": "Reason",              "type": "text"},
            {"key": "faculty_recommendation","label": "Your Recommendation", "type": "badge"},
            {"key": "status",                "label": "Final Status",        "type": "badge"},
            {"key": "submitted",             "label": "Submitted",           "type": "text"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_student_groups():
    """Drill-down: course-wise student group summary."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    co_names = _get_faculty_co_names(faculty_name)
    if not co_names:
        return {"title": "Student Groups", "columns": [], "rows": [], "count": 0}

    offerings = frappe.get_all(
        "Course Offering",
        filters={"name": ["in", co_names]},
        fields=["name", "course_name", "term_name", "academic_year"],
        ignore_permissions=True,
    )

    rows = []
    for co in offerings:
        try:
            enr = frappe.db.sql(
                """SELECT COUNT(DISTINCT se.student) AS cnt
                   FROM `tabStudent Enrollment Course` sec
                   JOIN `tabStudent Enrollment` se ON se.name = sec.parent
                   WHERE sec.course_offering = %s AND sec.status = 'Enrolled'""",
                co.name, as_dict=True,
            )
            students = (enr[0].cnt or 0) if enr else 0
        except Exception:
            students = 0

        if students > 0:
            try:
                att = frappe.db.sql(
                    """SELECT AVG(attendance_percentage) AS avg_pct
                       FROM `tabAttendance Session`
                       WHERE course_offering = %s AND attendance_marked = 1""",
                    co.name, as_dict=True,
                )
                avg_pct = round(float((att[0].avg_pct or 0) if att else 0), 1)
            except Exception:
                avg_pct = 0.0

            rows.append({
                "course_offering": co.name,
                "course_name": co.course_name or co.name,
                "term": co.term_name or "—",
                "academic_year": co.academic_year or "—",
                "student_count": students,
                "avg_attendance": avg_pct,
            })

    rows.sort(key=lambda x: x["student_count"], reverse=True)

    return {
        "title": "Student Groups",
        "columns": [
            {"key": "course_name",    "label": "Course",           "type": "text"},
            {"key": "term",           "label": "Term",             "type": "text"},
            {"key": "academic_year",  "label": "Academic Year",    "type": "text"},
            {"key": "student_count",  "label": "Students",         "type": "number"},
            {"key": "avg_attendance", "label": "Avg Attendance %", "type": "percent"},
        ],
        "rows": rows,
        "count": len(rows),
    }


@frappe.whitelist()
def drilldown_weekly_hours():
    """Drill-down: this week's teaching sessions with duration."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)
    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    co_names = _get_faculty_co_names(faculty_name)
    today = frappe.utils.today()
    week_start = frappe.utils.get_first_day_of_week(today)

    if not co_names:
        return {"title": "This Week's Teaching Hours", "columns": [], "rows": [], "count": 0}

    raw = frappe.get_all(
        "Attendance Session",
        filters=[
            ["course_offering", "in", co_names],
            ["session_date", ">=", week_start],
            ["session_date", "<=", today],
        ],
        fields=["name", "course_offering", "session_date",
                "session_start_time", "session_end_time",
                "room", "total_students", "present_count", "attendance_percentage"],
        order_by="session_date asc, session_start_time asc",
        ignore_permissions=True,
    )

    co_map = {co: frappe.db.get_value("Course Offering", co, "course_name") or co
              for co in co_names}

    from slcm.utils.faculty_portal import fmt_time

    rows = []
    for s in raw:
        duration_hrs = 0.0
        if s.session_start_time and s.session_end_time:
            secs = frappe.utils.time_diff_in_seconds(s.session_end_time, s.session_start_time)
            if secs > 0:
                duration_hrs = round(secs / 3600, 2)
        rows.append({
            "course_name": co_map.get(s.course_offering, s.course_offering),
            "date": frappe.utils.formatdate(s.session_date, "dd MMM yyyy"),
            "start_time": fmt_time(s.session_start_time),
            "end_time": fmt_time(s.session_end_time),
            "duration_hrs": duration_hrs,
            "venue": s.room or "—",
            "students": s.total_students or 0,
            "present": s.present_count or 0,
            "attendance_pct": round(float(s.attendance_percentage or 0), 1),
        })

    return {
        "title": "This Week's Teaching Sessions",
        "columns": [
            {"key": "course_name",    "label": "Course",       "type": "text"},
            {"key": "date",           "label": "Date",         "type": "text"},
            {"key": "start_time",     "label": "Start",        "type": "text"},
            {"key": "end_time",       "label": "End",          "type": "text"},
            {"key": "duration_hrs",   "label": "Duration (h)", "type": "number"},
            {"key": "venue",          "label": "Venue",        "type": "text"},
            {"key": "students",       "label": "Students",     "type": "number"},
            {"key": "present",        "label": "Present",      "type": "number"},
            {"key": "attendance_pct", "label": "Att. %",       "type": "percent"},
        ],
        "rows": rows,
        "count": len(rows),
    }
