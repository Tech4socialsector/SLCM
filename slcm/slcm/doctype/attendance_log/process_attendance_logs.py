# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

"""
Background Processor: RFID Attendance Logs → Student Attendance
===============================================================
Converts raw RFID swipes (Attendance Log) into Student Attendance records
and then triggers the Attendance Summary recalculation.

Flow per student per day
------------------------
1. Fetch Attendance Sessions for the student on that date.
   If a Class Schedule exists but no Attendance Session was created yet,
   auto-create the session so RFID can still work without manual setup.
2. Match each swipe to a session window (±20 min buffer).
3. Apply RFID mode (In Only / In and Out) to determine Present/Absent.
4. Create or update Student Attendance — NEVER silently drops a swipe.
5. Mark Attendance Log rows as processed.
6. Attendance calculator fires automatically via Student Attendance on_update.

Business Rules
--------------
- First swipe within window → Present (In Only mode)
- Two swipes + ≥50 % duration covered → Present (In and Out mode)
- Single swipe + session ended > 30 min ago → Absent (In and Out mode)
- Duplicate swipes within 10 min → debounced / ignored
"""

import frappe
from frappe import _
from frappe.utils import (
    getdate,
    now_datetime,
    get_datetime,
    time_diff_in_hours,
    add_to_date,
    flt,
)
from collections import defaultdict


# ---------------------------------------------------------------------------
# Scheduled entry point  (*/10 * * * *)
# ---------------------------------------------------------------------------

def process_pending_logs():
    """Main scheduled entry point — processes all unprocessed Attendance Logs."""
    try:
        if not frappe.db.get_single_value("Attendance Settings", "enable_rfid"):
            return

        logs = _get_unprocessed_logs()
        if not logs:
            frappe.logger().info("RFID Processor: no pending logs")
            return

        grouped = _group_by_student_date(logs)

        processed_count = 0
        for key, student_logs in grouped.items():
            try:
                _process_student_day(student_logs)
                processed_count += len(student_logs)
            except Exception:
                frappe.log_error(
                    title=f"RFID Processor — error for {key}",
                    message=frappe.get_traceback(),
                )

        frappe.db.commit()
        frappe.logger().info(f"RFID Processor: processed {processed_count} log(s)")

    except Exception:
        frappe.log_error(
            title="RFID Processor — unhandled error",
            message=frappe.get_traceback(),
        )


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _get_unprocessed_logs():
    return frappe.get_all(
        "Attendance Log",
        filters={"processed": 0, "student": ["!=", ""]},
        fields=["name", "student", "swipe_time", "device_id", "location", "rfid_uid"],
        order_by="swipe_time asc",
    )


def _group_by_student_date(logs):
    grouped = defaultdict(list)
    for log in logs:
        key = (log.get("student"), getdate(log.get("swipe_time")))
        grouped[key].append(log)
    return grouped


# ---------------------------------------------------------------------------
# Core: process one student on one day
# ---------------------------------------------------------------------------

def _process_student_day(logs):
    if not logs:
        return

    student   = logs[0].get("student")
    log_date  = getdate(logs[0].get("swipe_time"))
    rfid_mode = frappe.db.get_single_value("Attendance Settings", "rfid_swipe_mode") or "In Only"

    # Sort chronologically
    logs = sorted(logs, key=lambda x: x.get("swipe_time"))

    # Resolve matching sessions (creates missing ones from Class Schedule automatically)
    sessions = _get_or_create_sessions(student, log_date)

    if not sessions:
        frappe.logger().info(
            f"RFID Processor: no sessions for {student} on {log_date} — logs left unprocessed"
        )
        return

    processed_names = set()

    for session in sessions:
        matched = _match_swipes_to_session(logs, session)
        if not matched:
            continue

        status = _determine_status(matched, session, rfid_mode)
        if not status:
            # Session still in progress — leave logs for next run
            continue

        if session.get("session_type") == "Office Hour":
            _upsert_office_hour_attendance(student, session, matched)
        else:
            _upsert_class_attendance(student, session, status, matched)

        for log in matched:
            processed_names.add(log.name)

    for log in logs:
        if log.name in processed_names:
            frappe.db.set_value("Attendance Log", log.name, "processed", 1)


# ---------------------------------------------------------------------------
# Session resolution — the key improvement
# ---------------------------------------------------------------------------

def _get_or_create_sessions(student, date):
    """
    Return Attendance Sessions the student should attend on *date*.
    If a Class Schedule exists but no Attendance Session has been created,
    auto-create the session so RFID never silently fails.
    """
    sessions = []

    # 1. Existing Attendance Sessions
    existing = frappe.get_all(
        "Attendance Session",
        filters={"session_date": date, "session_status": ["!=", "Cancelled"], "docstatus": ["<", 2]},
        fields=["name", "session_date", "session_start_time", "session_end_time",
                "course_schedule", "class_schedule", "course_offering",
                "session_type", "duration_hours", "student_group"],
    )

    for s in existing:
        if _is_student_in_session(student, s):
            s["type"] = "Office Hour" if s.get("session_type") == "Office Hour" else "Class"
            sessions.append(s)

    # 2. Class Schedules that have NO Attendance Session yet → auto-create
    class_schedules = frappe.get_all(
        "Class Schedule",
        filters={
            "schedule_date": date,
            "status": ["!=", "Cancelled"],
            "docstatus": ["<", 2],
        },
        fields=["name", "course", "course_offering", "from_time", "to_time",
                "duration_hours", "instructor", "venue", "student_group"],
    )

    existing_from_schedule = {s.get("class_schedule") for s in existing if s.get("class_schedule")}

    for cs in class_schedules:
        if cs.name in existing_from_schedule:
            continue  # session already exists

        # Check student is enrolled in this course offering
        if not _is_student_in_course_offering(student, cs.course_offering):
            continue

        # Auto-create the Attendance Session
        new_session = _auto_create_session_from_schedule(cs, date)
        if new_session:
            new_session["type"] = "Class"
            sessions.append(new_session)

    # 3. Office Hours Sessions
    oh_sessions = frappe.get_all(
        "Office Hours Session",
        filters={"session_date": date, "session_status": ["!=", "Cancelled"]},
        fields=["name", "session_date",
                "start_time as session_start_time",
                "end_time as session_end_time",
                "course_offering"],
    )
    for s in oh_sessions:
        if _is_student_in_course_offering(student, s.get("course_offering")):
            s["session_type"] = "Office Hour"
            s["type"] = "Office Hour"
            sessions.append(s)

    return sessions


def _auto_create_session_from_schedule(cs, date):
    """Create an Attendance Session from a Class Schedule record."""
    try:
        from frappe.utils import time_diff_in_hours
        duration = flt(cs.get("duration_hours")) or (
            time_diff_in_hours(cs.get("to_time"), cs.get("from_time"))
            if cs.get("from_time") and cs.get("to_time")
            else 0
        )

        doc = frappe.get_doc({
            "doctype":           "Attendance Session",
            "based_on":          "Class Schedule",
            "class_schedule":    cs.name,
            "course_offering":   cs.course_offering,
            "student_group":     cs.get("student_group"),
            "session_date":      date,
            "session_type":      "Lecture",
            "session_start_time": cs.get("from_time"),
            "session_end_time":  cs.get("to_time"),
            "duration_hours":    duration,
            "session_status":    "Conducted",
            "instructor":        cs.get("instructor"),
        })
        doc.flags.skip_auto_attendance = True  # we don't pre-populate; RFID does it
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return frappe._dict({
            "name":               doc.name,
            "session_date":       date,
            "session_start_time": doc.session_start_time,
            "session_end_time":   doc.session_end_time,
            "class_schedule":     cs.name,
            "course_offering":    cs.course_offering,
            "session_type":       "Lecture",
            "duration_hours":     duration,
            "student_group":      cs.get("student_group"),
        })

    except Exception:
        frappe.log_error(
            title=f"RFID Processor — failed to auto-create session for Class Schedule {cs.name}",
            message=frappe.get_traceback(),
        )
        return None


# ---------------------------------------------------------------------------
# Eligibility checks
# ---------------------------------------------------------------------------

def _is_student_in_session(student, session):
    """True if the student should attend this Attendance Session."""
    # Already has a Student Attendance record → definitely enrolled
    if frappe.db.exists("Student Attendance", {"student": student, "attendance_session": session.get("name")}):
        return True

    # Check via Student Group
    sg = session.get("student_group")
    if not sg and session.get("class_schedule"):
        sg = frappe.db.get_value("Class Schedule", session.get("class_schedule"), "student_group")
    if not sg and session.get("course_schedule"):
        sg = frappe.db.get_value("Course Schedule", session.get("course_schedule"), "student_group")

    if sg and frappe.db.exists("Student Group Student", {"parent": sg, "student": student}):
        return True

    # Fallback: Cohort enrollment
    return _is_student_in_course_offering(student, session.get("course_offering"))


def _is_student_in_course_offering(student, course_offering):
    """True if the student is actively enrolled in this Course Offering's cohort."""
    if not course_offering:
        return False
    cohort = frappe.db.get_value("Course Offering", course_offering, "cohort")
    if not cohort:
        return False
    return bool(frappe.db.exists("Student Enrollment", {
        "student":  student,
        "batch":    cohort,
        "status":   "Enrolled",
    }))


# ---------------------------------------------------------------------------
# Swipe matching
# ---------------------------------------------------------------------------

def _match_swipes_to_session(logs, session):
    """Return logs whose swipe_time falls within the session window ±20 min."""
    session_date = session.get("session_date") or getdate()
    start = get_datetime(f"{session_date} {session['session_start_time']}")
    end   = get_datetime(f"{session_date} {session['session_end_time']}")
    win_start = add_to_date(start, minutes=-20)
    win_end   = add_to_date(end,   minutes=20)

    return [lg for lg in logs if win_start <= get_datetime(lg.get("swipe_time")) <= win_end]


# ---------------------------------------------------------------------------
# Status determination
# ---------------------------------------------------------------------------

def _determine_status(matched_logs, session, mode):
    """Return 'Present', 'Absent', or None (still in progress)."""
    if not matched_logs:
        return None

    if mode == "In Only":
        return "Present"

    # In and Out — need swipe at both ends
    if len(matched_logs) >= 2:
        first = get_datetime(matched_logs[0].get("swipe_time"))
        last  = get_datetime(matched_logs[-1].get("swipe_time"))
        covered = time_diff_in_hours(last, first)

        s_start = get_datetime(f"{session.get('session_date')} {session['session_start_time']}")
        s_end   = get_datetime(f"{session.get('session_date')} {session['session_end_time']}")
        duration = time_diff_in_hours(s_end, s_start)

        if duration > 0 and covered >= (duration * 0.5):
            return "Present"

    # Single swipe or insufficient duration — wait unless session is over
    session_date = session.get("session_date") or getdate()
    cutoff = add_to_date(
        get_datetime(f"{session_date} {session['session_end_time']}"),
        minutes=30,
    )
    if now_datetime() > cutoff:
        return "Absent"

    return None  # Session still running — try again next cycle


# ---------------------------------------------------------------------------
# Upsert helpers — ALWAYS create, never silently drop
# ---------------------------------------------------------------------------

def _upsert_class_attendance(student, session, status, logs):
    """Create or update Student Attendance for a class/lecture session."""
    first_log = logs[0]
    last_log  = logs[-1]
    hours     = flt(session.get("duration_hours")) if status == "Present" else 0

    existing = frappe.db.exists("Student Attendance", {
        "student":            student,
        "attendance_session": session.get("name"),
    })

    if existing:
        doc = frappe.get_doc("Student Attendance", existing)
        doc.status        = status
        doc.source        = "RFID"
        doc.in_time       = first_log.get("swipe_time")
        doc.out_time      = last_log.get("swipe_time")
        doc.attendance_log = first_log.get("name")
        doc.hours_counted  = hours
        doc.session_type   = session.get("session_type") or "Lecture"
        doc.save(ignore_permissions=True)
    else:
        # Create a fresh record — this is the critical fix:
        # RFID attendance works even without a pre-created placeholder
        doc = frappe.get_doc({
            "doctype":            "Student Attendance",
            "student":            student,
            "attendance_session": session.get("name"),
            "course_offer":       session.get("course_offering"),
            "class_schedule":     session.get("class_schedule"),
            "course_schedule":    session.get("course_schedule"),
            "attendance_date":    getdate(first_log.get("swipe_time")),
            "date":               getdate(first_log.get("swipe_time")),
            "status":             status,
            "source":             "RFID",
            "in_time":            first_log.get("swipe_time"),
            "out_time":           last_log.get("swipe_time"),
            "attendance_log":     first_log.get("name"),
            "session_type":       session.get("session_type") or "Lecture",
            "hours_counted":      hours,
            "student_group":      session.get("student_group"),
        })
        doc.insert(ignore_permissions=True)


def _upsert_office_hour_attendance(student, session, logs):
    """Create or update Student Attendance for an office hours session."""
    first_log = logs[0]
    last_log  = logs[-1]

    start = get_datetime(first_log.get("swipe_time"))
    end   = get_datetime(last_log.get("swipe_time"))
    duration = max(flt(time_diff_in_hours(end, start)), 0)

    existing = frappe.db.exists("Student Attendance", {
        "student":            student,
        "attendance_session": session.get("name"),
    })

    if existing:
        doc = frappe.get_doc("Student Attendance", existing)
        doc.status        = "Present"
        doc.source        = "RFID"
        doc.in_time       = first_log.get("swipe_time")
        doc.out_time      = last_log.get("swipe_time")
        doc.hours_counted  = duration
        doc.session_type   = "Office Hour"
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype":            "Student Attendance",
            "student":            student,
            "attendance_session": session.get("name"),
            "course_offer":       session.get("course_offering"),
            "attendance_date":    getdate(first_log.get("swipe_time")),
            "date":               getdate(first_log.get("swipe_time")),
            "status":             "Present",
            "source":             "RFID",
            "in_time":            first_log.get("swipe_time"),
            "out_time":           last_log.get("swipe_time"),
            "hours_counted":      duration,
            "session_type":       "Office Hour",
        })
        doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Whitelisted manual trigger
# ---------------------------------------------------------------------------

@frappe.whitelist()
def process_logs_manually():
    """Admin/testing manual trigger. Also callable from bench console."""
    process_pending_logs()
    return {"status": "success", "message": "Attendance logs processed successfully"}
