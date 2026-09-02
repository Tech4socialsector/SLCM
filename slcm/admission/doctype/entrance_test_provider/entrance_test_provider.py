# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EntranceTestProvider(Document):
	def validate(self):
		self.validate_duplicate_programmes()
		self.calculate_capacity()

	def validate_duplicate_programmes(self):
		if hasattr(self, "programme_capacity") and self.programme_capacity:
			seen = set()
			for row in self.programme_capacity:
				if row.program:
					if row.program in seen:
						frappe.throw(
							frappe._("Programme '{0}' has been selected more than once.").format(row.program)
						)
					seen.add(row.program)

	def calculate_capacity(self):
		"""
		Re-calculates global and per-programme capacities based on programme_capacity child table.
		"""
		if hasattr(self, "programme_capacity") and self.programme_capacity:
			for row in self.programme_capacity:
				cap = row.capacity or 0
				res = row.reserved_seats or 0
				row.available_capacity = max(0, cap - res)

			total_cap = sum((row.capacity or 0) for row in self.programme_capacity)
			total_res = sum((row.reserved_seats or 0) for row in self.programme_capacity)
			self.total_capacity = total_cap
			self.reserved_seats = total_res
			self.available_capacity = max(0, total_cap - total_res)
		else:
			self.available_capacity = max(0, (self.total_capacity or 0) - (self.reserved_seats or 0))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_active_cycle_programs(doctype, txt, searchfield, start, page_len, filters):
	"""
	Returns only programmes offered in active Admission Cycles.
	"""
	active_cycles = frappe.db.get_all("Admission Cycle", filters={"status": "Active"}, pluck="name")
	
	if not active_cycles:
		# Fallback to all admission cycles if no cycle is explicitly marked 'Active'
		active_cycles = frappe.db.get_all("Admission Cycle", pluck="name")

	if not active_cycles:
		return frappe.db.sql("""
			SELECT name, program_name
			FROM `tabProgramme`
			WHERE (name LIKE %(txt)s OR program_name LIKE %(txt)s)
			ORDER BY name ASC
			LIMIT %(page_len)s OFFSET %(start)s
		""", {"txt": f"%{txt}%", "page_len": int(page_len), "start": int(start)})

	escaped_cycles = ", ".join(frappe.db.escape(c) for c in active_cycles)
	return frappe.db.sql(f"""
		SELECT DISTINCT p.name, p.program_name
		FROM `tabProgramme` p
		INNER JOIN `tabAdmission Cycle Program` acp ON acp.program = p.name
		WHERE acp.parent IN ({escaped_cycles})
		  AND (p.name LIKE %(txt)s OR p.program_name LIKE %(txt)s)
		ORDER BY p.name ASC
		LIMIT %(page_len)s OFFSET %(start)s
	""", {
		"txt": f"%{txt}%",
		"page_len": int(page_len),
		"start": int(start)
	})


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
