# Copyright (c) 2026, Nishanth and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestRFIDDeviceRoomMapping(IntegrationTestCase):
	def test_overlap_validation_blocks_same_device_room(self):
		device = frappe.get_doc({
			"doctype": "RFID Device",
			"device_id": "TEST-DEVICE-001",
			"device_name": "Test Device",
		}).insert(ignore_permissions=True)

		room = frappe.get_doc({
			"doctype": "Room",
			"room_name": "TEST-ROOM-001",
		}).insert(ignore_permissions=True)

		frappe.get_doc({
			"doctype": "RFID Device Room Mapping",
			"device": device.name,
			"room": room.name,
			"effective_from": "2026-01-01",
		}).insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": "RFID Device Room Mapping",
				"device": device.name,
				"room": room.name,
				"effective_from": "2026-02-01",
			}).insert(ignore_permissions=True)
