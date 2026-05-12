# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_components():
	return frappe.get_all(
		"Exam Component",
		filters={"is_active": 1},
		fields=["name", "component_name", "component_type"],
		order_by="component_name asc",
	)


@frappe.whitelist()
def get_assessment_types():
	return frappe.get_all(
		"Exam Assessment Type",
		filters={"is_active": 1},
		fields=["name", "type_name", "assessment_type"],
		order_by="type_name asc",
	)
