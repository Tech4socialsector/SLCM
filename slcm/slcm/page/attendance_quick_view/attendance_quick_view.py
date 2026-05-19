import frappe


@frappe.whitelist()
def get_attendance_data(
    programme=None,
    course_offering=None,
    from_date=None,
    to_date=None,
    period=None,
    status=None,
    section=None,
):
    conditions = []
    values = {}

    if from_date:
        conditions.append("sa.attendance_date >= %(from_date)s")
        values["from_date"] = from_date
    if to_date:
        conditions.append("sa.attendance_date <= %(to_date)s")
        values["to_date"] = to_date
    if programme:
        conditions.append("sa.program = %(programme)s")
        values["programme"] = programme
    if course_offering:
        conditions.append("sa.course_offer = %(course_offering)s")
        values["course_offering"] = course_offering
    if period:
        conditions.append("sa.period = %(period)s")
        values["period"] = period
    if status:
        conditions.append("sa.status = %(status)s")
        values["status"] = status
    if section:
        conditions.append("ss.section = %(section)s")
        values["section"] = section

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    section_join = (
        "LEFT JOIN `tabStudent Group` ss ON sa.student_group = ss.name" if section else ""
    )

    data = frappe.db.sql(
        f"""
        SELECT
            sa.name,
            sa.student,
            sa.student_name,
            sa.attendance_date,
            sa.status,
            sa.course,
            sa.program,
            sa.course_offer,
            sa.period,
            sa.session_type,
            sa.in_time,
            sa.out_time,
            sa.student_group,
            sa.attendance_session
        FROM `tabStudent Attendance` sa
        {section_join}
        {where}
        ORDER BY sa.attendance_date DESC, sa.student_name ASC
        LIMIT 500
        """,
        values,
        as_dict=True,
    )

    # summary counts
    total = len(data)
    present = sum(1 for r in data if r.status == "Present")
    absent = sum(1 for r in data if r.status == "Absent")
    late = sum(1 for r in data if r.status == "Late")
    od = sum(1 for r in data if r.status == "OD")
    excused = sum(1 for r in data if r.status == "Excused")

    return {
        "data": data,
        "summary": {
            "total": total,
            "present": present,
            "absent": absent,
            "late": late,
            "od": od,
            "excused": excused,
        },
    }


@frappe.whitelist()
def get_course_offerings(programme=None):
    filters = {}
    if programme:
        filters["program"] = programme
    return frappe.get_all(
        "Course Offering",
        filters=filters,
        fields=["name", "course_title"],
        order_by="course_title asc",
        limit=200,
    )


@frappe.whitelist()
def get_sections(programme=None, course_offering=None):
    filters = {}
    if programme:
        filters["program"] = programme
    return frappe.get_all(
        "Program Batch Section",
        filters=filters,
        fields=["name", "section_name"],
        order_by="section_name asc",
        limit=200,
    )
