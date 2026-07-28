# Copyright (c) 2025, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import random_string


class Faculty(Document):
	def validate(self):
		if self.auto_create_user:
			self.create_user_if_needed()

	def create_user_if_needed(self):
		"""
		Auto-create (once) a Frappe User for this Faculty's Official Email ID,
		when "Auto Create User" is checked. Restricted to System Manager since
		it provisions portal login access. The new User gets Website User type
		(not System User) and the slcm_Faculty role, so Google OAuth sign-in on
		the Faculty Portal works immediately without a separate manual step.
		"""
		if "System Manager" not in frappe.get_roles(frappe.session.user):
			frappe.throw("Only a System Manager can enable Auto Create User.")

		if not self.official_email_id:
			frappe.throw("Please set the Official Email ID before enabling Auto Create User.")

		if self.user_id:
			# Already linked to a User — nothing to create.
			return

		existing_user = frappe.db.exists("User", self.official_email_id)
		if existing_user:
			self.user_id = existing_user
			self._ensure_faculty_role(existing_user)
			return

		user = frappe.get_doc({
			"doctype": "User",
			"email": self.official_email_id,
			"first_name": self.first_name or self.official_email_id.split("@")[0],
			"last_name": self.last_name,
			"mobile_no": self.phone,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"enabled": 1,
		})
		user.flags.ignore_password_policy = True
		user.flags.no_welcome_mail = True
		user.new_password = random_string(16)
		user.insert(ignore_permissions=True)

		self._ensure_faculty_role(user.name)
		self.user_id = user.name

	def _ensure_faculty_role(self, user_name):
		if not frappe.db.exists("Has Role", {"parent": user_name, "role": "slcm_Faculty"}):
			user_doc = frappe.get_doc("User", user_name)
			user_doc.append("roles", {"role": "slcm_Faculty"})
			user_doc.save(ignore_permissions=True)
