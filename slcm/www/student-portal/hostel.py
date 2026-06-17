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
		student = frappe.get_doc("Student Master", student_name)
		_set_student_nav(context, student)

		# ── Hostel Profile ────────────────────────────────────────
		profile = frappe.db.get_value(
			"Student Hostel Profile",
			{"student": student_name},
			["current_hostel", "current_room", "current_bed", "status"],
			as_dict=True,
		)
		context.profile = profile or frappe._dict()

		# is_hosteller: prefer Student Master flag (set by admin in Residence tab),
		# fall back to Student Hostel Profile status == "Active"
		student_is_hosteller = bool(student.is_hosteller)
		profile_is_active     = bool(profile and profile.status == "Active")
		context.is_hosteller  = student_is_hosteller or profile_is_active

		# Resolve hostel/room/bed — prefer Student Hostel Profile, fall back to Student Master fields
		resolved_hostel = (profile.current_hostel if profile else None) or student.hostel or None
		resolved_room   = (profile.current_room   if profile else None) or student.hostel_room or None
		resolved_bed    = (profile.current_bed    if profile else None) or student.hostel_bed  or None

		# ── Hostel Details ────────────────────────────────────────
		hostel_info = frappe._dict()
		if resolved_hostel:
			h = frappe.db.get_value(
				"Hostel", resolved_hostel,
				["hostel_name", "hostel_code", "hostel_type", "total_rooms", "total_capacity"],
				as_dict=True,
			) or frappe._dict()
			hostel_info.update(h)

			# Warden from child table
			wardens = frappe.get_all(
				"Hostel Warden",
				filters={"parent": resolved_hostel, "parenttype": "Hostel", "status": "Active"},
				fields=["warden_name", "warden_contact", "warden_email"],
				limit=1,
			)
			hostel_info.warden = wardens[0] if wardens else frappe._dict()

		# Expose block / building from Student Master if available
		hostel_info.hostel_block = student.hostel_block or ""
		context.hostel_info = hostel_info

		# ── Room Details ──────────────────────────────────────────
		room_info = frappe._dict()
		if resolved_room:
			r = frappe.db.get_value(
				"Hostel Room", resolved_room,
				["room_number", "floor", "room_type", "capacity"],
				as_dict=True,
			) or frappe._dict()
			room_info.update(r)
		context.room_info = room_info

		# ── Bed Details ───────────────────────────────────────────
		bed_info = frappe._dict()
		if resolved_bed:
			b = frappe.db.get_value(
				"Hostel Bed", resolved_bed,
				["bed_no"],
				as_dict=True,
			) or frappe._dict()
			bed_info.update(b)
		# Fall back to key_number from Student Master if bed name not resolved
		if not bed_info.get("bed_no") and student.get("key_number"):
			bed_info.bed_no = student.key_number
		context.bed_info = bed_info

		# ── Active Allocation ─────────────────────────────────────
		allocation = frappe._dict()
		alloc = frappe.db.get_value(
			"Hostel Allocation",
			{"student": student_name, "is_active": 1},
			["from_date", "to_date", "agreement_signed", "keys_handed_over", "status", "remarks"],
			as_dict=True,
		)
		if alloc:
			allocation.update(alloc)
		else:
			# Populate from Student Master Residence fields directly
			allocation.from_date         = student.get("allocation_date") or None
			allocation.to_date           = student.get("allocation_end_date") or None
			allocation.agreement_signed  = bool(student.get("residence_agreement_signed"))
			allocation.keys_handed_over  = bool(student.get("keys_handed_over"))
			allocation.status            = student.hostel_status or ""
			allocation.remarks           = student.hostel_remarks or ""
		context.allocation = allocation

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
