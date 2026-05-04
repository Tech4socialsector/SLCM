import frappe
from frappe.utils import today

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.is_guest = True
		return context

	context.is_guest = False
	context.active_page = "documents"

	student_name = _get_student_name()
	if not student_name:
		context.no_student = True
		_set_nav_defaults(context)
		return context

	context.no_student = False

	try:
		student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
		_set_student_nav(context, student)

		# ── Existing transcripts ──────────────────────────────────
		transcripts = frappe.get_all(
			"Student Transcript",
			filters={"student": student_name},
			fields=["name", "transcript_type", "status", "generation_date", "generated_by", "remarks"],
			order_by="generation_date desc",
			ignore_permissions=True,
		)
		context.transcripts = transcripts
		context.active_count = sum(1 for t in transcripts if t.status == "Generated")

		# ── Check if student has any published results ────────────
		published_count = frappe.db.count(
			"Student Result Publish",
			{"student": student_name, "is_published": 1},
		)
		context.has_published_results = bool(published_count)

		# ── Latest CGPA ───────────────────────────────────────────
		context.cgpa = round(student.current_cgpa or 0.0, 2)

	except Exception as e:
		frappe.log_error(f"Transcript request portal error: {e}", "Student Portal")
		context.portal_error = str(e)
		_set_nav_defaults(context)

	return context


@frappe.whitelist()
def request_transcript(transcript_type, remarks=""):
	student_name = _get_student_name()
	if not student_name:
		frappe.throw("Student record not found")

	if transcript_type not in ("Interim", "Final"):
		frappe.throw("Invalid transcript type")

	if transcript_type == "Final":
		# Final transcript requires completed academic status
		status = frappe.db.get_value("Student Master", student_name, "academic_status")
		if status not in ("Graduated", "Programme Completed", "Completed"):
			frappe.throw("Final transcripts are only issued after programme completion. Please request an Interim transcript.")

	doc = frappe.get_doc({
		"doctype": "Student Transcript",
		"student": student_name,
		"transcript_type": transcript_type,
		"status": "Generated",
		"generation_date": today(),
		"generated_by": frappe.session.user,
		"remarks": remarks,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": "Generated", "type": transcript_type}


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
