import frappe
from frappe.utils import today

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.is_guest = True
		return context

	context.is_guest = False
	context.active_page = "grievance"

	student_name = _get_student_name()
	if not student_name:
		context.no_student = True
		_set_nav_defaults(context)
		context.grievances = []
		return context

	context.no_student = False

	try:
		student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
		_set_student_nav(context, student)

		grievances = frappe.get_all(
			"Student Grievance",
			filters={"student": student_name},
			fields=[
				"name", "grievance_type", "priority", "subject",
				"status", "submitted_on", "resolution_details", "resolved_on",
			],
			order_by="creation desc",
			limit=50,
			ignore_permissions=True,
		)

		context.grievances = grievances
		context.total_count = len(grievances)
		context.open_count = sum(1 for g in grievances if g.status in ("Open", "Under Review"))
		context.resolved_count = sum(1 for g in grievances if g.status == "Resolved")

		context.grievance_types = [
			"Academic", "Administrative", "Faculty",
			"Infrastructure", "Examination", "Other",
		]
		context.priorities = ["Low", "Medium", "High", "Urgent"]

	except Exception as e:
		frappe.log_error(f"Grievance portal error: {e}", "Student Portal")
		context.portal_error = str(e)
		_set_nav_defaults(context)
		context.grievances = []

	return context


@frappe.whitelist()
def submit_grievance(grievance_type, subject, description, priority="Medium"):
	student_name = _get_student_name()
	if not student_name:
		frappe.throw("Student record not found")

	doc = frappe.get_doc({
		"doctype": "Student Grievance",
		"student": student_name,
		"grievance_type": grievance_type,
		"subject": subject,
		"description": description,
		"priority": priority,
		"status": "Open",
		"submitted_on": today(),
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": "Open"}


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
