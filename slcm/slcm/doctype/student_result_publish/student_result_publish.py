# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class StudentResultPublish(Document):
	def before_save(self):
		if self.is_published:
			if not self.published_on:
				self.published_by = frappe.session.user
				self.published_on = now()
			# Recalculate on every publish save
			sgpa, term_pct = _calculate_sgpa(self.student, self.exam_plan)
			self.term_gpa = sgpa
			self.term_percentage = term_pct
			cgpa, cpct = _calculate_cgpa(self.student, self.exam_plan)
			self.cumulative_gpa = cgpa
			self.cumulative_percentage = cpct
		elif not self.is_published and self.published_on and not self.unpublished_on:
			self.unpublished_by = frappe.session.user
			self.unpublished_on = now()

	def after_save(self):
		if self.is_published:
			_update_student_master_cgpa(self.student, self.cumulative_gpa, self.cumulative_percentage)


# ── GPA Calculation Helpers ───────────────────────────────────────────────────

def _calculate_sgpa(student, exam_plan):
	"""Calculate SGPA and term percentage for a student in one exam plan."""
	marks_records = frappe.get_all(
		"Student Course Marks",
		filters={
			"student": student,
			"exam_plan": exam_plan,
			"enrollment_status": ["not in", ["Dropped", "Detained", "Migrated"]],
		},
		fields=[
			"name", "course", "evaluation_schema",
			"total_marks", "updated_final_marks", "consider_for_sgpa",
		],
		ignore_permissions=True,
	)

	weighted_sum = 0.0
	total_credits = 0.0
	marks_sum = 0.0
	max_marks_sum = 0.0

	for m in marks_records:
		if not m.consider_for_sgpa:
			continue

		effective_marks = float(m.updated_final_marks or m.total_marks or 0)
		credit_value = float(frappe.db.get_value("Course", m.course, "credit_value") or 0)
		grade_point = _get_grade_point(exam_plan, m.course, effective_marks)
		max_marks = float(_get_max_marks(m.evaluation_schema))

		if credit_value > 0:
			weighted_sum += grade_point * credit_value
			total_credits += credit_value

		marks_sum += effective_marks
		max_marks_sum += max_marks

	sgpa = round(weighted_sum / total_credits, 2) if total_credits > 0 else 0.0
	term_pct = round((marks_sum / max_marks_sum) * 100, 2) if max_marks_sum > 0 else 0.0
	return sgpa, term_pct


def _calculate_cgpa(student, current_exam_plan=None):
	"""Calculate CGPA across all published exam plans plus the current one."""
	published = frappe.get_all(
		"Student Result Publish",
		filters={"student": student, "is_published": 1},
		pluck="exam_plan",
		ignore_permissions=True,
	)
	exam_plans = set(published)
	if current_exam_plan:
		exam_plans.add(current_exam_plan)

	if not exam_plans:
		return 0.0, 0.0

	marks_records = frappe.get_all(
		"Student Course Marks",
		filters={
			"student": student,
			"exam_plan": ["in", list(exam_plans)],
			"enrollment_status": ["not in", ["Dropped", "Detained", "Migrated"]],
		},
		fields=[
			"name", "exam_plan", "course", "evaluation_schema",
			"total_marks", "updated_final_marks", "consider_for_sgpa",
		],
		ignore_permissions=True,
	)

	weighted_sum = 0.0
	total_credits = 0.0
	marks_sum = 0.0
	max_marks_sum = 0.0

	for m in marks_records:
		if not m.consider_for_sgpa:
			continue

		effective_marks = float(m.updated_final_marks or m.total_marks or 0)
		credit_value = float(frappe.db.get_value("Course", m.course, "credit_value") or 0)
		grade_point = _get_grade_point(m.exam_plan, m.course, effective_marks)
		max_marks = float(_get_max_marks(m.evaluation_schema))

		if credit_value > 0:
			weighted_sum += grade_point * credit_value
			total_credits += credit_value

		marks_sum += effective_marks
		max_marks_sum += max_marks

	cgpa = round(weighted_sum / total_credits, 2) if total_credits > 0 else 0.0

	# If marks-based CGPA is 0 (no consider_for_sgpa courses), fall back to Student Master
	if cgpa == 0.0:
		try:
			sm_val = frappe.db.get_value("Student Master", student, "current_cgpa")
			if sm_val and float(sm_val) > 0:
				cgpa = round(float(sm_val), 2)
		except Exception:
			pass

	marks_cpct = round((marks_sum / max_marks_sum) * 100, 2) if max_marks_sum > 0 else 0.0

	# Use CGPA scale lookup if configured; fall back to marks-based percentage
	try:
		from slcm.slcm.doctype.cgpa_percentage_scale.cgpa_percentage_scale import (
			lookup_percentage_for_cgpa,
		)
		scale_pct = lookup_percentage_for_cgpa(cgpa) if cgpa else None
		cpct = scale_pct if scale_pct is not None else marks_cpct
	except Exception:
		cpct = marks_cpct

	return cgpa, cpct


def _get_grade_point(exam_plan, course, marks):
	"""Resolve grading schema via Course Schema Assignment and return grade_point."""
	schema_name = frappe.db.get_value(
		"Course Schema Assignment",
		{"exam_plan": exam_plan, "course": course},
		"grade_schema",
	)
	if not schema_name:
		return 0.0
	try:
		schema = frappe.get_doc("Grading Schema", schema_name)
		return schema.get_grade_point(float(marks))
	except Exception:
		return 0.0


def _get_max_marks(evaluation_schema):
	"""Return total_marks from EvaluationSchema or fallback 100."""
	if evaluation_schema:
		val = frappe.db.get_value("Evaluation Schema", evaluation_schema, "total_marks")
		if val:
			return float(val)
	return 100.0


def _update_student_master_cgpa(student, cgpa, cumulative_pct):
	"""Write CGPA / cumulative_percentage back to Student Master (silent update)."""
	if not student or not cgpa:
		return
	update = {"current_cgpa": cgpa}
	try:
		# only update cumulative_percentage if the field exists
		meta = frappe.get_meta("Student Master")
		if meta.get_field("cumulative_percentage"):
			update["cumulative_percentage"] = cumulative_pct or 0
	except Exception:
		pass
	frappe.db.set_value("Student Master", student, update, update_modified=False)


# ── Whitelisted APIs ──────────────────────────────────────────────────────────

@frappe.whitelist()
def bulk_publish_results(exam_plan):
	"""Create/update StudentResultPublish for every student who has marks in exam_plan."""
	if not frappe.has_permission("Student Result Publish", "create"):
		frappe.throw("Not permitted to publish results.")

	students = frappe.get_all(
		"Student Course Marks",
		filters={"exam_plan": exam_plan},
		pluck="student",
		distinct=True,
		ignore_permissions=True,
	)

	published = 0
	errors = []

	for student in students:
		try:
			existing = frappe.db.get_value(
				"Student Result Publish",
				{"student": student, "exam_plan": exam_plan},
				"name",
			)
			if existing:
				doc = frappe.get_doc("Student Result Publish", existing)
				doc.is_published = 1
				doc.save(ignore_permissions=True)
			else:
				doc = frappe.new_doc("Student Result Publish")
				doc.student = student
				doc.exam_plan = exam_plan
				doc.is_published = 1
				doc.insert(ignore_permissions=True)
			published += 1
		except Exception as e:
			frappe.log_error(f"bulk_publish_results: {student} — {e}", "Result Publish")
			errors.append(f"{student}: {e}")

	frappe.db.commit()
	return {"published": published, "total": len(students), "errors": errors}


@frappe.whitelist()
def unpublish_results(exam_plan):
	"""Set is_published=0 for all StudentResultPublish records in exam_plan."""
	if not frappe.has_permission("Student Result Publish", "write"):
		frappe.throw("Not permitted.")

	records = frappe.get_all(
		"Student Result Publish",
		filters={"exam_plan": exam_plan, "is_published": 1},
		fields=["name"],
		ignore_permissions=True,
	)

	count = 0
	for r in records:
		try:
			doc = frappe.get_doc("Student Result Publish", r.name)
			doc.is_published = 0
			doc.save(ignore_permissions=True)
			count += 1
		except Exception as e:
			frappe.log_error(f"unpublish_results: {r.name} — {e}", "Result Publish")

	frappe.db.commit()
	return {"unpublished": count}


@frappe.whitelist()
def recalculate_cgpa(student):
	"""Recalculate and update CGPA for a student from all their published results."""
	if not frappe.has_permission("Student Master", "write", doc=student):
		frappe.throw("Not permitted.")

	cgpa, cpct = _calculate_cgpa(student)
	_update_student_master_cgpa(student, cgpa, cpct)

	# Also refresh cumulative_gpa on all published records
	published = frappe.get_all(
		"Student Result Publish",
		filters={"student": student, "is_published": 1},
		fields=["name", "exam_plan"],
		ignore_permissions=True,
	)
	for rec in published:
		_, _ = _calculate_sgpa(student, rec.exam_plan)  # already saved during publish
	frappe.db.commit()

	return {"cgpa": cgpa, "cumulative_percentage": cpct}
