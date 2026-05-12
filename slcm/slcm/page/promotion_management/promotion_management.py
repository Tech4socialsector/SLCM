# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime, flt, cint


# ── Filter option helpers ──────────────────────────────────────────────────────

@frappe.whitelist()
def get_programs():
	return frappe.db.get_all("Program", fields=["name", "program_name"], order_by="name asc")


@frappe.whitelist()
def get_academic_years():
	return frappe.db.get_all(
		"Academic Year", fields=["name", "academic_year_name"],
		order_by="year_start_date desc"
	)


@frappe.whitelist()
def get_policies_for_filters(program, academic_year):
	"""Return matching Active policies for given program + academic_year."""
	if not program or not academic_year:
		return []
	return frappe.db.get_all(
		"Promotion Policy",
		filters={"program": program, "academic_year": academic_year, "status": "Active"},
		fields=["name", "title", "from_year", "to_year",
		        "enable_cgpa_check", "min_cgpa",
		        "enable_backlog_check", "max_backlogs_allowed",
		        "enable_attendance_check", "min_attendance_percent",
		        "enable_course_shortage_check", "max_shortage_courses",
		        "enable_cf_check", "max_cf_fa_shortage",
		        "conditional_promotion_action", "auto_update_student_year"],
		order_by="from_year asc",
	)


# ── Core promotion engine ──────────────────────────────────────────────────────

def _evaluate_student(student_row, policy_dict):
	cgpa_result            = "Not Checked"
	backlog_result         = "Not Checked"
	attendance_result      = "Not Checked"
	shortage_course_result = "Not Checked"
	cf_result              = "Not Checked"
	failures               = 0

	if policy_dict.get("enable_cgpa_check"):
		cgpa = flt(student_row.get("current_cgpa") or 0)
		if cgpa >= flt(policy_dict.get("min_cgpa") or 0):
			cgpa_result = "Pass"
		else:
			cgpa_result = "Fail"
			failures += 1

	if policy_dict.get("enable_backlog_check"):
		backlogs = cint(student_row.get("backlog_count") or 0)
		if backlogs <= cint(policy_dict.get("max_backlogs_allowed") or 0):
			backlog_result = "Pass"
		else:
			backlog_result = "Fail"
			failures += 1

	if policy_dict.get("enable_attendance_check"):
		att = flt(student_row.get("attendance_percent") or 0)
		if att >= flt(policy_dict.get("min_attendance_percent") or 0):
			attendance_result = "Pass"
		else:
			attendance_result = "Fail"
			failures += 1

	# Criterion 3: No more than N courses with attendance shortage
	if policy_dict.get("enable_course_shortage_check"):
		shortage_count = cint(student_row.get("shortage_course_count") or 0)
		if shortage_count <= cint(policy_dict.get("max_shortage_courses") or 2):
			shortage_course_result = "Pass"
		else:
			shortage_course_result = "Fail"
			failures += 1

	# Criterion 4: Carry-forward courses with FA applied but still not exam-eligible
	if policy_dict.get("enable_cf_check"):
		cf_shortage = cint(student_row.get("cf_fa_shortage_count") or 0)
		if cf_shortage <= cint(policy_dict.get("max_cf_fa_shortage") or 0):
			cf_result = "Pass"
		else:
			cf_result = "Fail"
			failures += 1

	total_checks = sum([
		bool(policy_dict.get("enable_cgpa_check")),
		bool(policy_dict.get("enable_backlog_check")),
		bool(policy_dict.get("enable_attendance_check")),
		bool(policy_dict.get("enable_course_shortage_check")),
		bool(policy_dict.get("enable_cf_check")),
	])

	if failures == 0:
		status = "Promoted"
	elif failures == total_checks:
		status = "Not Promoted"
	else:
		cond_action = policy_dict.get("conditional_promotion_action") or "Not Promoted"
		status = "Conditional" if "Conditional" in cond_action else "Not Promoted"

	return {
		"cgpa_result":            cgpa_result,
		"backlog_result":         backlog_result,
		"attendance_result":      attendance_result,
		"shortage_course_result": shortage_course_result,
		"cf_result":              cf_result,
		"promotion_status":       status,
	}


def _get_students_raw(program, academic_year, from_year):
	"""
	Fetch active students for the given program + academic_year + from_year
	along with their CGPA, backlog count, and attendance average.
	"""
	from_year_str = str(from_year)

	students = frappe.db.sql(
		"""
		SELECT
			sm.name          AS student,
			sm.first_name    AS first_name,
			sm.last_name     AS last_name,
			sm.current_cgpa  AS current_cgpa,
			sm.programme     AS programme,
			sm.batch_year    AS batch_year,
			sm.current_year  AS current_year,
			c.cohort_name    AS cohort_name
		FROM `tabStudent Master` sm
		INNER JOIN `tabCohort` c ON c.name = sm.programme
		WHERE
			c.program         = %(program)s
			AND c.academic_year = %(academic_year)s
			AND sm.current_year  = %(from_year)s
			AND sm.student_status = 'Active'
		ORDER BY sm.first_name, sm.last_name
		""",
		{"program": program, "academic_year": academic_year, "from_year": from_year_str},
		as_dict=True,
	)

	if not students:
		return []

	student_names = [s["student"] for s in students]

	# Backlog counts (failed courses in exam plans of this academic year)
	backlog_rows = frappe.db.sql(
		"""
		SELECT scm.student, COUNT(*) AS backlog_count
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabExam Plan` ep ON ep.name = scm.exam_plan
		INNER JOIN `tabAcademic Term` at2 ON at2.name = ep.term
		WHERE scm.student IN %(students)s
		  AND at2.academic_year = %(academic_year)s
		  AND scm.status = 'Fail'
		GROUP BY scm.student
		""",
		{"students": student_names, "academic_year": academic_year},
		as_dict=True,
	) if student_names else []
	backlog_map = {r["student"]: r["backlog_count"] for r in backlog_rows}

	# Attendance average (overall %)
	att_rows = frappe.db.sql(
		"""
		SELECT student, AVG(attendance_percentage) AS avg_attendance
		FROM `tabAttendance Summary`
		WHERE student IN %(students)s
		  AND academic_year = %(academic_year)s
		GROUP BY student
		""",
		{"students": student_names, "academic_year": academic_year},
		as_dict=True,
	) if student_names else []
	att_map = {r["student"]: flt(r["avg_attendance"]) for r in att_rows}

	# Criterion 3: Count courses where student has attendance shortage
	# (attendance_percentage < minimum_required_percentage for the course)
	shortage_rows = frappe.db.sql(
		"""
		SELECT student, COUNT(*) AS shortage_count
		FROM `tabAttendance Summary`
		WHERE student IN %(students)s
		  AND academic_year = %(academic_year)s
		  AND attendance_percentage < minimum_required_percentage
		GROUP BY student
		""",
		{"students": student_names, "academic_year": academic_year},
		as_dict=True,
	) if student_names else []
	shortage_map = {r["student"]: cint(r["shortage_count"]) for r in shortage_rows}

	# Criterion 4: Carry-forward FA + shortage check
	# Counts courses where FA/MFA condonation was applied (total_fa_mfa_hours > 0)
	# but student is still not exam-eligible (eligible_for_exam = 0).
	# This identifies carry-forward scenarios where attendance was already condoned
	# yet the student still falls short of the required minimum.
	cf_rows = frappe.db.sql(
		"""
		SELECT student, COUNT(*) AS cf_count
		FROM `tabAttendance Summary`
		WHERE student IN %(students)s
		  AND academic_year = %(academic_year)s
		  AND total_fa_mfa_hours > 0
		  AND eligible_for_exam = 0
		GROUP BY student
		""",
		{"students": student_names, "academic_year": academic_year},
		as_dict=True,
	) if student_names else []
	cf_map = {r["student"]: cint(r["cf_count"]) for r in cf_rows}

	for s in students:
		s["backlog_count"]         = backlog_map.get(s["student"], 0)
		s["attendance_percent"]    = att_map.get(s["student"], 0.0)
		s["shortage_course_count"] = shortage_map.get(s["student"], 0)
		s["cf_fa_shortage_count"]  = cf_map.get(s["student"], 0)
		s["student_name"]          = (
			(s.get("first_name") or "") + " " + (s.get("last_name") or "")
		).strip()

	return students


# ── Public APIs ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def fetch_students(program, academic_year, from_year, policy_name=None):
	"""
	Fetch students for filters and optionally evaluate against a policy.
	If no policy_name, all students are returned as 'Promoted' (no criteria active).
	"""
	students = _get_students_raw(program, academic_year, from_year)

	if not students:
		return {"students": [], "counts": {"total": 0, "promoted": 0, "not_promoted": 0, "conditional": 0}}

	policy_dict = {}
	if policy_name:
		p = frappe.get_doc("Promotion Policy", policy_name)
		policy_dict = p.as_dict()

	results = []
	counts  = {"total": 0, "promoted": 0, "not_promoted": 0, "conditional": 0}

	for s in students:
		evaluation = _evaluate_student(s, policy_dict)
		row = {**s, **evaluation}
		results.append(row)
		counts["total"] += 1
		st = evaluation["promotion_status"]
		if st == "Promoted":
			counts["promoted"] += 1
		elif st == "Not Promoted":
			counts["not_promoted"] += 1
		else:
			counts["conditional"] += 1

	return {"students": results, "counts": counts}


@frappe.whitelist()
def confirm_promotion(program, academic_year, from_year, to_year, policy_name=None):
	"""
	Save promotion results:
	- Auto-creates or reuses a Promotion Policy matching the filters.
	- Deletes old Student Promotion records for this policy (idempotent).
	- Creates new Student Promotion records.
	- Updates term_year on Student Master for Promoted students (if policy allows).
	Returns summary counts.
	"""
	frappe.has_permission("Student Promotion", "create", throw=True)

	from_year = cint(from_year)
	to_year   = cint(to_year)

	# Find or create a matching policy
	if policy_name:
		policy = frappe.get_doc("Promotion Policy", policy_name)
	else:
		existing = frappe.db.get_value(
			"Promotion Policy",
			{"program": program, "academic_year": academic_year,
			 "from_year": from_year, "to_year": to_year},
			"name",
		)
		if existing:
			policy = frappe.get_doc("Promotion Policy", existing)
		else:
			policy = frappe.new_doc("Promotion Policy")
			policy.title        = f"{program} | {academic_year} | Yr {from_year}→{to_year}"
			policy.program      = program
			policy.academic_year = academic_year
			policy.from_year    = from_year
			policy.to_year      = to_year
			policy.status       = "Active"
			policy.auto_update_student_year = 1
			policy.insert(ignore_permissions=True)
			frappe.db.commit()

	policy_dict = policy.as_dict()
	students    = _get_students_raw(program, academic_year, from_year)

	if not students:
		frappe.throw("No active students found for the selected filters.")

	# Remove old records for this policy
	old = frappe.db.get_all("Student Promotion", filters={"promotion_policy": policy.name}, pluck="name")
	for name in old:
		frappe.delete_doc("Student Promotion", name, ignore_permissions=True, force=True)

	promoted_count     = 0
	not_promoted_count = 0
	conditional_count  = 0
	now = now_datetime()

	for s in students:
		ev     = _evaluate_student(s, policy_dict)
		status = ev["promotion_status"]

		doc = frappe.new_doc("Student Promotion")
		doc.promotion_policy   = policy.name
		doc.student            = s["student"]
		doc.student_name       = s["student_name"]
		doc.batch_year         = s.get("batch_year") or ""
		doc.programme          = s.get("programme") or ""
		doc.current_year       = str(from_year)
		doc.target_year        = str(to_year)
		doc.current_cgpa            = flt(s.get("current_cgpa") or 0)
		doc.backlog_count           = cint(s.get("backlog_count") or 0)
		doc.attendance_percent      = flt(s.get("attendance_percent") or 0)
		doc.shortage_course_count   = cint(s.get("shortage_course_count") or 0)
		doc.cf_fa_shortage_count    = cint(s.get("cf_fa_shortage_count") or 0)
		doc.cgpa_result             = ev["cgpa_result"]
		doc.backlog_result          = ev["backlog_result"]
		doc.attendance_result       = ev["attendance_result"]
		doc.shortage_course_result  = ev["shortage_course_result"]
		doc.cf_result               = ev["cf_result"]
		doc.promotion_status        = status
		doc.processed_by       = frappe.session.user
		doc.processed_on       = now
		doc.insert(ignore_permissions=True)

		if status == "Promoted":
			promoted_count += 1
		elif status == "Not Promoted":
			not_promoted_count += 1
		else:
			conditional_count += 1

	# Update Student Master year for promoted students
	if policy.auto_update_student_year:
		promoted_students = frappe.db.get_all(
			"Student Promotion",
			filters={"promotion_policy": policy.name, "promotion_status": "Promoted"},
			pluck="student",
		)
		for sname in promoted_students:
			frappe.db.set_value("Student Master", sname, "term_year", to_year, update_modified=False)

	frappe.db.commit()

	return {
		"policy_name":  policy.name,
		"total":        len(students),
		"promoted":     promoted_count,
		"not_promoted": not_promoted_count,
		"conditional":  conditional_count,
	}


@frappe.whitelist()
def get_saved_results_by_filters(program, academic_year, from_year, to_year):
	"""Return existing saved Student Promotion records for these filters."""
	policy_name = frappe.db.get_value(
		"Promotion Policy",
		{"program": program, "academic_year": academic_year,
		 "from_year": cint(from_year), "to_year": cint(to_year)},
		"name",
	)
	if not policy_name:
		return {"records": [], "policy_name": None}

	records = frappe.db.get_all(
		"Student Promotion",
		filters={"promotion_policy": policy_name},
		fields=[
			"name", "student", "student_name", "batch_year", "programme",
			"current_year", "target_year", "promotion_status",
			"current_cgpa", "backlog_count", "attendance_percent",
			"shortage_course_count", "cf_fa_shortage_count",
			"cgpa_result", "backlog_result", "attendance_result",
			"shortage_course_result", "cf_result",
			"manual_override", "override_reason", "processed_on",
		],
		order_by="student_name asc",
	)
	return {"records": records, "policy_name": policy_name}


@frappe.whitelist()
def save_override(record_name, new_status, reason):
	frappe.has_permission("Student Promotion", "write", throw=True)
	doc = frappe.get_doc("Student Promotion", record_name)
	doc.promotion_status = new_status
	doc.manual_override  = 1
	doc.override_reason  = reason
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def download_promotion_list(policy_name, list_type):
	"""
	Download Excel for:
	  list_type = 'promoted' | 'not_promoted' | 'conditional' | 'all'
	"""
	import io
	try:
		import openpyxl
		from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
	except ImportError:
		frappe.throw("openpyxl is not installed. Run: bench pip install openpyxl")

	status_map = {
		"promoted":     ["Promoted", "Override - Promoted"],
		"not_promoted": ["Not Promoted", "Override - Not Promoted"],
		"conditional":  ["Conditional"],
		"all":          ["Promoted", "Not Promoted", "Conditional",
		                 "Override - Promoted", "Override - Not Promoted"],
	}
	statuses = status_map.get(list_type, ["Promoted"])
	policy   = frappe.get_doc("Promotion Policy", policy_name)

	records = frappe.db.get_all(
		"Student Promotion",
		filters=[
			["promotion_policy", "=", policy_name],
			["promotion_status", "in", statuses],
		],
		fields=[
			"student", "student_name", "batch_year", "current_year", "target_year",
			"promotion_status", "current_cgpa", "backlog_count", "attendance_percent",
			"shortage_course_count", "cf_fa_shortage_count",
			"cgpa_result", "backlog_result", "attendance_result",
			"shortage_course_result", "cf_result",
			"manual_override", "override_reason",
		],
		order_by="promotion_status asc, student_name asc",
	)

	label_map = {
		"promoted":     "Promoted List",
		"not_promoted": "Not Promoted List",
		"conditional":  "Conditional List",
		"all":          "All Students",
	}

	wb  = openpyxl.Workbook()
	ws  = wb.active
	ws.title = label_map.get(list_type, "List")

	hdr_fill = PatternFill("solid", fgColor="1E293B")
	hdr_font = Font(bold=True, color="FFFFFF", size=11)
	ctr      = Alignment(horizontal="center", vertical="center")
	bdr      = Border(
		left=Side(style="thin"), right=Side(style="thin"),
		top=Side(style="thin"),  bottom=Side(style="thin"),
	)
	row_colors = {
		"Promoted":                "D1FAE5",
		"Override - Promoted":     "A7F3D0",
		"Not Promoted":            "FEE2E2",
		"Override - Not Promoted": "FECACA",
		"Conditional":             "FEF3C7",
	}

	# Title
	ws.merge_cells("A1:P1")
	t = ws["A1"]
	t.value = (f"{label_map.get(list_type)} — {policy.title}  "
	           f"({policy.program} | {policy.academic_year} | "
	           f"Year {policy.from_year} → Year {policy.to_year})")
	t.font      = Font(bold=True, size=13, color="0F172A")
	t.alignment = ctr
	ws.row_dimensions[1].height = 22

	ws.merge_cells("A2:P2")
	ws["A2"].value = (f"Promoted: {sum(1 for r in records if 'Promoted' in (r.promotion_status or ''))}   |   "
	                  f"Not Promoted: {sum(1 for r in records if 'Not Promoted' in (r.promotion_status or ''))}   |   "
	                  f"Conditional: {sum(1 for r in records if r.promotion_status == 'Conditional')}   |   "
	                  f"Total: {len(records)}")
	ws["A2"].font = Font(italic=True, size=10, color="475569")
	ws.row_dimensions[2].height = 16

	headers   = ["#", "Student ID", "Student Name", "Batch", "Current Year", "Target Year",
	             "CGPA", "Backlogs", "Attendance %", "Shortage Courses", "CF FA+Shortage",
	             "CGPA Check", "Backlog Check", "Attendance Check", "Shortage Check", "CF Check",
	             "Promotion Status", "Override Reason"]
	col_widths = [5, 18, 28, 14, 14, 14, 10, 12, 14, 16, 16, 14, 15, 18, 16, 14, 22, 30]

	for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
		cell         = ws.cell(row=3, column=ci, value=h)
		cell.fill    = hdr_fill
		cell.font    = hdr_font
		cell.alignment = ctr
		cell.border  = bdr
		ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = w
	ws.row_dimensions[3].height = 18

	for ri, rec in enumerate(records, 1):
		rn   = ri + 3
		rfil = PatternFill("solid", fgColor=row_colors.get(rec.promotion_status, "FFFFFF"))
		vals = [
			ri,
			rec.student,
			rec.student_name,
			rec.batch_year or "",
			rec.current_year or "",
			rec.target_year or "",
			round(flt(rec.current_cgpa), 2),
			cint(rec.backlog_count),
			str(round(flt(rec.attendance_percent), 1)) + "%",
			cint(rec.shortage_course_count),
			cint(rec.cf_fa_shortage_count),
			rec.cgpa_result or "Not Checked",
			rec.backlog_result or "Not Checked",
			rec.attendance_result or "Not Checked",
			rec.shortage_course_result or "Not Checked",
			rec.cf_result or "Not Checked",
			rec.promotion_status,
			rec.override_reason or "",
		]
		for ci, v in enumerate(vals, 1):
			cell         = ws.cell(row=rn, column=ci, value=v)
			cell.fill    = rfil
			cell.border  = bdr
			if ci == 1:
				cell.alignment = ctr

	ws.freeze_panes = "A4"

	output = io.BytesIO()
	wb.save(output)
	output.seek(0)

	frappe.response.filename    = f"{list_type}_{policy_name}.xlsx"
	frappe.response.filecontent = output.read()
	frappe.response.type        = "download"
