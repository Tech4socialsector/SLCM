# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	columns = [
		_("Admission Cycle") + ":Link/Admission Cycle:150",
		_("Campus") + ":Link/Campus:150",
		_("Program") + ":Link/Program:200",
		_("Scholarship Scheme") + ":Link/Scholarship Scheme:200",
		_("Total Beneficiaries") + ":Int:150",
		_("Total Scholarship Utilized") + ":Currency:200"
	]

	conditions = ""
	values = {}
	
	if filters:
		if filters.get("admission_cycle"):
			conditions += " AND admission_cycle = %(admission_cycle)s"
			values["admission_cycle"] = filters.get("admission_cycle")
		if filters.get("campus"):
			conditions += " AND campus = %(campus)s"
			values["campus"] = filters.get("campus")
		if filters.get("program"):
			conditions += " AND program = %(program)s"
			values["program"] = filters.get("program")
		if filters.get("scholarship_scheme"):
			conditions += " AND scholarship_scheme = %(scholarship_scheme)s"
			values["scholarship_scheme"] = filters.get("scholarship_scheme")

	data = frappe.db.sql(f"""
		SELECT
			admission_cycle,
			campus,
			program,
			scholarship_scheme,
			COUNT(name) AS total_beneficiaries,
			SUM(calculated_benefit) AS total_utilized
		FROM `tabScholarship Application`
		WHERE status = 'Approved'
		{conditions}
		GROUP BY admission_cycle, campus, program, scholarship_scheme
		ORDER BY admission_cycle DESC, scholarship_scheme
	""", values, as_dict=True)

	return columns, data
