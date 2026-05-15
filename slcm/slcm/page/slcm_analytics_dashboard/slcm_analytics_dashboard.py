# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe

# Roles permitted to access the analytics dashboard
_DASHBOARD_ROLES = {
	"System Manager",
	"slcm_Registrar",
	"slcm_Programme Chair",
	"slcm_REGO Officer",
	"slcm_FINO Officer",
	"slcm_Registration Officer",
	"slcm_Hostel Admin",
	"slcm_Placement Officer",
}


def _require_dashboard_access():
	"""Raise PermissionError if the caller lacks a dashboard role."""
	if frappe.session.user == "Administrator":
		return
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not user_roles.intersection(_DASHBOARD_ROLES):
		frappe.throw(
			"You do not have permission to access the SLCM Analytics Dashboard.",
			frappe.PermissionError,
		)


# ── Filter helpers ────────────────────────────────────────────────────────────

def _build_filters(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Return (where_clause, params) tuples for common filter sets."""
	conditions = []
	params = {}

	if academic_year:
		conditions.append("sm.academic_year = %(academic_year)s")
		params["academic_year"] = academic_year

	if student_status:
		conditions.append("sm.student_status = %(student_status)s")
		params["student_status"] = student_status

	if cohort:
		conditions.append("sm.programme = %(cohort)s")
		params["cohort"] = cohort
	elif program:
		# Filter by cohorts belonging to the program
		cohorts = frappe.db.get_all(
			"Cohort",
			filters={"program": program},
			pluck="name",
		)
		if cohorts:
			conditions.append("sm.programme IN %(cohorts)s")
			params["cohorts"] = cohorts
		else:
			conditions.append("1=0")

	return " AND ".join(conditions), params


# ── Public API ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_filter_options():
	"""Return cascading filter options for the dashboard."""
	_require_dashboard_access()
	academic_years = frappe.db.get_all(
		"Academic Year",
		fields=["name", "academic_year_name"],
		order_by="year_start_date desc",
	)

	programs = frappe.db.get_all(
		"Program",
		filters={"program_status": "Active"},
		fields=["name", "program_name", "program_shortcode"],
		order_by="program_name asc",
	)

	cohorts = frappe.db.get_all(
		"Cohort",
		fields=["name", "cohort_name", "program", "academic_year", "batch", "status"],
		order_by="academic_year desc, cohort_name asc",
	)

	terms = frappe.db.get_all(
		"Academic Term",
		fields=["name", "term_name", "academic_year"],
		order_by="term_start_date desc",
	)

	student_statuses = [
		{"value": "Active",    "label": "Active"},
		{"value": "Inactive",  "label": "Inactive"},
		{"value": "Graduated", "label": "Graduated"},
		{"value": "Dropped",   "label": "Dropped"},
		{"value": "Dormant",   "label": "Dormant"},
	]

	return {
		"academic_years": academic_years,
		"programs": programs,
		"cohorts": cohorts,
		"terms": terms,
		"student_statuses": student_statuses,
	}


@frappe.whitelist()
def get_overview_stats(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Executive KPI cards across all modules."""
	_require_dashboard_access()
	where, params = _build_filters(academic_year, term, program, cohort, student_status)
	sm_where = f"WHERE {where}" if where else ""

	# ── Student totals ────────────────────────────────────────────────────────
	student_totals = frappe.db.sql(
		f"""
		SELECT
			COUNT(*) AS total_students,
			SUM(CASE WHEN student_status = 'Active' THEN 1 ELSE 0 END) AS active_students,
			SUM(CASE WHEN student_status = 'Graduated' THEN 1 ELSE 0 END) AS graduated,
			SUM(CASE WHEN student_status = 'Dropped' THEN 1 ELSE 0 END) AS dropped
		FROM `tabStudent Master` sm
		{sm_where}
		""",
		params,
		as_dict=True,
	)[0]

	# ── Attendance rate (last 30 days) ────────────────────────────────────────
	att_filters = {"attendance_date": [">=", frappe.utils.add_days(frappe.utils.today(), -30)]}
	if academic_year:
		att_filters["academic_year"] = academic_year
	if program:
		att_filters["program"] = program

	att_stats = frappe.db.sql(
		"""
		SELECT
			SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count,
			SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
			COUNT(*) AS total_count
		FROM `tabStudent Attendance`
		WHERE attendance_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
		""",
		as_dict=True,
	)[0]

	total_att = att_stats.total_count or 0
	att_rate = round((att_stats.present_count or 0) / total_att * 100, 1) if total_att else 0

	# ── Fee collection ────────────────────────────────────────────────────────
	fee_where_parts = []
	fee_params = {}
	if academic_year:
		fee_where_parts.append("academic_year = %(ay)s")
		fee_params["ay"] = academic_year
	if program:
		fee_where_parts.append("program = %(prog)s")
		fee_params["prog"] = program
	fee_where = ("WHERE " + " AND ".join(fee_where_parts)) if fee_where_parts else ""

	fee_stats = frappe.db.sql(
		f"""
		SELECT
			COALESCE(SUM(total_amount), 0) AS total_billed,
			COALESCE(SUM(paid_amount), 0) AS total_collected,
			COALESCE(SUM(outstanding_amount), 0) AS total_outstanding,
			COUNT(*) AS invoice_count
		FROM `tabFee Invoice`
		{fee_where}
		""",
		fee_params,
		as_dict=True,
	)[0]

	fee_rate = (
		round(fee_stats.total_collected / fee_stats.total_billed * 100, 1)
		if fee_stats.total_billed
		else 0
	)

	# ── Active exams ──────────────────────────────────────────────────────────
	active_exams = frappe.db.count("Exam Plan", filters={"status": "Active"})

	# ── Hostel occupancy ──────────────────────────────────────────────────────
	hostel_allocated = frappe.db.count("Hostel Allocation", filters={"is_active": 1})
	total_beds = frappe.db.count("Hostel Bed")

	# ── Placement offers ──────────────────────────────────────────────────────
	total_offers = frappe.db.count("Placement Offer")
	accepted_offers = frappe.db.count("Placement Offer", filters={"offer_status": "Accepted"})

	return {
		"total_students": student_totals.total_students or 0,
		"active_students": student_totals.active_students or 0,
		"graduated_students": student_totals.graduated or 0,
		"dropped_students": student_totals.dropped or 0,
		"attendance_rate": att_rate,
		"total_attendance_records": total_att,
		"fee_collection_rate": fee_rate,
		"total_billed": fee_stats.total_billed or 0,
		"total_collected": fee_stats.total_collected or 0,
		"total_outstanding": fee_stats.total_outstanding or 0,
		"active_exams": active_exams,
		"hostel_allocated": hostel_allocated,
		"total_beds": total_beds,
		"hostel_occupancy_rate": round(hostel_allocated / total_beds * 100, 1) if total_beds else 0,
		"total_placement_offers": total_offers,
		"accepted_placement_offers": accepted_offers,
		"placement_acceptance_rate": round(accepted_offers / total_offers * 100, 1) if total_offers else 0,
	}


@frappe.whitelist()
def get_student_analytics(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Student enrollment, status distribution, demographics."""
	_require_dashboard_access()
	where, params = _build_filters(academic_year, term, program, cohort, student_status)
	sm_where = f"WHERE {where}" if where else ""
	sm_and = f"AND {where}" if where else ""

	# Status distribution
	status_dist = frappe.db.sql(
		f"""
		SELECT student_status AS label, COUNT(*) AS value
		FROM `tabStudent Master` sm
		{sm_where}
		GROUP BY student_status
		ORDER BY value DESC
		""",
		params,
		as_dict=True,
	)

	# Gender distribution
	gender_dist = frappe.db.sql(
		f"""
		SELECT COALESCE(gender, 'Not Specified') AS label, COUNT(*) AS value
		FROM `tabStudent Master` sm
		{sm_where}
		GROUP BY gender
		ORDER BY value DESC
		""",
		params,
		as_dict=True,
	)

	# Quota distribution
	quota_dist = frappe.db.sql(
		f"""
		SELECT COALESCE(NULLIF(quota, ''), 'Not Set') AS label, COUNT(*) AS value
		FROM `tabStudent Master` sm
		{sm_where}
		GROUP BY quota
		ORDER BY value DESC
		""",
		params,
		as_dict=True,
	)

	# Program-wise enrollment (through Cohort)
	program_dist = frappe.db.sql(
		f"""
		SELECT
			COALESCE(p.program_name, c.program, 'Unknown') AS label,
			COUNT(sm.name) AS value
		FROM `tabStudent Master` sm
		LEFT JOIN `tabCohort` c ON c.name = sm.programme
		LEFT JOIN `tabProgram` p ON p.name = c.program
		{sm_where}
		GROUP BY c.program
		ORDER BY value DESC
		LIMIT 12
		""",
		params,
		as_dict=True,
	)

	# Registration status distribution
	reg_status_dist = frappe.db.sql(
		f"""
		SELECT
			COALESCE(registration_status, 'Not Started') AS label,
			COUNT(*) AS value
		FROM `tabStudent Master` sm
		{sm_where}
		GROUP BY registration_status
		ORDER BY value DESC
		""",
		params,
		as_dict=True,
	)

	# Admission type breakdown
	admission_type_dist = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(admission_type, ''), 'Not Set') AS label,
			COUNT(*) AS value
		FROM `tabStudent Master` sm
		{sm_where}
		GROUP BY admission_type
		ORDER BY value DESC
		""",
		params,
		as_dict=True,
	)

	# Scholarship breakdown
	scholarship_dist = frappe.db.sql(
		f"""
		SELECT
			CASE WHEN applying_scholarship = 'Yes' THEN 'Scholarship' ELSE 'No Scholarship' END AS label,
			COUNT(*) AS value
		FROM `tabStudent Master` sm
		{sm_where}
		GROUP BY applying_scholarship
		""",
		params,
		as_dict=True,
	)

	# Cohort-wise count (top 10)
	cohort_dist = frappe.db.sql(
		f"""
		SELECT
			COALESCE(c.cohort_name, sm.programme, 'Unknown') AS label,
			COUNT(sm.name) AS value
		FROM `tabStudent Master` sm
		LEFT JOIN `tabCohort` c ON c.name = sm.programme
		{sm_where}
		GROUP BY sm.programme
		ORDER BY value DESC
		LIMIT 10
		""",
		params,
		as_dict=True,
	)

	return {
		"status_distribution": status_dist,
		"gender_distribution": gender_dist,
		"quota_distribution": quota_dist,
		"program_distribution": program_dist,
		"registration_status": reg_status_dist,
		"admission_type": admission_type_dist,
		"scholarship_distribution": scholarship_dist,
		"cohort_distribution": cohort_dist,
	}


@frappe.whitelist()
def get_attendance_analytics(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Attendance rates, trends, and pattern analytics."""
	_require_dashboard_access()
	att_where_parts = []
	att_params = {}

	if academic_year:
		att_where_parts.append("academic_year = %(academic_year)s")
		att_params["academic_year"] = academic_year
	if program:
		att_where_parts.append("program = %(program)s")
		att_params["program"] = program
	if term:
		att_where_parts.append("academic_term = %(term)s")
		att_params["term"] = term

	att_where = ("WHERE " + " AND ".join(att_where_parts)) if att_where_parts else ""
	att_and = ("AND " + " AND ".join(att_where_parts)) if att_where_parts else ""

	# Overall status distribution
	status_dist = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabStudent Attendance`
		{att_where}
		GROUP BY status
		ORDER BY value DESC
		""",
		att_params,
		as_dict=True,
	)

	# Monthly trend (last 12 months)
	monthly_trend = frappe.db.sql(
		f"""
		SELECT
			DATE_FORMAT(attendance_date, '%%Y-%%m') AS month,
			DATE_FORMAT(attendance_date, '%%b %%Y') AS month_label,
			SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
			SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent,
			SUM(CASE WHEN status = 'OD' THEN 1 ELSE 0 END) AS od,
			COUNT(*) AS total
		FROM `tabStudent Attendance`
		WHERE attendance_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
			AND attendance_date IS NOT NULL
			{att_and}
		GROUP BY DATE_FORMAT(attendance_date, '%%Y-%%m')
		ORDER BY month ASC
		""",
		att_params,
		as_dict=True,
	)

	# Program-wise attendance rate
	program_attendance = frappe.db.sql(
		f"""
		SELECT
			COALESCE(p.program_name, sa.program, 'Unknown') AS label,
			ROUND(
				SUM(CASE WHEN sa.status = 'Present' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0),
				1
			) AS attendance_rate,
			COUNT(*) AS total_records
		FROM `tabStudent Attendance` sa
		LEFT JOIN `tabProgram` p ON p.name = sa.program
		WHERE sa.program IS NOT NULL AND sa.program != ''
			{att_and}
		GROUP BY sa.program
		HAVING total_records > 10
		ORDER BY attendance_rate DESC
		LIMIT 10
		""",
		att_params,
		as_dict=True,
	)

	# Condonation pipeline — field is `final_status` on this doctype
	cond_stats = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(final_status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabStudent Attendance Condonation`
		GROUP BY final_status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# FA/MFA applications
	fa_mfa_stats = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabFA MFA Application`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Daily attendance for last 30 days (for sparkline)
	daily_trend = frappe.db.sql(
		f"""
		SELECT
			attendance_date AS date,
			SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
			COUNT(*) AS total
		FROM `tabStudent Attendance`
		WHERE attendance_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			AND attendance_date IS NOT NULL
			{att_and}
		GROUP BY attendance_date
		ORDER BY attendance_date ASC
		""",
		att_params,
		as_dict=True,
	)

	return {
		"status_distribution": status_dist,
		"monthly_trend": monthly_trend,
		"program_attendance": program_attendance,
		"condonation_stats": cond_stats,
		"fa_mfa_stats": fa_mfa_stats,
		"daily_trend": daily_trend,
	}


@frappe.whitelist()
def get_examination_analytics(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Exam enrollment, grade distribution, pass/fail analytics."""
	_require_dashboard_access()
	# Exam plan filters
	ep_where_parts = []
	ep_params = {}
	if term:
		ep_where_parts.append("term = %(term)s")
		ep_params["term"] = term

	ep_where = ("WHERE " + " AND ".join(ep_where_parts)) if ep_where_parts else ""

	# Exam plans summary
	exam_plans = frappe.db.sql(
		f"""
		SELECT
			ep.exam_name AS label,
			ep.status,
			COUNT(scm.name) AS enrolled_students
		FROM `tabExam Plan` ep
		LEFT JOIN `tabStudent Course Marks` scm ON scm.exam_plan = ep.name
		{ep_where}
		GROUP BY ep.name
		ORDER BY ep.creation DESC
		LIMIT 15
		""",
		ep_params,
		as_dict=True,
	)

	# Grade distribution
	grade_dist = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(grade, ''), 'Not Graded') AS label,
			COUNT(*) AS value
		FROM `tabStudent Course Marks`
		WHERE status = 'Submitted'
		GROUP BY grade
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Pass/Fail/Detained distribution
	enrollment_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(enrollment_status, ''), 'Enrolled') AS label,
			COUNT(*) AS value
		FROM `tabStudent Course Marks`
		WHERE status = 'Submitted'
		GROUP BY enrollment_status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Exam plan status breakdown
	exam_status = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabExam Plan`
		{ep_where}
		GROUP BY status
		""",
		ep_params,
		as_dict=True,
	)

	# Re-exam statistics
	reexam_stats = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabRe Exam Registration`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Improvement exam stats
	improvement_stats = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabImprovement Exam Registration`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Course-wise submission status
	course_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Draft') AS label,
			COUNT(*) AS value
		FROM `tabStudent Course Marks`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	return {
		"exam_plans": exam_plans,
		"grade_distribution": grade_dist,
		"enrollment_status": enrollment_status,
		"exam_status": exam_status,
		"reexam_stats": reexam_stats,
		"improvement_stats": improvement_stats,
		"course_marks_status": course_status,
	}


@frappe.whitelist()
def get_fees_analytics(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Fee collection, payment status, outstanding analysis."""
	_require_dashboard_access()
	fi_where_parts = []
	fi_params = {}

	if academic_year:
		fi_where_parts.append("academic_year = %(academic_year)s")
		fi_params["academic_year"] = academic_year
	if program:
		fi_where_parts.append("program = %(program)s")
		fi_params["program"] = program

	fi_where = ("WHERE " + " AND ".join(fi_where_parts)) if fi_where_parts else ""
	fi_and = ("AND " + " AND ".join(fi_where_parts)) if fi_where_parts else ""

	# Invoice status distribution — uses `status` field (Unpaid/Partially Paid/Paid/Overdue/Cancelled)
	# NOTE: `payment_status` on Fee Invoice is the Razorpay gateway field, not the invoice status
	payment_status = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value,
			COALESCE(SUM(total_amount), 0) AS amount
		FROM `tabFee Invoice`
		{fi_where}
		GROUP BY status
		ORDER BY value DESC
		""",
		fi_params,
		as_dict=True,
	)

	# Collection summary
	collection_summary = frappe.db.sql(
		f"""
		SELECT
			COALESCE(SUM(total_amount), 0) AS total_billed,
			COALESCE(SUM(paid_amount), 0) AS total_collected,
			COALESCE(SUM(outstanding_amount), 0) AS total_outstanding,
			COUNT(*) AS total_invoices,
			COUNT(DISTINCT student) AS students_billed
		FROM `tabFee Invoice`
		{fi_where}
		""",
		fi_params,
		as_dict=True,
	)[0]

	# Program-wise fee collection
	program_fees = frappe.db.sql(
		f"""
		SELECT
			COALESCE(p.program_name, fi.program, 'Unknown') AS label,
			COALESCE(SUM(fi.total_amount), 0) AS total_billed,
			COALESCE(SUM(fi.paid_amount), 0) AS collected,
			COALESCE(SUM(fi.outstanding_amount), 0) AS outstanding
		FROM `tabFee Invoice` fi
		LEFT JOIN `tabProgram` p ON p.name = fi.program
		WHERE fi.program IS NOT NULL AND fi.program != ''
			{fi_and}
		GROUP BY fi.program
		ORDER BY total_billed DESC
		LIMIT 10
		""",
		fi_params,
		as_dict=True,
	)

	# Monthly collection trend
	monthly_collection = frappe.db.sql(
		f"""
		SELECT
			DATE_FORMAT(invoice_date, '%%Y-%%m') AS month,
			DATE_FORMAT(invoice_date, '%%b %%Y') AS month_label,
			COALESCE(SUM(total_amount), 0) AS billed,
			COALESCE(SUM(paid_amount), 0) AS collected
		FROM `tabFee Invoice`
		WHERE invoice_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
			AND invoice_date IS NOT NULL
			{fi_and}
		GROUP BY DATE_FORMAT(invoice_date, '%%Y-%%m')
		ORDER BY month ASC
		""",
		fi_params,
		as_dict=True,
	)

	# Fee payment status from Student Master
	sm_fee_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(fee_payment_status, ''), 'Not Set') AS label,
			COUNT(*) AS value
		FROM `tabStudent Master`
		GROUP BY fee_payment_status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	return {
		"payment_status_distribution": payment_status,
		"collection_summary": collection_summary,
		"program_fees": program_fees,
		"monthly_collection": monthly_collection,
		"student_fee_payment_status": sm_fee_status,
	}


@frappe.whitelist()
def get_hostel_analytics(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Hostel occupancy, room allocation, and complaint analytics."""
	_require_dashboard_access()
	# Room summary
	room_summary = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS total_rooms,
			SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS occupied_rooms
		FROM `tabHostel Allocation`
		""",
		as_dict=True,
	)[0]

	total_beds = frappe.db.count("Hostel Bed")
	occupied_beds = frappe.db.count("Hostel Allocation", filters={"is_active": 1})

	# Per-hostel occupancy
	hostel_occupancy = frappe.db.sql(
		"""
		SELECT
			COALESCE(h.hostel_name, ha.hostel, 'Unknown') AS label,
			COUNT(ha.name) AS value
		FROM `tabHostel Allocation` ha
		LEFT JOIN `tabHostel` h ON h.name = ha.hostel
		WHERE ha.is_active = 1
		GROUP BY ha.hostel
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Allocation status
	allocation_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabHostel Allocation`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Complaint analytics
	complaint_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabHostel Complaint`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Complaint types
	complaint_type = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(complaint_type, ''), 'Other') AS label,
			COUNT(*) AS value
		FROM `tabHostel Complaint`
		GROUP BY complaint_type
		ORDER BY value DESC
		LIMIT 8
		""",
		as_dict=True,
	)

	# Meal plan distribution
	meal_dist = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(meal_plan, ''), 'Not Set') AS label,
			COUNT(*) AS value
		FROM `tabStudent Master`
		WHERE is_hosteller = 1
		GROUP BY meal_plan
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Leave request status
	leave_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabHostel Leave Request`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	return {
		"total_beds": total_beds,
		"occupied_beds": occupied_beds,
		"available_beds": max(0, total_beds - occupied_beds),
		"occupancy_rate": round(occupied_beds / total_beds * 100, 1) if total_beds else 0,
		"hostel_occupancy": hostel_occupancy,
		"allocation_status": allocation_status,
		"complaint_status": complaint_status,
		"complaint_type": complaint_type,
		"meal_distribution": meal_dist,
		"leave_request_status": leave_status,
	}


@frappe.whitelist()
def get_placement_analytics(academic_year=None, term=None, program=None, cohort=None, student_status=None):
	"""Placement opportunity pipeline, applications, and offers."""
	_require_dashboard_access()
	# Opportunity summary
	opportunity_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabPlacement Opportunity`
		GROUP BY status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Opportunity type breakdown
	opportunity_type = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(opportunity_type, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabPlacement Opportunity`
		GROUP BY opportunity_type
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Application funnel
	application_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(application_status, ''), 'Unknown') AS label,
			COUNT(*) AS value
		FROM `tabPlacement Application`
		GROUP BY application_status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Offer status
	offer_status = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(offer_status, ''), 'Unknown') AS label,
			COUNT(*) AS value,
			COALESCE(SUM(compensation), 0) AS total_compensation
		FROM `tabPlacement Offer`
		GROUP BY offer_status
		ORDER BY value DESC
		""",
		as_dict=True,
	)

	# Top companies by offers
	top_companies = frappe.db.sql(
		"""
		SELECT
			COALESCE(c.company_name, po.company, 'Unknown') AS label,
			COUNT(pof.name) AS offer_count,
			COALESCE(SUM(pof.compensation), 0) AS total_compensation
		FROM `tabPlacement Offer` pof
		LEFT JOIN `tabPlacement Opportunity` po ON po.name = pof.opportunity
		LEFT JOIN `tabCompany` c ON c.name = po.company
		GROUP BY po.company
		ORDER BY offer_count DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	# Summary stats
	total_opportunities = frappe.db.count("Placement Opportunity")
	total_applications = frappe.db.count("Placement Application")
	total_offers = frappe.db.count("Placement Offer")
	accepted_offers = frappe.db.count("Placement Offer", filters={"offer_status": "Accepted"})

	avg_compensation = frappe.db.sql(
		"""
		SELECT COALESCE(AVG(compensation), 0) AS avg_comp
		FROM `tabPlacement Offer`
		WHERE offer_status = 'Accepted' AND compensation > 0
		""",
		as_dict=True,
	)[0].get("avg_comp", 0)

	return {
		"opportunity_status": opportunity_status,
		"opportunity_type": opportunity_type,
		"application_funnel": application_status,
		"offer_status": offer_status,
		"top_companies": top_companies,
		"total_opportunities": total_opportunities,
		"total_applications": total_applications,
		"total_offers": total_offers,
		"accepted_offers": accepted_offers,
		"avg_compensation": round(avg_compensation, 0),
		"placement_rate": round(accepted_offers / total_applications * 100, 1) if total_applications else 0,
	}


@frappe.whitelist()
def get_drilldown_data(module, dimension, value, academic_year=None, term=None, program=None,
					   cohort=None, student_status=None, page=1, page_size=25):
	"""Generic drilldown — returns a detailed record list for chart click-throughs."""
	_require_dashboard_access()
	page     = int(page)
	page_size = int(page_size)
	offset   = (page - 1) * page_size

	# ── Students ──────────────────────────────────────────────────────────────
	if module == "students":
		if dimension == "student_status":
			filters = {"student_status": value}
			if academic_year:
				filters["academic_year"] = academic_year
			rows = frappe.db.get_all(
				"Student Master", filters=filters,
				fields=["registration_id", "first_name", "last_name", "programme",
						"academic_year", "gender", "student_status", "email", "phone"],
				limit_start=offset, limit_page_length=page_size, order_by="registration_id asc",
			)
			total = frappe.db.count("Student Master", filters=filters)
			return {"rows": rows, "total": total,
					"columns": ["registration_id", "first_name", "last_name", "programme",
								"academic_year", "gender", "student_status"]}

		elif dimension == "gender":
			filters = {"gender": value}
			if academic_year:
				filters["academic_year"] = academic_year
			rows = frappe.db.get_all(
				"Student Master", filters=filters,
				fields=["registration_id", "first_name", "last_name", "programme",
						"gender", "student_status", "academic_year"],
				limit_start=offset, limit_page_length=page_size, order_by="registration_id asc",
			)
			total = frappe.db.count("Student Master", filters=filters)
			return {"rows": rows, "total": total,
					"columns": ["registration_id", "first_name", "last_name",
								"programme", "gender", "student_status"]}

		elif dimension == "program":
			rows = frappe.db.sql(
				"""
				SELECT sm.registration_id, sm.first_name, sm.last_name,
					   p.program_name, sm.academic_year, sm.student_status
				FROM `tabStudent Master` sm
				LEFT JOIN `tabCohort` c ON c.name = sm.programme
				LEFT JOIN `tabProgram` p ON p.name = c.program
				WHERE p.program_name = %(value)s OR c.program = %(value)s
				ORDER BY sm.registration_id ASC
				LIMIT %(limit)s OFFSET %(offset)s
				""",
				{"value": value, "limit": page_size, "offset": offset}, as_dict=True,
			)
			cnt = frappe.db.sql(
				"""
				SELECT COUNT(*) FROM `tabStudent Master` sm
				LEFT JOIN `tabCohort` c ON c.name = sm.programme
				LEFT JOIN `tabProgram` p ON p.name = c.program
				WHERE p.program_name = %(value)s OR c.program = %(value)s
				""",
				{"value": value},
			)
			total = cnt[0][0] if cnt else 0
			return {"rows": rows, "total": total,
					"columns": ["registration_id", "first_name", "last_name",
								"program_name", "academic_year", "student_status"]}

		elif dimension == "programs_list":
			rows = frappe.db.sql(
				"""
				SELECT p.program_name AS label, p.name AS program_id,
					   COUNT(sm.name) AS total_students,
					   SUM(CASE WHEN sm.student_status='Active' THEN 1 ELSE 0 END) AS active,
					   SUM(CASE WHEN sm.student_status='Graduated' THEN 1 ELSE 0 END) AS graduated
				FROM `tabProgram` p
				LEFT JOIN `tabCohort` c ON c.program = p.name
				LEFT JOIN `tabStudent Master` sm ON sm.programme = c.name
				GROUP BY p.name
				HAVING total_students > 0
				ORDER BY total_students DESC
				LIMIT %(limit)s OFFSET %(offset)s
				""",
				{"limit": page_size, "offset": offset}, as_dict=True,
			)
			total = frappe.db.count("Program")
			return {"rows": rows, "total": total,
					"columns": ["label", "total_students", "active", "graduated"]}

		elif dimension == "cohorts_list":
			rows = frappe.db.sql(
				"""
				SELECT c.cohort_name AS label, c.name AS cohort_id,
					   p.program_name, c.batch, c.status,
					   COUNT(sm.name) AS total_students
				FROM `tabCohort` c
				LEFT JOIN `tabProgram` p ON p.name = c.program
				LEFT JOIN `tabStudent Master` sm ON sm.programme = c.name
				GROUP BY c.name
				HAVING total_students > 0
				ORDER BY total_students DESC
				LIMIT %(limit)s OFFSET %(offset)s
				""",
				{"limit": page_size, "offset": offset}, as_dict=True,
			)
			total = frappe.db.count("Cohort")
			return {"rows": rows, "total": total,
					"columns": ["label", "program_name", "batch", "status", "total_students"]}

	# ── Attendance ────────────────────────────────────────────────────────────
	elif module == "attendance":
		att_filters = {}
		if dimension == "status" and value and value != "all":
			att_filters["status"] = value
		if academic_year:
			att_filters["academic_year"] = academic_year
		if program:
			att_filters["program"] = program
		if term:
			att_filters["academic_term"] = term

		rows = frappe.db.get_all(
			"Student Attendance", filters=att_filters,
			fields=["student", "student_name", "attendance_date", "status",
					"course", "program", "academic_term", "session_type"],
			limit_start=offset, limit_page_length=page_size,
			order_by="attendance_date desc",
		)
		total = frappe.db.count("Student Attendance", filters=att_filters)
		return {"rows": rows, "total": total,
				"columns": ["student", "student_name", "attendance_date", "status",
							"course", "program", "session_type"]}

	# ── Examination ──────────────────────────────────────────────────────────
	elif module == "examination":
		if dimension == "grade":
			filters = {"grade": value, "status": "Submitted"}
			rows = frappe.db.get_all(
				"Student Course Marks", filters=filters,
				fields=["student", "course", "grade", "total_marks",
						"enrollment_status", "exam_plan"],
				limit_start=offset, limit_page_length=page_size, order_by="student asc",
			)
			total = frappe.db.count("Student Course Marks", filters=filters)
			return {"rows": rows, "total": total,
					"columns": ["student", "course", "grade", "total_marks",
								"enrollment_status", "exam_plan"]}

		elif dimension == "marks_status":
			filters = {}
			if value and value != "all":
				filters["status"] = value
			rows = frappe.db.get_all(
				"Student Course Marks", filters=filters,
				fields=["student", "course", "grade", "total_marks",
						"status", "enrollment_status", "exam_plan"],
				limit_start=offset, limit_page_length=page_size, order_by="student asc",
			)
			total = frappe.db.count("Student Course Marks", filters=filters)
			return {"rows": rows, "total": total,
					"columns": ["student", "course", "grade", "total_marks",
								"status", "enrollment_status", "exam_plan"]}

		elif dimension == "exam_plans":
			ep_filters = {}
			if value and value != "all":
				ep_filters["status"] = value
			if term:
				ep_filters["term"] = term
			rows = frappe.db.get_all(
				"Exam Plan", filters=ep_filters,
				fields=["name", "exam_name", "term", "status"],
				limit_start=offset, limit_page_length=page_size, order_by="creation desc",
			)
			# Enrich with enrolled count
			for r in rows:
				r["enrolled_students"] = frappe.db.count(
					"Student Course Marks", filters={"exam_plan": r["name"]}
				)
			total = frappe.db.count("Exam Plan", filters=ep_filters)
			return {"rows": rows, "total": total,
					"columns": ["exam_name", "term", "status", "enrolled_students"]}

	# ── Fees ──────────────────────────────────────────────────────────────────
	elif module == "fees":
		if dimension == "payment_status":
			fi_filters = {}
			if value and value not in ("all", "All"):
				fi_filters["status"] = value
			if academic_year:
				fi_filters["academic_year"] = academic_year
			if program:
				fi_filters["program"] = program
			rows = frappe.db.get_all(
				"Fee Invoice", filters=fi_filters,
				fields=["name", "student", "student_name", "program",
						"total_amount", "paid_amount", "outstanding_amount",
						"status", "invoice_date"],
				limit_start=offset, limit_page_length=page_size, order_by="invoice_date desc",
			)
			total = frappe.db.count("Fee Invoice", filters=fi_filters)
			return {"rows": rows, "total": total,
					"columns": ["name", "student_name", "program", "total_amount",
								"paid_amount", "outstanding_amount", "status"]}

		elif dimension == "students_billed":
			rows = frappe.db.sql(
				"""
				SELECT fi.student,
					   sm.registration_id,
					   CONCAT_WS(' ', sm.first_name, sm.last_name) AS student_name,
					   fi.program,
					   COALESCE(SUM(fi.total_amount),      0) AS total_billed,
					   COALESCE(SUM(fi.paid_amount),       0) AS total_paid,
					   COALESCE(SUM(fi.outstanding_amount),0) AS outstanding,
					   COUNT(fi.name) AS invoice_count
				FROM `tabFee Invoice` fi
				LEFT JOIN `tabStudent Master` sm ON sm.name = fi.student
				GROUP BY fi.student
				ORDER BY outstanding DESC
				LIMIT %(limit)s OFFSET %(offset)s
				""",
				{"limit": page_size, "offset": offset}, as_dict=True,
			)
			total = frappe.db.count("Fee Invoice")
			return {"rows": rows, "total": total,
					"columns": ["registration_id", "student_name", "program",
								"total_billed", "total_paid", "outstanding", "invoice_count"]}

	# ── Hostel ────────────────────────────────────────────────────────────────
	elif module == "hostel":
		if dimension in ("hostel", "active_allocations"):
			ha_filters = {"is_active": 1}
			if dimension == "hostel" and value and value != "all":
				ha_filters["hostel"] = value
			rows = frappe.db.get_all(
				"Hostel Allocation", filters=ha_filters,
				fields=["student", "hostel", "room", "bed", "from_date", "to_date", "status"],
				limit_start=offset, limit_page_length=page_size,
				order_by="hostel asc, room asc",
			)
			total = frappe.db.count("Hostel Allocation", filters=ha_filters)
			return {"rows": rows, "total": total,
					"columns": ["student", "hostel", "room", "bed", "from_date", "status"]}

		elif dimension == "all_beds":
			rows = frappe.db.get_all(
				"Hostel Bed",
				fields=["name", "hostel", "room", "bed_number", "is_occupied"],
				limit_start=offset, limit_page_length=page_size,
				order_by="hostel asc, room asc",
			)
			total = frappe.db.count("Hostel Bed")
			return {"rows": rows, "total": total,
					"columns": ["name", "hostel", "room", "bed_number", "is_occupied"]}

		elif dimension == "available_beds":
			rows = frappe.db.sql(
				"""
				SELECT hb.name, hb.hostel, hb.room, hb.bed_number
				FROM `tabHostel Bed` hb
				WHERE NOT EXISTS (
					SELECT 1 FROM `tabHostel Allocation` ha
					WHERE ha.bed = hb.name AND ha.is_active = 1
				)
				ORDER BY hb.hostel ASC, hb.room ASC
				LIMIT %(limit)s OFFSET %(offset)s
				""",
				{"limit": page_size, "offset": offset}, as_dict=True,
			)
			total_cnt = frappe.db.sql(
				"""
				SELECT COUNT(*) FROM `tabHostel Bed` hb
				WHERE NOT EXISTS (
					SELECT 1 FROM `tabHostel Allocation` ha
					WHERE ha.bed = hb.name AND ha.is_active = 1
				)
				"""
			)
			total = total_cnt[0][0] if total_cnt else 0
			return {"rows": rows, "total": total,
					"columns": ["name", "hostel", "room", "bed_number"]}

	# ── Placement ─────────────────────────────────────────────────────────────
	elif module == "placement":
		if dimension == "company":
			rows = frappe.db.sql(
				"""
				SELECT pof.student, pof.opportunity, pof.offered_role,
					   pof.compensation, pof.offer_status,
					   COALESCE(c.company_name, po.company) AS company_name
				FROM `tabPlacement Offer` pof
				LEFT JOIN `tabPlacement Opportunity` po ON po.name = pof.opportunity
				LEFT JOIN `tabCompany` c ON c.name = po.company
				WHERE po.company = %(value)s OR c.company_name = %(value)s
				LIMIT %(limit)s OFFSET %(offset)s
				""",
				{"value": value, "limit": page_size, "offset": offset}, as_dict=True,
			)
			total = len(rows)
			return {"rows": rows, "total": total,
					"columns": ["student", "company_name", "offered_role",
								"compensation", "offer_status"]}

		elif dimension == "offer_status":
			filters = {}
			if value and value != "all":
				filters["offer_status"] = value
			rows = frappe.db.get_all(
				"Placement Offer", filters=filters,
				fields=["student", "opportunity", "offered_role", "location",
						"compensation", "offer_status", "decision_date"],
				limit_start=offset, limit_page_length=page_size, order_by="decision_date desc",
			)
			total = frappe.db.count("Placement Offer", filters=filters)
			return {"rows": rows, "total": total,
					"columns": ["student", "opportunity", "offered_role",
								"location", "compensation", "offer_status"]}

		elif dimension == "application_status":
			filters = {}
			if value and value != "all":
				filters["application_status"] = value
			rows = frappe.db.get_all(
				"Placement Application", filters=filters,
				fields=["student", "opportunity", "application_status", "applied_on", "remarks"],
				limit_start=offset, limit_page_length=page_size, order_by="applied_on desc",
			)
			total = frappe.db.count("Placement Application", filters=filters)
			return {"rows": rows, "total": total,
					"columns": ["student", "opportunity", "application_status", "applied_on"]}

		elif dimension == "opportunity_status":
			opp_filters = {}
			if value and value != "all":
				opp_filters["status"] = value
			rows = frappe.db.get_all(
				"Placement Opportunity", filters=opp_filters,
				fields=["name", "company", "opportunity_type", "compensation",
						"location", "status", "application_start", "application_end"],
				limit_start=offset, limit_page_length=page_size, order_by="application_start desc",
			)
			# Enrich with applicant count
			for r in rows:
				r["applicants"] = frappe.db.count(
					"Placement Application", filters={"opportunity": r["name"]}
				)
			total = frappe.db.count("Placement Opportunity", filters=opp_filters)
			return {"rows": rows, "total": total,
					"columns": ["name", "company", "opportunity_type", "compensation",
								"location", "status", "applicants"]}

	return {"rows": [], "total": 0, "columns": [],
			"message": "No drilldown configured for this dimension."}
