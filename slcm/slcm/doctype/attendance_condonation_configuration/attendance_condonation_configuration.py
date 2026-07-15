# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AttendanceCondonationConfiguration(Document):
	pass

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_users_by_role(doctype, txt, searchfield, start, page_len, filters):
	role = filters.get("role")
	return frappe.db.sql("""
		select u.name, u.full_name
		from `tabUser` u
		inner join `tabHas Role` hr on hr.parent = u.name
		where hr.role = %(role)s
		  and u.enabled = 1
		  and u.name like %(txt)s
		order by u.name
		limit %(start)s, %(page_len)s
	""", {
		"role": role,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})
