# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InterviewStaffMember(Document):
    pass


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user_query(doctype, txt, searchfield, start, page_len, filters):
	role = "Interview Staff Member"
	
	# Users who have the Role Profile named 'Interview Staff Member'
	users_with_profile = frappe.db.get_all("User", filters={"role_profile_name": role}, pluck="name")
	
	# Users who have the Role 'Interview Staff Member' directly
	users_with_role = frappe.db.get_all("Has Role", filters={"role": role}, pluck="parent")
	
	# Combine and deduplicate
	user_ids = list(set(users_with_profile + users_with_role))
	
	if not user_ids:
		return []

	query_filters = {"name": ["in", user_ids]}
	or_filters = None
	if txt:
		or_filters = {
			"name": ["like", f"%{txt}%"],
			"full_name": ["like", f"%{txt}%"]
		}

	return frappe.get_all(
		"User",
		filters=query_filters,
		or_filters=or_filters,
		fields=["name", "full_name"],
		as_list=True,
		start=start,
		page_length=page_len
	)
