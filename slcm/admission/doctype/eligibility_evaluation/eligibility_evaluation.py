# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EligibilityEvaluation(Document):
	pass


def _truthy(val):
	if val is None:
		return False
	if isinstance(val, bool):
		return val
	if isinstance(val, (int, float)):
		return val != 0
	return str(val).strip().lower() in ("1", "true", "yes")


# All three exemption status names (try exact match; alternate spellings for Applicant Status master)
_STATUS_BOTH = ["Excempted Entrance Test And Interview", "Exempted Entrance Test And Interview"]
_STATUS_ENTRANCE_ONLY = ["Entrance Test Exempted", "Entrance Test Excempted"]
# Interview-only: try "Interview Excempted" first (exact spelling in Applicant Status list)
_STATUS_INTERVIEW_ONLY = ["Interview Excempted", "Interview Exempted"]


def _resolve_applicant_status(candidates):
	"""Return the first candidate that exists in Applicant Status, or None."""
	for name in (candidates if isinstance(candidates, (list, tuple)) else [candidates]):
		if name and frappe.db.exists("Applicant Status", name):
			return name
	return None


def _status_from_exemption_flags(exempts_entrance_test, exempts_interview):
	"""Return Applicant Status name from exemption flags (Eligible evaluations only)."""
	et = _truthy(exempts_entrance_test)
	iv = _truthy(exempts_interview)
	if et and iv:
		return _resolve_applicant_status(_STATUS_BOTH)
	# Interview only (explicit: no entrance test exemption)
	if iv and not et:
		return _resolve_applicant_status(_STATUS_INTERVIEW_ONLY)
	if et:
		return _resolve_applicant_status(_STATUS_ENTRANCE_ONLY)
	return None


@frappe.whitelist()
def update_applicant_status_from_evaluations(campus, academic_year, admission_cycle, program_level):
	"""
	From Eligibility Evaluation list: update Applicant status ONLY for
	applicants whose Eligibility Evaluation has exemption checkboxes checked
	(Exempts Entrance Test and/or Exempts Interview). Applicants with no exemption
	are left unchanged.
	Filters: campus, academic_year, admission_cycle, program_level.
	Returns the number of applicants updated.
	"""
	if not all([campus, academic_year, admission_cycle, program_level]):
		frappe.throw("Campus, Academic Year, Admission Cycle, and Program Level are required.")

	
	prog_field = "level_of_study" if frappe.get_meta("Programme").has_field("level_of_study") else "program_level"
	programs = frappe.get_all(
		"Programme",
		filters={prog_field: program_level},
		pluck="name",
	)
	if not programs:
		frappe.throw(f"No programs found for Program Level: {program_level}.")

	# Fetch all Eligible evaluations for this context; filter by program_level in loop
	# so we don't miss any exempt record due to program filter edge cases
	filters = {
		"campus": campus,
		"academic_year": academic_year,
		"admission_cycle": admission_cycle,
		"evaluation_status": "Eligible",
	}

	rows = frappe.get_all(
		"Eligibility Evaluation",
		filters=filters,
		fields=["name", "applicant_name", "program", "exempts_entrance_test", "exempts_interview"],
	)

	updated = 0
	for row in rows:
		# Restrict to selected program level
		if row.get("program") not in programs:
			continue

		# Coerce checkbox values: treat any truthy or "1" as checked so no exempt row is missed
		raw_et = row.get("exempts_entrance_test")
		raw_iv = row.get("exempts_interview")
		et = _truthy(raw_et) or (raw_et not in (None, "", 0, "0", False))
		iv = _truthy(raw_iv) or (raw_iv not in (None, "", 0, "0", False))
		if not et and not iv:
			continue

		applicant_name = (row.get("applicant_name") or "").strip()
		if not applicant_name or not frappe.db.exists("Applicant", applicant_name):
			continue

		new_status = _status_from_exemption_flags(et, iv)
		# Fallback: if status not resolved, try exact names so we never skip an exempt row
		if not new_status:
			if iv and not et:
				new_status = _resolve_applicant_status(_STATUS_INTERVIEW_ONLY)
			elif et and not iv:
				new_status = _resolve_applicant_status(_STATUS_ENTRANCE_ONLY)
			elif et and iv:
				new_status = _resolve_applicant_status(_STATUS_BOTH)
		if not new_status:
			continue

		frappe.db.set_value(
			"Applicant", applicant_name, "status", new_status, update_modified=True
		)
		frappe.clear_document_cache("Applicant", applicant_name)
		updated += 1

	frappe.db.commit()
	return updated
