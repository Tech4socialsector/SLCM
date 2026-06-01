import frappe

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.is_guest = True
		return context

	context.is_guest = False
	context.active_page = "enrollment"

	student_name = _get_student_name()
	if not student_name:
		context.no_student = True
		_set_nav_defaults(context)
		return context

	context.no_student = False

	try:
		student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
		_set_student_nav(context, student)

		# ── All enrollments ───────────────────────────────────────
		enrollments = frappe.get_all(
			"Student Enrollment",
			filters={"student": student_name},
			fields=["name", "cohort", "program", "academic_year", "term_name", "status",
					"faculty_advisor", "enrollment_date"],
			order_by="creation desc",
			ignore_permissions=True,
		)

		# Mark active enrollment
		context.active_enrollment = None
		for e in enrollments:
			e["is_active"] = e.status == "Enrolled"
			if e["is_active"] and not context.active_enrollment:
				context.active_enrollment = e

		context.enrollments = enrollments

		# ── Course offerings for active enrollment ────────────────
		active_courses = []
		dropped_courses = []
		if context.active_enrollment:
			enrollment_name = context.active_enrollment["name"]

			# Child rows from Student Enrollment Course child table
			prog_rows = frappe.get_all(
				"Student Enrollment Course",
				filters={"parent": enrollment_name},
				fields=["course_offering", "course", "course_type", "credits", "status", "grade"],
				ignore_permissions=True,
			)

			# Fetch Course Offering details in bulk
			co_names = [r.course_offering for r in prog_rows if r.course_offering]
			co_map = {}
			if co_names:
				for co in frappe.get_all(
					"Course Offering",
					filters={"name": ["in", co_names]},
					fields=["name", "course_name", "faculty", "credit_value", "term_name"],
					ignore_permissions=True,
				):
					co_map[co.name] = co

			# Enrich with attendance
			for r in prog_rows:
				co = co_map.get(r.course_offering) or frappe._dict()

				att = frappe.db.get_value(
					"Attendance Summary",
					{"student": student_name, "course_offering": r.course_offering},
					["attendance_percentage", "eligible_for_exam"],
					as_dict=True,
				) or frappe._dict()

				entry = {
					"course": r.course,
					"course_offering": r.course_offering or "",
					"course_name": co.get("course_name") or r.course or "—",
					"course_type": r.course_type or "Core",
					"course_status": r.status or "Enrolled",
					"credits": co.get("credit_value") or r.credits or 0,
					"faculty": co.get("faculty") or "—",
					"term": co.get("term_name") or context.active_enrollment.get("term_name") or "",
					"attendance_pct": round(float(att.get("attendance_percentage") or 0), 1),
					"eligible": bool(att.get("eligible_for_exam")),
				}
				if r.status == "Dropped":
					dropped_courses.append(entry)
				else:
					active_courses.append(entry)

		context.active_courses = active_courses
		context.dropped_courses = dropped_courses
		context.total_credits = sum(c["credits"] for c in active_courses)

		# ── Credit summary ────────────────────────────────────────
		context.core_credits = sum(c["credits"] for c in active_courses if c["course_type"] == "Core")
		context.elective_credits = sum(c["credits"] for c in active_courses if c["course_type"] == "Elective")

	except Exception as e:
		frappe.log_error(f"Enrollment portal error: {e}", "Student Portal")
		context.portal_error = str(e)
		_set_nav_defaults(context)

	return context


def _get_student_name():
	user = frappe.session.user
	name = frappe.db.get_value("Student Master", {"user": user}, "name")
	if not name:
		name = frappe.db.get_value("Student Master", {"email": user}, "name")
	if not name:
		name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
	return name


def _set_student_nav(context, student):
	full_name = " ".join(filter(None, [student.first_name, student.middle_name, student.last_name]))
	context.student_name = full_name or student.name
	context.student_id = student.registration_id or student.name
	context.student_photo = student.passport_size_photo or ""
	context.student_initial = (context.student_name[0]).upper() if context.student_name else "S"
	context.programme_name = frappe.db.get_value("Cohort", student.programme, "cohort_name") or student.programme or ""
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
