import frappe


def execute():
	"""
	Applicant is not submittable (application workflow uses application_status, not Frappe submit).
	Rows with docstatus=1 incorrectly trigger UpdateAfterSubmit validation on save.
	"""
	if frappe.get_meta("Applicant").is_submittable:
		return
	frappe.db.sql("UPDATE `tabApplicant` SET `docstatus` = 0 WHERE `docstatus` = 1")
