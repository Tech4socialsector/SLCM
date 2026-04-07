import frappe


def execute():
	"""Cancelled Admission Cycles (docstatus=2) must show status Closed for desk and portal filters."""
	if not frappe.db.has_column("Admission Cycle", "status"):
		return
	frappe.db.sql(
		"""
		UPDATE `tabAdmission Cycle`
		SET `status` = 'Closed'
		WHERE `docstatus` = 2
		  AND IFNULL(`status`, '') != 'Closed'
		"""
	)
