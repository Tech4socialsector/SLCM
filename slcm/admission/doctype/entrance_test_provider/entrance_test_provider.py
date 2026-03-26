# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

# import frappe
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
