# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class RFIDDeviceRoomMapping(Document):
	def validate(self):
		self.validate_date_range()
		self.validate_overlap()

	def validate_date_range(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To date cannot be before Effective From date."))

	def validate_overlap(self):
		"""Prevent two active mappings of the same device to the same room
		with overlapping date ranges."""
		existing = frappe.db.sql("""
			SELECT name, effective_from, effective_to
			FROM `tabRFID Device Room Mapping`
			WHERE device = %(device)s
			AND room = %(room)s
			AND name != %(name)s
			AND is_active = 1
		""", {
			"device": self.device,
			"room": self.room,
			"name": self.name or "New RFID Device Room Mapping",
		}, as_dict=True)

		new_start = getdate(self.effective_from)
		new_end = getdate(self.effective_to) if self.effective_to else None

		for row in existing:
			existing_start = getdate(row.effective_from)
			existing_end = getdate(row.effective_to) if row.effective_to else None

			starts_before_existing_ends = existing_end is None or new_start <= existing_end
			ends_after_existing_starts = new_end is None or new_end >= existing_start

			if starts_before_existing_ends and ends_after_existing_starts:
				frappe.throw(_(
					"This Device-Room mapping overlaps with existing mapping {0} "
					"for the same device and room."
				).format(frappe.utils.get_link_to_form("RFID Device Room Mapping", row.name)))


def get_active_rooms_for_device(device_id, on_date=None):
	"""Return list of Room names currently (or as of on_date) mapped to the given device."""
	on_date = getdate(on_date) if on_date else getdate()

	rows = frappe.db.sql("""
		SELECT room
		FROM `tabRFID Device Room Mapping`
		WHERE device = %(device)s
		AND is_active = 1
		AND effective_from <= %(on_date)s
		AND (effective_to IS NULL OR effective_to >= %(on_date)s)
	""", {"device": device_id, "on_date": on_date}, as_dict=True)

	return [row.room for row in rows]
