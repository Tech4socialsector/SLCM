import frappe
from frappe.utils import today

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.is_guest = True
		return context

	context.is_guest = False
	context.active_page = "grade_appeal"

	student_name = _get_student_name()
	if not student_name:
		context.no_student = True
		_set_nav_defaults(context)
		return context

	context.no_student = False

	try:
		student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
		_set_student_nav(context, student)

		# ── Existing appeals ──────────────────────────────────────
		appeals = frappe.get_all(
			"Grade Appeal",
			filters={"student": student_name},
			fields=[
				"name", "exam_plan", "course", "appeal_type", "status",
				"current_grade", "current_marks", "reason", "resolution",
				"submitted_on", "resolved_on",
			],
			order_by="creation desc",
			limit=30,
			ignore_permissions=True,
		)
		for a in appeals:
			a["course_name"] = frappe.db.get_value("Course", a.course, "course_name") or a.course
			a["exam_name"] = frappe.db.get_value("Exam Plan", a.exam_plan, "exam_name") or a.exam_plan

		context.appeals = appeals
		context.active_appeals = sum(1 for a in appeals if a.status in ("Submitted", "Under Review"))

		# ── Published results for the appeal form ─────────────────
		published_marks = frappe.get_all(
			"Student Course Marks",
			filters={"student": student_name, "status": "Locked"},
			fields=["exam_plan", "course", "grade", "total_marks", "updated_final_marks", "updated_grade"],
			ignore_permissions=True,
		)

		# Only show results that have a published result
		published_plans = {r.exam_plan for r in frappe.get_all(
			"Student Result Publish",
			filters={"student": student_name, "is_published": 1},
			fields=["exam_plan"],
			ignore_permissions=True,
		)}

		eligible = []
		for r in published_marks:
			if r.exam_plan not in published_plans:
				continue
			eligible.append({
				"exam_plan": r.exam_plan,
				"exam_name": frappe.db.get_value("Exam Plan", r.exam_plan, "exam_name") or r.exam_plan,
				"course": r.course,
				"course_name": frappe.db.get_value("Course", r.course, "course_name") or r.course,
				"grade": r.updated_grade or r.grade or "—",
				"marks": r.updated_final_marks or r.total_marks or 0,
			})

		context.eligible_results = eligible

	except Exception as e:
		frappe.log_error(f"Grade Appeal portal error: {e}", "Student Portal")
		context.portal_error = str(e)
		_set_nav_defaults(context)

	return context


@frappe.whitelist()
def submit_appeal(exam_plan, course, appeal_type, reason, supporting_remarks=""):
	student_name = _get_student_name()
	if not student_name:
		frappe.throw("Student record not found")

	# Verify the result is published
	is_published = frappe.db.exists(
		"Student Result Publish",
		{"student": student_name, "exam_plan": exam_plan, "is_published": 1},
	)
	if not is_published:
		frappe.throw("You can only appeal published results.")

	marks_doc = frappe.db.get_value(
		"Student Course Marks",
		{"student": student_name, "exam_plan": exam_plan, "course": course},
		["grade", "updated_grade", "total_marks", "updated_final_marks"],
		as_dict=True,
	) or frappe._dict()

	doc = frappe.get_doc({
		"doctype": "Grade Appeal",
		"student": student_name,
		"exam_plan": exam_plan,
		"course": course,
		"appeal_type": appeal_type,
		"reason": reason,
		"supporting_remarks": supporting_remarks,
		"current_grade": marks_doc.updated_grade or marks_doc.grade or "",
		"current_marks": marks_doc.updated_final_marks or marks_doc.total_marks or 0,
		"status": "Submitted",
		"submitted_on": today(),
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": "Submitted"}


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
