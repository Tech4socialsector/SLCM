# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, cint, flt

from slcm.slcm.page.promotion_management.promotion_management import (
	_evaluate_student,
	_get_students_raw,
)

BATCH_SIZE = 25
ALLOWED_ROLES = ("System Manager", "slcm_Academic Incharge")


def _resolve_target_batch(current_batch, target_academic_year, target_term=None):
	"""Resolve the Batch to promote into, honoring the target academic year
	the user picked on the Promotion Run (unlike the generic
	promotion_management._resolve_next_batch, which always auto-picks the
	chronologically-next Academic Year)."""
	batch = frappe.db.get_value(
		"Batch", current_batch, ["program", "section", "term_year"], as_dict=True
	)
	if not batch or not batch.section or batch.term_year is None:
		return None

	filters = {
		"program": batch.program,
		"section": batch.section,
		"term_year": cint(batch.term_year) + 1,
		"academic_year": target_academic_year,
	}
	if target_term:
		filters["academic_term"] = target_term

	return frappe.db.get_value("Batch", filters, "name")


class PromotionRun(Document):
	pass


def _check_permission():
	if not (set(ALLOWED_ROLES) & set(frappe.get_roles())):
		frappe.throw(
			frappe._("You are not permitted to run student promotions."),
			frappe.PermissionError,
		)


def _has_fee_due(student):
	return bool(
		frappe.db.exists(
			"Fee Demand",
			{"student": student, "status": ["in", ["Pending", "Partially Paid", "Overdue"]]},
		)
	)


def _reason_for_skip(evaluation, student):
	"""Map a failed evaluation to a structured reason_code + human detail."""
	checks = [
		("attendance_result", "Attendance Shortage", "attendance_percent"),
		("backlog_result", "Backlog", "backlog_count"),
		("cgpa_result", "CGPA Shortfall", "current_cgpa"),
		("shortage_course_result", "Attendance Shortage", "shortage_course_count"),
		("cf_result", "Backlog", "cf_fa_shortage_count"),
	]
	for result_key, reason_code, _val_key in checks:
		if evaluation.get(result_key) == "Fail":
			return reason_code, f"{result_key.replace('_', ' ').title()} did not meet policy criteria."
	return "Other", "Did not meet promotion policy criteria."


@frappe.whitelist()
def get_target_options(program, source_academic_year, from_batch=None):
	"""Populate target academic year / term choices for the dialog."""
	_check_permission()
	years = frappe.db.get_all(
		"Academic Year", fields=["name", "academic_year_name"], order_by="year_start_date desc"
	)
	terms = frappe.db.get_all(
		"Academic Term", fields=["name", "term_name"], order_by="sequence asc"
	)
	policies = frappe.db.get_all(
		"Promotion Policy",
		filters={"program": program, "academic_year": source_academic_year, "status": "Active"},
		fields=["name", "title"],
	)
	return {"academic_years": years, "terms": terms, "policies": policies}


def _matching_enrollments(program, source_academic_year, batch=None, section=None):
	"""Enrolled students matching the source criteria, restricted to the given program."""
	filters = {"status": "Enrolled", "academic_year": source_academic_year}
	if batch:
		filters["batch"] = batch
	if section:
		filters["section"] = section

	enrollments = frappe.db.get_all(
		"Student Enrollment",
		filters=filters,
		fields=["name", "student", "student_name", "batch"],
	)
	if not enrollments:
		return []

	batch_names = list({e.batch for e in enrollments if e.batch})
	program_map = {
		b.name: b.program
		for b in frappe.db.get_all("Batch", filters={"name": ["in", batch_names]}, fields=["name", "program"])
	} if batch_names else {}

	return [e for e in enrollments if program_map.get(e.batch) == program]


def _academic_years_with_enrollments(program):
	"""Which Academic Years actually have Enrolled students for this program —
	used to give a helpful hint when a chosen Academic Year matches nothing
	(e.g. picking a near-duplicate Academic Year record by mistake)."""
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT se.academic_year AS academic_year, COUNT(*) AS student_count
		FROM `tabStudent Enrollment` se
		INNER JOIN `tabBatch` b ON b.name = se.batch
		WHERE se.status = 'Enrolled' AND b.program = %(program)s
		GROUP BY se.academic_year
		ORDER BY se.academic_year DESC
		""",
		{"program": program},
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def preview_students(program, source_academic_year, batch=None, section=None, promotion_policy=None):
	"""Return the Enrolled students matching the source criteria, with a quick
	eligibility hint per student if a Promotion Policy is selected, so the user
	can review and pick exactly who to promote before starting the run."""
	_check_permission()
	if not program or not source_academic_year:
		frappe.throw(frappe._("Programme and Source Academic Year are required."))

	enrollments = _matching_enrollments(program, source_academic_year, batch, section)
	if not enrollments:
		return {"students": [], "available_academic_years": _academic_years_with_enrollments(program)}

	policy_dict = {}
	if promotion_policy:
		policy_dict = frappe.get_doc("Promotion Policy", promotion_policy).as_dict()

	eval_map = {}
	if policy_dict:
		batch_ids = list({e.batch for e in enrollments if e.batch})
		from_years = {
			b.name: cint(b.term_year)
			for b in frappe.db.get_all("Batch", filters={"name": ["in", batch_ids]}, fields=["name", "term_year"])
		} if batch_ids else {}
		for from_year in set(from_years.values()):
			for row in _get_students_raw(program, source_academic_year, from_year):
				eval_map[row["student"]] = _evaluate_student(row, policy_dict)

	fee_gated = bool(policy_dict.get("block_on_fee_due"))

	results = []
	for e in enrollments:
		likely_eligible = True
		hint = None
		if policy_dict:
			evaluation = eval_map.get(e.student)
			if evaluation is None:
				likely_eligible = False
				hint = "No academic data found for this term"
			elif evaluation.get("promotion_status") != "Promoted":
				likely_eligible = False
				_, hint = _reason_for_skip(evaluation, e.student)
			elif fee_gated and _has_fee_due(e.student):
				likely_eligible = False
				hint = "Fee Due"
		results.append({
			"student": e.student,
			"student_name": e.student_name,
			"enrollment": e.name,
			"batch": e.batch,
			"likely_eligible": likely_eligible,
			"hint": hint,
		})

	results.sort(key=lambda r: (not r["likely_eligible"], r["student_name"] or ""))
	return {"students": results}


@frappe.whitelist()
def create_and_queue(program, source_academic_year, target_academic_year, source_term=None,
                      target_term=None, batch=None, section=None, promotion_policy=None,
                      student_list=None):
	"""Create a Promotion Run in Queued state and enqueue the background job.
	If student_list is given (a list/JSON list of Student Enrollment names),
	the run is restricted to exactly those enrollments."""
	_check_permission()

	if not program or not source_academic_year or not target_academic_year:
		frappe.throw(frappe._("Programme, Source Academic Year and Target Academic Year are required."))

	if isinstance(student_list, str):
		import json
		student_list = json.loads(student_list) if student_list else None

	doc = frappe.new_doc("Promotion Run")
	doc.program = program
	doc.source_academic_year = source_academic_year
	doc.source_term = source_term
	doc.target_academic_year = target_academic_year
	doc.target_term = target_term
	doc.batch = batch
	doc.section = section
	doc.promotion_policy = promotion_policy
	doc.status = "Queued"
	doc.run_by = frappe.session.user
	doc.run_on = now_datetime()
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	if student_list:
		frappe.db.set_value("Promotion Run", doc.name, "selected_enrollments", frappe.as_json(student_list))

	frappe.enqueue(
		method="slcm.slcm.doctype.promotion_run.promotion_run.process_promotion_run",
		queue="short",
		timeout=1200,
		promotion_run_name=doc.name,
	)

	return doc.name


def process_promotion_run(promotion_run_name):
	doc = frappe.get_doc("Promotion Run", promotion_run_name)

	if doc.status == "Queued":
		doc.db_set("status", "In Progress")
		frappe.db.commit()

	try:
		enrollments = _matching_enrollments(doc.program, doc.source_academic_year, doc.batch, doc.section)

		if doc.selected_enrollments:
			import json
			selected = set(json.loads(doc.selected_enrollments))
			enrollments = [e for e in enrollments if e.name in selected]

		doc.db_set("total_students", len(enrollments))
		frappe.db.commit()

		policy_dict = {}
		if doc.promotion_policy:
			policy_dict = frappe.get_doc("Promotion Policy", doc.promotion_policy).as_dict()

		# from_year for the eligibility query: pulled from the source term_year on the Batch
		students_raw = []
		if enrollments and doc.batch:
			batch_row = frappe.db.get_value("Batch", doc.batch, ["term_year"], as_dict=True)
			from_year = cint(batch_row.term_year) if batch_row and batch_row.term_year else None
			if from_year is not None:
				students_raw = _get_students_raw(doc.program, doc.source_academic_year, from_year)
		student_eval_map = {s["student"]: s for s in students_raw}

		already_done = {row.student for row in doc.log}
		pending = [e for e in enrollments if e.student not in already_done]
		batch = pending[:BATCH_SIZE]

		for enrollment in batch:
			_process_one_student(doc, enrollment, policy_dict, student_eval_map)
			frappe.db.set_value(
				"Promotion Run", doc.name, "last_heartbeat", now_datetime(), update_modified=False
			)
			frappe.db.commit()

		doc.reload()
		processed = len(doc.log)

		if processed < len(enrollments):
			frappe.enqueue(
				method="slcm.slcm.doctype.promotion_run.promotion_run.process_promotion_run",
				queue="short",
				timeout=1200,
				promotion_run_name=doc.name,
			)
		else:
			_finalize(doc)

	except Exception:
		frappe.log_error(
			title=f"Promotion Run {promotion_run_name} failed",
			message=frappe.get_traceback(),
		)
		doc.db_set("status", "Error")
		doc.db_set("error_log", frappe.get_traceback())
		frappe.db.commit()
		frappe.publish_realtime(
			"promotion_run_complete",
			{"promotion_run": promotion_run_name, "status": "Error"},
			user=doc.run_by,
		)


def _process_one_student(doc, enrollment, policy_dict, student_eval_map):
	student = enrollment.student

	if policy_dict:
		row = student_eval_map.get(student)
		if not row:
			_append_log(doc, enrollment, "Skipped", "Other", "Student not found in eligibility dataset for this term.")
			return

		evaluation = _evaluate_student(row, policy_dict)
		status = evaluation.get("promotion_status", "Promoted")

		if status != "Promoted":
			reason_code, detail = _reason_for_skip(evaluation, student)
			_append_log(doc, enrollment, "Skipped", reason_code, detail)
			return

	if policy_dict.get("block_on_fee_due") and _has_fee_due(student):
		_append_log(doc, enrollment, "Skipped", "Fee Due", "Student has outstanding Fee Demand(s).")
		return

	next_batch = _resolve_target_batch(enrollment.batch, doc.target_academic_year, doc.target_term)
	if not next_batch:
		_append_log(
			doc, enrollment, "Skipped", "No Target Batch",
			f"No target Batch found for {doc.target_academic_year}. Create the Batch first.",
		)
		return

	existing = frappe.db.exists(
		"Student Enrollment", {"student": student, "batch": next_batch, "docstatus": ["<", 2]}
	)
	if existing:
		_append_log(doc, enrollment, "Skipped", "Already Promoted", "Enrollment already exists for the target term.", to_enrollment=existing)
		return

	try:
		old_doc = frappe.get_doc("Student Enrollment", enrollment.name)
		old_doc.status = "Completed"
		old_doc.save(ignore_permissions=True)

		new_doc = frappe.new_doc("Student Enrollment")
		new_doc.student = student
		new_doc.batch = next_batch
		new_doc.status = "Enrolled"
		new_doc.insert(ignore_permissions=True)

		_append_log(doc, enrollment, "Promoted", None, None, to_enrollment=new_doc.name)
	except Exception:
		frappe.log_error(
			title=f"Promotion Run {doc.name}: promote failed for {student}",
			message=frappe.get_traceback(),
		)
		_append_log(doc, enrollment, "Failed", "Other", frappe.get_traceback()[:1000])


def _append_log(doc, enrollment, result, reason_code, reason_detail, to_enrollment=None):
	frappe.get_doc(
		{
			"doctype": "Promotion Run Log",
			"parent": doc.name,
			"parenttype": "Promotion Run",
			"parentfield": "log",
			"student": enrollment.student,
			"student_name": enrollment.student_name,
			"from_enrollment": enrollment.name,
			"to_enrollment": to_enrollment,
			"result": result,
			"reason_code": reason_code,
			"reason_detail": reason_detail,
		}
	).db_insert()
	frappe.db.commit()


def _finalize(doc):
	doc.reload()
	promoted = len([r for r in doc.log if r.result == "Promoted"])
	skipped = len([r for r in doc.log if r.result in ("Skipped", "Failed")])
	final_status = "Completed" if skipped == 0 else "Completed with Errors"

	doc.db_set("promoted_count", promoted)
	doc.db_set("skipped_count", skipped)
	doc.db_set("status", final_status)
	frappe.db.commit()

	frappe.publish_realtime(
		"promotion_run_complete",
		{
			"promotion_run": doc.name,
			"status": final_status,
			"promoted": promoted,
			"skipped": skipped,
			"total": doc.total_students,
		},
		user=doc.run_by,
	)


@frappe.whitelist()
def promote_anyway(promotion_run_name, log_row_name, reason=None):
	"""Manual override: create the target enrollment for one skipped student,
	bypassing the policy check."""
	_check_permission()
	run = frappe.get_doc("Promotion Run", promotion_run_name)
	frappe.has_permission("Promotion Run", "write", doc=run, throw=True)

	row = next((r for r in run.log if r.name == log_row_name), None)
	if not row:
		frappe.throw(frappe._("Log entry not found."))
	if row.result == "Promoted":
		frappe.throw(frappe._("This student was already promoted."))

	enrollment = frappe.db.get_value(
		"Student Enrollment", row.from_enrollment, ["name", "student", "batch"], as_dict=True
	)
	if not enrollment:
		frappe.throw(frappe._("Original enrollment not found."))

	next_batch = _resolve_target_batch(enrollment.batch, run.target_academic_year, run.target_term)
	if not next_batch:
		frappe.throw(frappe._("No target Batch exists yet for this student's next term."))

	existing = frappe.db.exists(
		"Student Enrollment", {"student": enrollment.student, "batch": next_batch, "docstatus": ["<", 2]}
	)
	if existing:
		new_name = existing
	else:
		old_doc = frappe.get_doc("Student Enrollment", enrollment.name)
		old_doc.status = "Completed"
		old_doc.save(ignore_permissions=True)

		new_doc = frappe.new_doc("Student Enrollment")
		new_doc.student = enrollment.student
		new_doc.batch = next_batch
		new_doc.status = "Enrolled"
		new_doc.insert(ignore_permissions=True)
		new_name = new_doc.name

	row.to_enrollment = new_name
	row.result = "Promoted"
	row.resolved = 1
	row.resolution_action = "Manually Promoted"
	row.resolved_by = frappe.session.user
	row.resolved_on = now_datetime()
	row.reason_detail = (row.reason_detail or "") + f"\n[Manual override by {frappe.session.user}] {reason or ''}".strip()
	row.db_update()

	_recount(run.name)
	frappe.db.commit()
	return {"ok": True, "to_enrollment": new_name}


@frappe.whitelist()
def mark_as_exempt(promotion_run_name, log_row_name, reason=None):
	_check_permission()
	run = frappe.get_doc("Promotion Run", promotion_run_name)
	frappe.has_permission("Promotion Run", "write", doc=run, throw=True)

	row = next((r for r in run.log if r.name == log_row_name), None)
	if not row:
		frappe.throw(frappe._("Log entry not found."))

	row.resolved = 1
	row.resolution_action = "Marked Exempt"
	row.resolved_by = frappe.session.user
	row.resolved_on = now_datetime()
	row.reason_detail = (row.reason_detail or "") + f"\n[Marked exempt by {frappe.session.user}] {reason or ''}".strip()
	row.db_update()

	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist()
def bulk_resolve(promotion_run_name, log_row_names, action, reason=None):
	"""action: 'promote' or 'exempt'"""
	_check_permission()
	if isinstance(log_row_names, str):
		import json
		log_row_names = json.loads(log_row_names)

	results = {"succeeded": [], "failed": []}
	for row_name in log_row_names:
		try:
			if action == "promote":
				promote_anyway(promotion_run_name, row_name, reason)
			elif action == "exempt":
				mark_as_exempt(promotion_run_name, row_name, reason)
			else:
				frappe.throw(frappe._("Unknown action."))
			results["succeeded"].append(row_name)
		except Exception as e:
			results["failed"].append({"row": row_name, "error": str(e)})
	return results


@frappe.whitelist()
def retry_unresolved(promotion_run_name):
	"""Re-evaluate only the still-unresolved Skipped/Failed rows of a run,
	e.g. after underlying data (attendance, fee payment) has been corrected."""
	_check_permission()
	run = frappe.get_doc("Promotion Run", promotion_run_name)
	frappe.has_permission("Promotion Run", "write", doc=run, throw=True)

	unresolved = [r for r in run.log if r.result in ("Skipped", "Failed") and not r.resolved]
	if not unresolved:
		return {"retried": 0, "promoted": 0}

	policy_dict = {}
	if run.promotion_policy:
		policy_dict = frappe.get_doc("Promotion Policy", run.promotion_policy).as_dict()

	batch_row = frappe.db.get_value("Batch", run.batch, ["term_year"], as_dict=True) if run.batch else None
	from_year = cint(batch_row.term_year) if batch_row and batch_row.term_year else None
	students_raw = _get_students_raw(run.program, run.source_academic_year, from_year) if from_year is not None else []
	student_eval_map = {s["student"]: s for s in students_raw}

	promoted_now = 0
	for row in unresolved:
		enrollment = frappe.db.get_value(
			"Student Enrollment", row.from_enrollment, ["name", "student", "student_name", "batch"], as_dict=True
		)
		if not enrollment:
			continue

		eval_row = student_eval_map.get(enrollment.student)
		evaluation = _evaluate_student(eval_row, policy_dict) if (eval_row and policy_dict) else {"promotion_status": "Promoted"}
		status = evaluation.get("promotion_status", "Promoted")

		fee_blocked = policy_dict.get("block_on_fee_due") and _has_fee_due(enrollment.student)
		if status == "Promoted" and not fee_blocked:
			next_batch = _resolve_target_batch(enrollment.batch, run.target_academic_year, run.target_term)
			if next_batch and not frappe.db.exists(
				"Student Enrollment", {"student": enrollment.student, "batch": next_batch, "docstatus": ["<", 2]}
			):
				old_doc = frappe.get_doc("Student Enrollment", enrollment.name)
				old_doc.status = "Completed"
				old_doc.save(ignore_permissions=True)

				new_doc = frappe.new_doc("Student Enrollment")
				new_doc.student = enrollment.student
				new_doc.batch = next_batch
				new_doc.status = "Enrolled"
				new_doc.insert(ignore_permissions=True)

				row.to_enrollment = new_doc.name
				row.result = "Promoted"
				row.reason_code = None
				row.reason_detail = f"Promoted on retry by {frappe.session.user}."
				row.resolved = 1
				row.resolution_action = "Manually Promoted"
				row.resolved_by = frappe.session.user
				row.resolved_on = now_datetime()
				row.db_update()
				promoted_now += 1

	_recount(run.name)
	frappe.db.commit()
	return {"retried": len(unresolved), "promoted": promoted_now}


def _recount(promotion_run_name):
	log_rows = frappe.db.get_all(
		"Promotion Run Log", filters={"parent": promotion_run_name}, fields=["result"]
	)
	promoted = len([r for r in log_rows if r.result == "Promoted"])
	skipped = len([r for r in log_rows if r.result in ("Skipped", "Failed")])
	final_status = "Completed" if skipped == 0 else "Completed with Errors"
	frappe.db.set_value("Promotion Run", promotion_run_name, {
		"promoted_count": promoted,
		"skipped_count": skipped,
		"status": final_status,
	})


@frappe.whitelist()
def is_job_active(promotion_run_name):
	last_beat = frappe.db.get_value("Promotion Run", promotion_run_name, "last_heartbeat")
	if not last_beat:
		return False
	return (now_datetime() - last_beat).total_seconds() < 90
