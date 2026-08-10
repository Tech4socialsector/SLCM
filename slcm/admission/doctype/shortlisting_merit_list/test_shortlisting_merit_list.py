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

		sql_queries = []
		def mock_sql(query, values=None, *args, **kwargs):
			sql_queries.append((query, values))
			return []

		orig_sql = frappe.db.sql
		orig_delete = frappe.db.delete

		try:
			frappe.db.sql = mock_sql
			frappe.db.delete = lambda dt, filters: None

			# Test Sync
			sp.sync_shortlisted_status_to_entrance_test_allocations()
			assert any("SET shortlisted_status = %(status)s" in q[0] and q[1].get("status") == "Shortlisted" for q in sql_queries)

			# Test Clear on Deletion
			sql_queries.clear()
			sp.clear_shortlisted_status_in_entrance_test_allocations()
			assert any("SET shortlisted_status = ''" in q[0] for q in sql_queries)

		finally:
			frappe.db.sql = orig_sql
			frappe.db.delete = orig_delete

	def test_part_b_zero_or_negative_rejection_in_final_merit_ranking(self):
		"""
		Test that candidates with Part B score <= 0 (0 or minus marks) during Final Allotment Ranking
		are Rejected and omitted from rank.
		"""
		from slcm.admission.doctype.merit_generation.merit_service import _rank_applicants

		cands = [
			frappe._dict({
				"applicant_id": "APP-01",
				"total_score": 90.0,
				"entrance_score": 50.0,
				"interview_score": 40.0,
				"status": "Selected",
				"overall_rank": 0
			}),
			frappe._dict({
				"applicant_id": "APP-02",
				"total_score": 60.0,
				"entrance_score": 60.0,
				"interview_score": 0.0,  # Zero Part B -> should be Rejected
				"status": "Selected",
				"overall_rank": 0
			}),
			frappe._dict({
				"applicant_id": "APP-03",
				"total_score": 50.0,
				"entrance_score": 30.0,
				"interview_score": 20.0,
				"status": "Selected",
				"overall_rank": 0
			}),
		]

		_rank_applicants(cands, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")

		# APP-01 (Part B = 40) should be Rank 1
		app1 = next(c for c in cands if c.applicant_id == "APP-01")
		assert app1.overall_rank == 1
		assert app1.status == "Selected"

		# APP-02 (Part B = 0) MUST be Rejected and unranked
		app2 = next(c for c in cands if c.applicant_id == "APP-02")
		assert app2.overall_rank == 0
		assert app2.status == "Rejected"

		# APP-03 (Part B = 20) should be Rank 2
		app3 = next(c for c in cands if c.applicant_id == "APP-03")
		assert app3.overall_rank == 2
		assert app3.status == "Selected"

	def test_part_b_not_appeared_rejection_in_final_merit_ranking(self):
		"""
		Test that candidates who did NOT appear for Part B (part_b_not_appeared=True)
		during Final Allotment Ranking are Rejected and omitted from rank.
		"""
		from slcm.admission.doctype.merit_generation.merit_service import _rank_applicants

		cands = [
			frappe._dict({
				"applicant_id": "APP-01",
				"total_score": 90.0,
				"entrance_score": 50.0,
				"interview_score": 40.0,
				"part_b_not_appeared": False,
				"status": "Selected",
				"overall_rank": 0
			}),
			frappe._dict({
				"applicant_id": "APP-02",
				"total_score": 60.0,
				"entrance_score": 60.0,
				"interview_score": 10.0,
				"part_b_not_appeared": False,
				"status": "Selected",
				"overall_rank": 0
			}),
			frappe._dict({
				"applicant_id": "APP-04",
				"total_score": 70.0,
				"entrance_score": 70.0,
				"interview_score": 0.0,  # Did NOT appear for Part B
				"part_b_not_appeared": True,
				"status": "Selected",
				"overall_rank": 0
			}),
		]

		_rank_applicants(cands, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")

		# APP-01 (Part B = 40, appeared) → Rank 1
		app1 = next(c for c in cands if c.applicant_id == "APP-01")
		assert app1.overall_rank == 1
		assert app1.status == "Selected"

		# APP-02 (Part B = 10, appeared) → Rank 2
		app2 = next(c for c in cands if c.applicant_id == "APP-02")
		assert app2.overall_rank == 2
		assert app2.status == "Selected"

		# APP-04 (did NOT appear for Part B) → Rejected, rank = 0
		app4 = next(c for c in cands if c.applicant_id == "APP-04")
		assert app4.overall_rank == 0
		assert app4.status == "Rejected"
		assert app4.remarks == "Rejected: did not appear for Part B"

	def test_part_a_rank_preservation_in_final_merit_ranking(self):
		"""
		Test that Part A ranks from Shortlist are preserved and not recalculated
		during Final Allotment Ranking.
		"""
		from slcm.admission.doctype.merit_generation.merit_service import _rank_applicants

		cands = [
			frappe._dict({
				"applicant_id": "APP-01",
				"total_score": 110.0,
				"entrance_score": 50.0,
				"interview_score": 60.0,
				"shortlist_rank": 15,  # Original Part A Rank from shortlist
				"part_a_rank": 15,
				"status": "Selected",
				"overall_rank": 0
			}),
			frappe._dict({
				"applicant_id": "APP-02",
				"total_score": 120.0,
				"entrance_score": 40.0,
				"interview_score": 80.0,
				"shortlist_rank": 45,  # Original Part A Rank from shortlist
				"part_a_rank": 45,
				"status": "Selected",
				"overall_rank": 0
			}),
		]

		_rank_applicants(cands, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")

		app1 = next(c for c in cands if c.applicant_id == "APP-01")
		app2 = next(c for c in cands if c.applicant_id == "APP-02")

		# Part A ranks must be preserved as 15 and 45 (NOT recalculated to 1 and 2)
		assert app1.part_a_rank == 15
		assert app2.part_a_rank == 45

		# Part B ranks are calculated independently (APP-02 = 80 -> Rank 1; APP-01 = 60 -> Rank 2)
		assert app2.part_b_rank == 1
		assert app1.part_b_rank == 2

		# Final Overall ranks are calculated (APP-02 = Total 120 -> Rank 1; APP-01 = Total 110 -> Rank 2)
		assert app2.overall_rank == 1
		assert app1.overall_rank == 2
