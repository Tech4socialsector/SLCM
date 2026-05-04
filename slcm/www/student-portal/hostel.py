import frappe
from frappe.utils import today

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		context.is_guest = True
		return context

	context.is_guest = False
	context.active_page = "hostel"

	student_name = _get_student_name()
	if not student_name:
		context.no_student = True
		_set_nav_defaults(context)
		return context

	context.no_student = False

	try:
		student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
		_set_student_nav(context, student)

		# ── Hostel Profile ────────────────────────────────────────
		profile = frappe.db.get_value(
			"Student Hostel Profile",
			{"student": student_name},
			["current_hostel", "current_room", "current_bed", "status"],
			as_dict=True,
		)
		context.profile = profile or frappe._dict()
		context.is_hosteller = bool(profile and profile.status == "Active")

		if profile and profile.current_hostel:
			hostel_doc = frappe.db.get_value(
				"Hostel", profile.current_hostel,
				["hostel_name", "address", "warden"],
				as_dict=True,
			) or frappe._dict()
			context.hostel_info = hostel_doc
		else:
			context.hostel_info = frappe._dict()

		# ── Complaints ────────────────────────────────────────────
		complaints = frappe.get_all(
			"Hostel Complaint",
			filters={"student": student_name},
			fields=["name", "complaint_type", "severity", "description", "status", "resolution_details", "creation"],
			order_by="creation desc",
			limit=20,
			ignore_permissions=True,
		)
		context.complaints = complaints
		context.open_complaints = sum(1 for c in complaints if c.status in ("Open", "In Progress"))

		# ── Leave Requests ────────────────────────────────────────
		leave_requests = frappe.get_all(
			"Hostel Leave Request",
			filters={"student": student_name},
			fields=["name", "from_date", "to_date", "reason", "status", "approved_by", "creation"],
			order_by="creation desc",
			limit=20,
			ignore_permissions=True,
		)
		context.leave_requests = leave_requests
		context.pending_leaves = sum(1 for l in leave_requests if l.status == "Pending")

		# ── Fines ─────────────────────────────────────────────────
		fines = frappe.get_all(
			"Hostel Fine",
			filters={"student": student_name},
			fields=["name", "reason", "amount", "fine_date", "status", "issued_by"],
			order_by="fine_date desc",
			limit=20,
			ignore_permissions=True,
		)
		context.fines = fines
		context.total_unpaid_fines = sum(f.amount or 0 for f in fines if f.status == "Unpaid")
		context.unpaid_fine_count = sum(1 for f in fines if f.status == "Unpaid")

	except Exception as e:
		frappe.log_error(f"Hostel portal error: {e}", "Student Portal")
		context.portal_error = str(e)
		_set_nav_defaults(context)

	return context


@frappe.whitelist()
def submit_complaint(complaint_type, severity, description):
	student_name = _get_student_name()
	if not student_name:
		frappe.throw("Student record not found")

	doc = frappe.get_doc({
		"doctype": "Hostel Complaint",
		"student": student_name,
		"complaint_type": complaint_type,
		"severity": severity,
		"description": description,
		"status": "Open",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": "Open"}


@frappe.whitelist()
def submit_leave_request(from_date, to_date, reason):
	student_name = _get_student_name()
	if not student_name:
		frappe.throw("Student record not found")

	if from_date > to_date:
		frappe.throw("From Date cannot be after To Date")

	doc = frappe.get_doc({
		"doctype": "Hostel Leave Request",
		"student": student_name,
		"from_date": from_date,
		"to_date": to_date,
		"reason": reason,
		"status": "Pending",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": "Pending"}


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
