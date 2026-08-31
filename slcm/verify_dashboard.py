"""Quick verify: simulate what index.py computes for FAC009"""
import frappe

FACULTY_NAME_DOC = "10"

co_list = frappe.get_all(
    "Course Offering",
    filters={"faculty": FACULTY_NAME_DOC, "status": ["in", ["Open", "Active"]]},
    fields=["name", "course_name", "term_name", "academic_year", "credit_value", "status"],
    order_by="term_name asc, course_name asc",
    ignore_permissions=True,
)
co_names = [c.name for c in co_list]

print(f"Course Offerings: {len(co_list)}")
for co in co_list:
    enr = frappe.db.sql(
        "SELECT COUNT(DISTINCT se.student) AS cnt FROM `tabStudent Enrollment Course` sec "
        "JOIN `tabStudent Enrollment` se ON se.name=sec.parent "
        "WHERE sec.course_offering=%s AND sec.status='Enrolled'",
        co.name, as_dict=True,
    )
    att = frappe.db.sql(
        "SELECT AVG(attendance_percentage) AS avg_pct, COUNT(*) AS sess FROM `tabAttendance Session` "
        "WHERE course_offering=%s AND attendance_marked=1",
        co.name, as_dict=True,
    )
    sc = (enr[0].cnt or 0) if enr else 0
    ap = round(float((att[0].avg_pct or 0) if att else 0), 1)
    sd = (att[0].sess or 0) if att else 0
    print(f"  {co.course_name:30s} | students={sc:3d} | sessions={sd:3d} | avg_att={ap:5.1f}%")

# Total students
total_students = 0
if co_names:
    res = frappe.db.sql(
        "SELECT COUNT(DISTINCT se.student) AS cnt FROM `tabStudent Enrollment Course` sec "
        "JOIN `tabStudent Enrollment` se ON se.name=sec.parent "
        "WHERE sec.course_offering IN %s AND sec.status='Enrolled'",
        (tuple(co_names),), as_dict=True,
    )
    total_students = (res[0].cnt or 0) if res else 0

pending_att = frappe.db.count(
    "Attendance Session",
    filters={"course_offering": ["in", co_names], "attendance_marked": 0,
             "session_date": ["<=", frappe.utils.today()], "session_status": "Scheduled"},
) if co_names else 0

fac = frappe.get_doc("Faculty", FACULTY_NAME_DOC)
fac_display = f"{fac.first_name or ''} {fac.last_name or ''}".strip()
pending_venues = frappe.db.count(
    "Venue Booking",
    filters={"requester_name": ["in", [FACULTY_NAME_DOC, fac_display, fac.email or ""]], "status": "Pending Allotment"},
)

pending_cond = frappe.db.count(
    "Student Attendance Condonation",
    filters={"course_offering": ["in", co_names], "faculty_recommendation": ["in", ["", None]], "final_status": "Pending"},
) if co_names else 0

print(f"\nDashboard Stats:")
print(f"  Total Subjects:       {len(co_list)}")
print(f"  Total Students:       {total_students}")
print(f"  Attendance Pending:   {pending_att}")
print(f"  Venue Bookings Pend.: {pending_venues}")
print(f"  Condonation Pending:  {pending_cond}")
