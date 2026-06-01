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
                filters={"faculty": faculty_name, "status": "Active"},
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
                        "session_status": "Active",
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
                        "faculty_recommendation": ["in", ["", None]],
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

    return {
        "notifications": notifications[:15],
        "count": count,
        "urgent_count": urgent_count,
    }


@frappe.whitelist()
def get_session_students(session_name):
    """Return students in an attendance session with their current status."""
    if frappe.session.user == "Guest":
        frappe.throw("Not permitted", frappe.PermissionError)

    faculty_name = get_faculty_name()
    if not faculty_name:
        frappe.throw("No faculty record found", frappe.DoesNotExistError)

    # Verify the session belongs to this faculty
    session = frappe.get_doc("Attendance Session", session_name, ignore_permissions=True)
    co_faculty = frappe.db.get_value("Course Offering", session.course_offering, "faculty")
    if co_faculty != faculty_name:
        frappe.throw("Not permitted", frappe.PermissionError)

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
            "status": row.attendance_status or "Absent",
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

    # Verify ownership
    session = frappe.get_doc("Attendance Session", session_name, ignore_permissions=True)
    co_faculty = frappe.db.get_value("Course Offering", session.course_offering, "faculty")
    if co_faculty != faculty_name:
        frappe.throw("Not permitted", frappe.PermissionError)

    if isinstance(attendance, str):
        attendance = json.loads(attendance)

    # Build a lookup of submitted statuses
    att_map = {row["student"]: row["status"] for row in attendance}

    present_count = 0
    absent_count = 0

    for row in session.get("students", []):
        status = att_map.get(row.student, "Absent")
        row.attendance_status = status
        if status == "Present":
            present_count += 1
        else:
            absent_count += 1

    total = len(session.get("students", []))
    session.present_count = present_count
    session.absent_count = absent_count
    session.total_students = total
    session.attendance_percentage = round((present_count / total) * 100, 2) if total else 0
    session.attendance_marked = 1

    session.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True, "present": present_count, "absent": absent_count}


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

    # Verify the course offering belongs to this faculty
    co_faculty = frappe.db.get_value("Course Offering", doc.course_offering, "faculty")
    if co_faculty != faculty_name:
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

    doc = frappe.new_doc("Venue Booking")
    doc.event_name = event_name
    doc.venue_type = venue_type
    doc.room = room
    doc.start_datetime = start_datetime
    doc.end_datetime = end_datetime
    doc.expected_attendees = int(expected_attendees or 0)
    doc.reason = reason
    doc.requester_type = "Faculty"
    doc.requester_name = faculty_name
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
        filters={"faculty": faculty_name, "status": "Active"},
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
            "session_status": "Active",
        },
    ) if co_names else 0

    return {
        "total_subjects": len(co_names),
        "todays_class_count": today_classes,
        "attendance_pending": pending_att,
    }
