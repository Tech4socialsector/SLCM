# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestShortlistingMeritList(IntegrationTestCase):
	"""
	Integration tests for ShortlistingMeritList.
	"""

	def test_sync_and_clear_shortlisted_status(self):
		# Create test ShortlistingMeritList document instance with mock values
		sp = frappe.new_doc("Shortlisting Merit List")
		sp.admission_cycle = "2026"
		sp.campus = "Main"
		sp.program_level = "Undergraduate"
		sp.program = "BA LLB"
		sp.append("shortlist_applicants", {
			"applicant_id": "APP-TEST-SHORTLIST-01",
			"shortlist_status": "Shortlisted"
		})

		# Mock get_all to simulate Entrance Test Seat Allocation records
		all_allocs = [
			frappe._dict({"name": "ALLOC-01", "applicant": "APP-TEST-SHORTLIST-01", "shortlisted_status": ""}),
			frappe._dict({"name": "ALLOC-02", "applicant": "APP-TEST-SHORTLIST-02", "shortlisted_status": "Shortlisted"})
		]

		saved_values = {}
		def mock_set_value(dt, name, field, val, update_modified=False):
			saved_values[name] = val

		orig_get_all = frappe.get_all
		orig_set_value = frappe.db.set_value

		try:
			frappe.db.set_value = mock_set_value
			frappe.get_all = lambda dt, **kwargs: all_allocs if dt == "Entrance Test Seat Allocation" else []

			# Test Sync
			sp.sync_shortlisted_status_to_entrance_test_allocations()
			assert saved_values.get("ALLOC-01") == "Shortlisted"
			assert saved_values.get("ALLOC-02") == ""  # Not in shortlist_applicants -> reset to blank

			# Test Clear on Deletion
			saved_values.clear()
			sp.clear_shortlisted_status_in_entrance_test_allocations()
			assert saved_values.get("ALLOC-01") == ""
			assert saved_values.get("ALLOC-02") == ""

		finally:
			frappe.get_all = orig_get_all
			frappe.db.set_value = orig_set_value
