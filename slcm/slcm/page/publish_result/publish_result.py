# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.utils import now_datetime


@frappe.whitelist()
def get_exam_plans(search=None):
	"""Return exam plans for the plan selector."""
	filters = {}
	if search:
		filters["exam_name"] = ["like", f"%{search}%"]
	return frappe.get_all(
		"Exam Plan",
		filters=filters,
		fields=["name", "exam_name", "term", "status"],
		order_by="creation desc",
	)


@frappe.whitelist()
def get_publish_stats(exam_plan):
	"""Return publish summary stats for the exam plan."""
	if not exam_plan:
		return {}

	total_row = frappe.db.sql(
		"SELECT COUNT(DISTINCT student) AS cnt FROM `tabStudent Course Marks` WHERE exam_plan=%s",
		exam_plan, as_dict=True,
	)
	total = total_row[0]["cnt"] if total_row else 0

	pub_row = frappe.db.sql(
		"SELECT COUNT(*) AS cnt FROM `tabStudent Result Publish` WHERE exam_plan=%s AND is_published=1",
		exam_plan, as_dict=True,
	)
	published = pub_row[0]["cnt"] if pub_row else 0

	return {
		"total":         total,
		"published":     published,
		"not_published": total - published,
	}


@frappe.whitelist()
def get_publish_inst_filter_options(exam_plan):
	"""Return distinct programmes and batches for students in this exam plan."""
	if not exam_plan:
		return {"programmes": [], "batches": []}

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT sm.programme, sm.batch_year
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabStudent Master` sm ON sm.name = scm.student
		WHERE scm.exam_plan = %(exam_plan)s
		""",
		{"exam_plan": exam_plan},
		as_dict=True,
	)
	programmes = sorted(set(r["programme"] for r in rows if r.get("programme")))
	batches    = sorted(set(str(r["batch_year"]) for r in rows if r.get("batch_year")), reverse=True)
	return {"programmes": programmes, "batches": batches}


@frappe.whitelist()
def get_publish_students(exam_plan, search="", page=1, page_length=20,
                         status_filter="all", sort_by="registration_id", sort_order="asc",
                         inst_programmes="", inst_batches=""):
	"""Return paginated students with their publish status for the given exam plan."""
	if not exam_plan:
		return {"students": [], "total": 0}

	page        = int(page)
	page_length = int(page_length)
	offset      = (page - 1) * page_length
	sort_dir    = "DESC" if sort_order == "desc" else "ASC"

	f_programmes = json.loads(inst_programmes) if inst_programmes else []
	f_batches    = json.loads(inst_batches)    if inst_batches    else []

	sort_col_map = {
		"registration_id": "sm.registration_id",
		"name":            "CONCAT_WS(' ', sm.first_name, sm.last_name)",
		"programme":       "sm.programme",
	}
	sort_col = sort_col_map.get(sort_by, "sm.registration_id")

	params      = {"exam_plan": exam_plan}
	extra_cond  = ""
	if search:
		extra_cond += (
			" AND (sm.registration_id LIKE %(search)s"
			" OR sm.first_name LIKE %(search)s"
			" OR sm.last_name LIKE %(search)s)"
		)
		params["search"] = f"%{search}%"

	if status_filter == "published":
		extra_cond += " AND COALESCE(srp.is_published, 0) = 1"
	elif status_filter == "not_published":
		extra_cond += " AND COALESCE(srp.is_published, 0) = 0"

	if f_programmes:
		placeholders = ",".join([f"%(prog_{i})s" for i in range(len(f_programmes))])
		extra_cond += f" AND sm.programme IN ({placeholders})"
		for i, v in enumerate(f_programmes):
			params[f"prog_{i}"] = v
	if f_batches:
		placeholders = ",".join([f"%(batch_{i})s" for i in range(len(f_batches))])
		extra_cond += f" AND sm.batch_year IN ({placeholders})"
		for i, v in enumerate(f_batches):
			params[f"batch_{i}"] = v

	students = frappe.db.sql(
		f"""
		SELECT
			sm.name                                                              AS student,
			sm.registration_id,
			TRIM(CONCAT_WS(' ', sm.first_name,
				COALESCE(NULLIF(sm.middle_name,''), NULL),
				sm.last_name))                                                   AS student_name,
			sm.programme,
			sm.passport_size_photo                                               AS image,
			sm.email,
			COALESCE(srp.is_published, 0)                                        AS is_published,
			srp.published_by,
			srp.published_on,
			srp.unpublished_by,
			srp.unpublished_on
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabStudent Master` sm ON sm.name = scm.student
		LEFT JOIN `tabStudent Result Publish` srp
			ON srp.exam_plan = %(exam_plan)s AND srp.student = sm.name
		WHERE scm.exam_plan = %(exam_plan)s
		{extra_cond}
		GROUP BY scm.student
		ORDER BY {sort_col} {sort_dir}
		LIMIT %(lim)s OFFSET %(off)s
		""",
		{**params, "lim": page_length, "off": offset},
		as_dict=True,
	)

	# Resolve user full names
	for s in students:
		s["published_by_name"]   = frappe.db.get_value("User", s["published_by"],   "full_name") if s.get("published_by")   else None
		s["unpublished_by_name"] = frappe.db.get_value("User", s["unpublished_by"], "full_name") if s.get("unpublished_by") else None

	total_row = frappe.db.sql(
		f"""
		SELECT COUNT(DISTINCT scm.student) AS cnt
		FROM `tabStudent Course Marks` scm
		INNER JOIN `tabStudent Master` sm ON sm.name = scm.student
		LEFT JOIN `tabStudent Result Publish` srp
			ON srp.exam_plan = %(exam_plan)s AND srp.student = sm.name
		WHERE scm.exam_plan = %(exam_plan)s
		{extra_cond}
		""",
		params,
		as_dict=True,
	)
	total = total_row[0]["cnt"] if total_row else 0

	return {"students": students, "total": total}


@frappe.whitelist()
def toggle_publish(exam_plan, student, publish):
	"""Toggle publish status for a single student."""
	if not exam_plan or not student:
		return False

	publish = int(publish)
	user    = frappe.session.user
	now     = now_datetime()

	existing = frappe.db.get_value(
		"Student Result Publish",
		{"exam_plan": exam_plan, "student": student},
		"name",
	)

	if existing:
		updates = {"is_published": publish}
		if publish:
			updates["published_by"]   = user
			updates["published_on"]   = now
		else:
			updates["unpublished_by"] = user
			updates["unpublished_on"] = now
		frappe.db.set_value("Student Result Publish", existing, updates)
	else:
		doc = frappe.get_doc({
			"doctype":        "Student Result Publish",
			"exam_plan":      exam_plan,
			"student":        student,
			"is_published":   publish,
			"published_by":   user if publish else None,
			"published_on":   now  if publish else None,
			"unpublished_by": None if publish else user,
			"unpublished_on": None if publish else now,
		})
		doc.insert(ignore_permissions=True)

	frappe.db.commit()

	full_name = frappe.db.get_value("User", user, "full_name") or user
	if publish:
		return {"published_by_name": full_name, "published_on": str(now),
		        "unpublished_by_name": None,    "unpublished_on": None}
	else:
		return {"published_by_name": None, "published_on": None,
		        "unpublished_by_name": full_name, "unpublished_on": str(now)}


@frappe.whitelist()
def bulk_publish(exam_plan, students, publish):
	"""Bulk publish or unpublish a list of students."""
	if not exam_plan or not students:
		return 0

	if isinstance(students, str):
		students = json.loads(students)

	publish = int(publish)
	count   = 0
	for student in students:
		toggle_publish(exam_plan, student, publish)
		count += 1

	return count
