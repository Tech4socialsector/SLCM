import frappe
from frappe.utils import nowdate, getdate

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.is_guest = True
		return context

	context.is_guest = False
	context.active_page = "announcements"

	student_name = _get_student_name()
	if not student_name:
		context.no_student = True
		_set_nav_defaults(context)
		return context

	context.no_student = False

	try:
		student = frappe.get_doc("Student Master", student_name)
		_set_student_nav(context, student)

		today_str = nowdate()
		all_records = frappe.get_all(
			"Student Announcement",
			filters=[["is_active", "=", 1], ["publish_date", "<=", today_str]],
			fields=[
				"name", "title", "content", "announcement_type", "priority",
				"publish_date", "expiry_date", "target_audience",
			],
			order_by="priority desc, publish_date desc",
			limit=60,
			ignore_permissions=True,
		)

		announcements = []
		today_date = getdate(today_str)
		for r in all_records:
			if r.expiry_date and getdate(r.expiry_date) < today_date:
				continue

			if r.target_audience == "All Students":
				announcements.append(r)
				continue

			if r.target_audience == "Specific Programme(s)":
				targets = frappe.get_all(
					"Announcement Programme Target",
					filters={"parent": r.name},
					fields=["programme"],
					ignore_permissions=True,
				)
				if any(t.programme == student.programme for t in targets):
					announcements.append(r)

			elif r.target_audience == "Specific Batch Year(s)":
				targets = frappe.get_all(
					"Announcement Batch Target",
					filters={"parent": r.name},
					fields=["batch_year"],
					ignore_permissions=True,
				)
				s_batch = str(student.batch_year or "")
				s_acyr  = str(student.academic_year or "")
				if any(
					str(t.batch_year) == s_batch or (s_acyr and str(t.batch_year) == s_acyr)
					for t in targets
				):
					announcements.append(r)

		priority_icon = {"Urgent": "warning", "Important": "priority_high", "Normal": "campaign"}
		type_icon = {
			"Academic": "school", "Administrative": "admin_panel_settings",
			"Hostel": "hotel", "Placement": "work", "General": "campaign",
		}
		for a in announcements:
			a["priority_icon"] = priority_icon.get(a.priority, "campaign")
			a["type_icon"] = type_icon.get(a.announcement_type, "campaign")

		context.announcements = announcements
		context.total_count = len(announcements)
		context.urgent_count = sum(1 for a in announcements if a.priority == "Urgent")
		context.important_count = sum(1 for a in announcements if a.priority == "Important")

	except Exception as e:
		frappe.log_error(f"Announcements portal error: {e}", "Student Portal")
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
	context.programme_name = frappe.db.get_value("Batch", student.programme, "cohort_name") or student.programme or ""
	context.department = student.department or ""
	context.batch_year = student.batch_year or ""
	context.academic_year = student.academic_year or ""


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
