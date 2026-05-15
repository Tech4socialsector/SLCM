# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EntranceTestProvider(Document):
	def validate(self):
		self.calculate_capacity()

	def calculate_capacity(self):
		"""
		Re-calculates all room and global capacities to ensure data integrity.
		"""
		total_cap = 0
		total_reserved = 0
		total_available = 0

		for room in self.provider_room:
			# Calculate room available capacity
			room.room_available_capacity = (room.room_capacity or 0) - (room.room_reserved_seats or 0)
			
			# Accumulate totals
			total_cap += (room.room_capacity or 0)
			total_reserved += (room.room_reserved_seats or 0)
			total_available += (room.room_available_capacity or 0)

		# Set main fields
		self.total_capacity = total_cap
		self.reserved_seats = total_reserved
		self.available_capacity = total_available


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user_query(doctype, txt, searchfield, start, page_len, filters):
	role = "Entrance Test Provider"
	
	# Users who have the Role Profile named 'Entrance Test Provider'
	users_with_profile = frappe.db.get_all("User", filters={"role_profile_name": role}, pluck="name")
	
	# Users who have the Role 'Entrance Test Provider' directly
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
