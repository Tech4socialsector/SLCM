# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	if filters is None:
		filters = {}

	columns = get_columns()
	data = get_data(filters)

	total_pass = sum(d.get("pass_count", 0) for d in data)

	summary = [
		{
			"label": _("Total Passed Applicants"),
			"value": total_pass,
			"indicator": "Green",
			"datatype": "Int",
		}
	]

	message = (
		_("Passed applicant counts by centre.")
		if data
		else _("No passed applicants found.")
	)

	return columns, data, message, None, summary


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Entrance Test Provider"),
			"fieldname": "entrance_test_provider",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Centre Name"),
			"fieldname": "center_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Entrance Test Name"),
			"fieldname": "entrance_test_name",
			"fieldtype": "Link",
			"options": "Entrance Test",
			"width": 160,
		},
		{
			"label": _("Programme"),
			"fieldname": "program",
			"fieldtype": "Link",
			"options": "Programme",
			"width": 160,
		},
		{
			"label": _("Academic Year"),
			"fieldname": "academic_year",
			"fieldtype": "Link",
			"options": "Academic Year",
			"width": 130,
		},
		{
			"label": _("Admission Cycle"),
			"fieldname": "admission_cycle",
			"fieldtype": "Link",
			"options": "Admission Cycle",
			"width": 130,
		},
		{
			"label": _("Pass Count"),
			"fieldname": "pass_count",
			"fieldtype": "Int",
			"width": 140,
		},
	]


def get_data(filters: dict) -> list[dict]:
	user = frappe.session.user
	roles = frappe.get_roles(user)

	provider_filter = None
	if (
		"Entrance Test Provider" in roles
		and "System Manager" not in roles
		and "Entrance Test Admin" not in roles
		and user != "Administrator"
	):
		provider_name = frappe.db.get_value("Entrance Test Provider", {"user": user}, "name")
		if not provider_name:
			return []
		provider_filter = provider_name
	elif filters.get("entrance_test_provider"):
		provider_filter = filters.get("entrance_test_provider")

	conditions = ["result_status = 'Pass'", "docstatus < 2"]
	values = {}

	if filters.get("is_international_applicant") or filters.get("show_international_applicant"):
		conditions.append(
			"(is_international_applicant = 1 OR entrance_test_provider = 'International Applicant' OR entrance_test_provider IS NULL OR entrance_test_provider = '')"
		)
	elif provider_filter:
		conditions.append(
			"(entrance_test_provider = %(provider)s OR re_entrance_test_provider = %(provider)s)"
		)
		values["provider"] = provider_filter

	if filters.get("academic_year"):
		conditions.append("academic_year = %(academic_year)s")
		values["academic_year"] = filters.get("academic_year")

	if filters.get("admission_cycle"):
		conditions.append("admission_cycle = %(admission_cycle)s")
		values["admission_cycle"] = filters.get("admission_cycle")

	if filters.get("campus"):
		conditions.append("campus = %(campus)s")
		values["campus"] = filters.get("campus")

	if filters.get("program_level"):
		conditions.append("program_level = %(program_level)s")
		values["program_level"] = filters.get("program_level")

	if filters.get("program"):
		conditions.append("program = %(program)s")
		values["program"] = filters.get("program")

	if filters.get("entrance_test_list"):
		conditions.append("entrance_test_list = %(entrance_test_list)s")
		values["entrance_test_list"] = filters.get("entrance_test_list")

	if filters.get("allocation_date"):
		conditions.append("allocation_date = %(allocation_date)s")
		values["allocation_date"] = filters.get("allocation_date")

	where_clause = " AND ".join(conditions)

	records = frappe.db.sql(
		f"""
		SELECT
			IFNULL(
				NULLIF(
					IF(is_rescheduled = 1 AND re_entrance_test_provider IS NOT NULL AND re_entrance_test_provider != '', re_entrance_test_provider, entrance_test_provider),
					''
				),
				'International Applicant'
			) as entrance_test_provider,
			IFNULL(
				NULLIF(
					IF(is_rescheduled = 1 AND re_center_name IS NOT NULL AND re_center_name != '', re_center_name, center_name),
					''
				),
				'International Applicant'
			) as center_name,
			IF(is_rescheduled = 1 AND re_entrance_test_name IS NOT NULL AND re_entrance_test_name != '', re_entrance_test_name, entrance_test_name) as entrance_test_name,
			program,
			academic_year,
			admission_cycle,
			COUNT(name) as pass_count
		FROM `tabEntrance Test Seat Allocation`
		WHERE {where_clause}
		GROUP BY 1, 2, 3, 4, 5, 6
		ORDER BY pass_count DESC
		""",
		values,
		as_dict=True,
	)

	return records
