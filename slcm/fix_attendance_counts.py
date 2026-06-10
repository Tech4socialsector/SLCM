"""
Fix attendance session data:
1. Populate the Attendance Session Student child table
2. Update aggregate counts on each session
3. Create Student Attendance records

Run with: bench --site slcm.local execute slcm.fix_attendance_counts.fix_attendance_counts
"""

import frappe
from frappe.utils import getdate, today
import datetime
import random

FACULTY_NAME_DOC = "10"
CO_NAMES = [
    "Microbiology Fundamentals",
    "Cell Biology & Genetics",
    "Biochemistry – I",
    "Genetics & Cell Biology",
    "Biochemistry Lab",
    "Bioinformatics",
    "Immunology",
]


def get_students_for_offering(co_name):
    rows = frappe.db.sql("""
        SELECT se.student
        FROM `tabStudent Enrollment Course` sec
        JOIN `tabStudent Enrollment` se ON se.name = sec.parent
        WHERE sec.course_offering = %s AND sec.status = 'Enrolled'
    """, co_name, as_dict=True)
    return [r.student for r in rows]


def fix_attendance_counts():
    random.seed(42)
    today_date = getdate(today())

    for co_name in CO_NAMES:
        students = get_students_for_offering(co_name)
        if not students:
            print(f"No students for {co_name}, skipping")
            continue

        student_genders = {}
        for s in students:
            g = frappe.db.get_value("Student Master", s, "gender") or "Male"
            student_genders[s] = g

        # Get all sessions for this offering
        sessions = frappe.get_all(
            "Attendance Session",
            filters={"course_offering": co_name},
            fields=["name", "session_date", "session_status", "attendance_marked"],
            order_by="session_date asc",
        )

        updated = 0
        for sess in sessions:
            session_name = sess.name
            session_date = getdate(sess.session_date)
            is_pending = sess.session_status == "Scheduled"

            if is_pending:
                # Pending session: add students with Absent status, no marks
                existing_children = frappe.db.count("Attendance Session Student", {"parent": session_name})
                if existing_children == 0:
                    for idx_s, student in enumerate(students):
                        frappe.db.sql("""
                            INSERT INTO `tabAttendance Session Student`
                            (name, creation, modified, modified_by, owner, docstatus, idx,
                             student, status, gender, parent, parentfield, parenttype)
                            VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, %s,
                                    %s, 'Absent', %s, %s, 'students', 'Attendance Session')
                        """, (
                            frappe.generate_hash(length=10),
                            idx_s + 1,
                            student,
                            student_genders.get(student, "Male"),
                            session_name,
                        ))
                frappe.db.sql("""
                    UPDATE `tabAttendance Session`
                    SET total_students=%s, present_count=0, absent_count=%s,
                        attendance_marked=0
                    WHERE name=%s
                """, (len(students), len(students), session_name))
                continue

            # Conducted sessions: assign realistic attendance
            existing_children = frappe.db.count("Attendance Session Student", {"parent": session_name})
            if existing_children > 0:
                continue  # Already has data

            present = 0
            absent = 0
            boys = 0
            girls = 0
            days_ago = (today_date - session_date).days

            for idx_s, student in enumerate(students):
                if idx_s < 3:
                    att_prob = 0.55
                elif idx_s < 8:
                    att_prob = 0.75
                else:
                    att_prob = 0.90
                if days_ago > 30:
                    att_prob -= 0.05

                roll = random.random()
                if roll < att_prob:
                    status = "Present"
                    present += 1
                elif roll < att_prob + 0.08:
                    status = "Late"
                    present += 1
                else:
                    status = "Absent"
                    absent += 1

                g = student_genders.get(student, "Male")
                if g == "Male":
                    boys += 1
                else:
                    girls += 1

                frappe.db.sql("""
                    INSERT INTO `tabAttendance Session Student`
                    (name, creation, modified, modified_by, owner, docstatus, idx,
                     student, status, gender, parent, parentfield, parenttype)
                    VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, %s,
                            %s, %s, %s, %s, 'students', 'Attendance Session')
                """, (
                    frappe.generate_hash(length=10),
                    idx_s + 1,
                    student,
                    status,
                    g,
                    session_name,
                ))

            total = len(students)
            pct = round((present / total) * 100, 1) if total else 0.0

            frappe.db.sql("""
                UPDATE `tabAttendance Session`
                SET total_students=%s, present_count=%s, absent_count=%s,
                    total_boys=%s, total_girls=%s, attendance_percentage=%s,
                    attendance_marked=1
                WHERE name=%s
            """, (total, present, absent, boys, girls, pct, session_name))
            updated += 1

        frappe.db.commit()
        print(f"Fixed {updated} sessions for {co_name}")

    # Verify
    total_sessions = frappe.db.count("Attendance Session", {"course_offering": ["in", CO_NAMES]})
    marked = frappe.db.count("Attendance Session", {
        "course_offering": ["in", CO_NAMES],
        "attendance_marked": 1,
    })
    pending = frappe.db.count("Attendance Session", {
        "course_offering": ["in", CO_NAMES],
        "attendance_marked": 0,
        "session_status": "Scheduled",
    })
    total_student_rows = frappe.db.sql("SELECT COUNT(*) FROM `tabAttendance Session Student`")[0][0]

    print(f"\nSummary:")
    print(f"  Total sessions: {total_sessions}")
    print(f"  Marked sessions: {marked}")
    print(f"  Pending sessions: {pending}")
    print(f"  Total attendance rows: {total_student_rows}")

    # Sample check
    sample = frappe.db.sql("""
        SELECT course_offering, session_date, total_students, present_count,
               absent_count, attendance_percentage, attendance_marked
        FROM `tabAttendance Session`
        WHERE course_offering = 'Microbiology Fundamentals'
        ORDER BY session_date DESC LIMIT 5
    """, as_dict=True)
    print("\nSample sessions (Microbiology Fundamentals):")
    for s in sample:
        print(f"  {s.session_date}: {s.present_count}/{s.total_students} ({s.attendance_percentage}%) marked={s.attendance_marked}")
