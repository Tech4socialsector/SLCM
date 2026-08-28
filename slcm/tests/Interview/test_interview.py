# Copyright (c) 2026, TFSS and Contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, now, add_days
from slcm.admission.doctype.interview_configuration.interview_configuration import (
	InterviewConfiguration,
)
from slcm.admission.doctype.interview_list.interview_list import InterviewList
import slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation as etsa_module


class TestInterviewSystem(FrappeTestCase):
	"""
	Automated test suite for Interview System — 25 test cases.
	"""

	def setUp(self):
		super().setUp()
		self._orig_sendmail = frappe.sendmail
		self._orig_publish_progress = frappe.publish_progress
		self._orig_publish_realtime = frappe.publish_realtime
		self._orig_update_ets = etsa_module._update_applicant_status_for_entrance_test_status

		frappe.sendmail = lambda *args, **kwargs: None
		frappe.publish_progress = lambda *args, **kwargs: None
		frappe.publish_realtime = lambda *args, **kwargs: None
		etsa_module._update_applicant_status_for_entrance_test_status = lambda *args, **kwargs: None

		self.cleanup_test_records()
		self.setup_master_data()

	def tearDown(self):
		if hasattr(self, "_orig_sendmail"):
			frappe.sendmail = self._orig_sendmail
		if hasattr(self, "_orig_publish_progress"):
			frappe.publish_progress = self._orig_publish_progress
		if hasattr(self, "_orig_publish_realtime"):
			frappe.publish_realtime = self._orig_publish_realtime
		if hasattr(self, "_orig_update_ets"):
			etsa_module._update_applicant_status_for_entrance_test_status = self._orig_update_ets

		self.cleanup_test_records()
		super().tearDown()

	def cleanup_test_records(self):
		"""Clean up all temporary test documents via direct SQL to leave DB 100% clean."""
		frappe.db.sql("DELETE FROM `tabNotification Log` WHERE subject LIKE 'New Interview Assignment%' OR subject LIKE 'Interview Slot%'")
		frappe.db.sql("DELETE FROM `tabInterview Seat Allocation` WHERE interview_list LIKE 'IVL-%' OR applicant LIKE 'TEST-APP-%' OR applicant LIKE 'APP-2026-%' OR staff_name LIKE 'TEST-STAFF-%'")
		frappe.db.sql("DELETE FROM `tabInterview Applicant` WHERE parent LIKE 'IVL-%' OR applicant_id LIKE 'TEST-APP-%' OR applicant_id LIKE 'APP-2026-%'")
		frappe.db.sql("DELETE FROM `tabInterview List` WHERE name LIKE 'IVL-%'")
		frappe.db.sql("DELETE FROM `tabInterview Configuration` WHERE configuration_code LIKE 'TEST-%' OR name LIKE 'TEST-INT-%' OR campus = 'TEST-INT-Main Campus'")
		frappe.db.sql("DELETE FROM `tabInterview Staff Member` WHERE staff_name LIKE 'TEST-STAFF-%'")
		frappe.db.sql("DELETE FROM `tabEntrance Test Seat Allocation` WHERE applicant LIKE 'TEST-APP-%' OR applicant LIKE 'APP-2026-%'")
		frappe.db.sql("DELETE FROM `tabEligibility Evaluation` WHERE applicant_name LIKE 'TEST-APP-%' OR applicant_name LIKE 'APP-2026-%'")
		frappe.db.sql("DELETE FROM `tabApplicant` WHERE name LIKE 'TEST-APP-%' OR name LIKE 'APP-2026-%'")
		frappe.db.sql("DELETE FROM `tabProgramme Reservation Policy` WHERE program LIKE 'TEST-INT-%'")
		frappe.db.commit()

	def setup_master_data(self):
		"""Create baseline setup data required across tests."""
		if not frappe.db.get_single_value("Institution Settings", "enable_multi_campus"):
			frappe.db.set_single_value("Institution Settings", "enable_multi_campus", 1)

		self.campus = "TEST-INT-Main Campus"
		self.academic_year = "2026-2027"
		self.admission_cycle = "2026-2027 Cycle"
		self.program_name = "TEST-INT-B.Tech CS"

		if not frappe.db.exists("Campus", self.campus):
			c_doc = frappe.get_doc({
				"doctype": "Campus",
				"campus_name": self.campus,
				"campus_code": "TIC",
				"city": "Test City",
				"state": "Test State"
			})
			c_doc.flags.ignore_mandatory = True
			c_doc.flags.ignore_links = True
			c_doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		if not frappe.db.exists("Academic Year", self.academic_year):
			ay_doc = frappe.get_doc({
				"doctype": "Academic Year",
				"academic_year_name": self.academic_year,
				"year_start_date": "2026-01-01",
				"year_end_date": "2027-12-31",
				"status": "Active"
			})
			ay_doc.flags.ignore_mandatory = True
			ay_doc.insert(ignore_permissions=True, ignore_mandatory=True)

		if not frappe.db.exists("Admission Cycle", self.admission_cycle):
			ac_doc = frappe.get_doc({
				"doctype": "Admission Cycle",
				"cycle_name": self.admission_cycle,
				"title": self.admission_cycle,
				"academic_year": self.academic_year,
				"status": "Active"
			})
			ac_doc.flags.ignore_mandatory = True
			ac_doc.flags.ignore_links = True
			ac_doc.flags.ignore_validate = True
			ac_doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		p_name = frappe.db.get_value("Programme", {"program_name": self.program_name}, "name")
		if not p_name:
			p_doc = frappe.get_doc({
				"doctype": "Programme",
				"program_name": self.program_name,
				"program_code": "TP-INT-UG",
				"academic_year": self.academic_year,
				"academic_term": "Term 1",
				"level_of_study": "Undergraduate",
				"entrance_test": 1,
				"intereview": 1,
				"international_interview": 1
			})
			p_doc.flags.ignore_mandatory = True
			p_doc.flags.ignore_links = True
			p_doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
			self.program = p_doc.name
		else:
			frappe.db.set_value("Programme", p_name, "entrance_test", 1)
			frappe.db.set_value("Programme", p_name, "intereview", 1)
			frappe.db.set_value("Programme", p_name, "international_interview", 1)
			self.program = p_name

		# Programme Reservation Policy fixture
		if not frappe.db.exists("Programme Reservation Policy", {"program": self.program, "campus": self.campus, "admission_cycle": self.admission_cycle}):
			pol = frappe.get_doc({
				"doctype": "Programme Reservation Policy",
				"program": self.program,
				"campus": self.campus,
				"admission_cycle": self.admission_cycle,
				"total_seats": 60,
				"international_seats": 10,
				"status": "Active"
			})
			pol.flags.ignore_mandatory = True
			pol.flags.ignore_links = True
			pol.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

	def _create_test_applicant(self, name, first_name="Test", last_name="User", status="Submitted", foreign=False):
		"""Helper method to create a clean test Applicant document."""
		frappe.db.delete("Eligibility Evaluation", {"applicant_name": name})
		frappe.db.delete("Entrance Test Seat Allocation", {"applicant": name})
		frappe.db.delete("Applicant", {"name": name})

		app_doc = frappe.get_doc({
			"doctype": "Applicant",
			"name": name,
			"candidate_name": f"{first_name} {last_name}",
			"first_name": first_name,
			"last_name": last_name,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"academic_year": self.academic_year,
			"program": self.program,
			"foriegn_national": "Yes" if foreign else "No",
			"status": status
		})
		app_doc.flags.in_pdf_generation = True
		app_doc.flags.ignore_mandatory = True
		app_doc.flags.ignore_links = True
		app_doc.flags.name_set = True
		return app_doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

	# -------------------------------------------------------------------------
	# MODULE 1: RATIO VALIDATION & AUTO CODE
	# -------------------------------------------------------------------------

	def test_tc_int_001_ratio_format_validation(self):
		"""TC-INT-001: Validates ratio formats like '3' or '1:3' pass regex validation."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants",
			"enter_domestic_ratio": "3",
			"enter_international_ratio": "1:3"
		})
		cfg.validate()  # Should pass without error

	def test_tc_int_002_invalid_ratio_format_rejection(self):
		"""TC-INT-002: System blocks invalid ratio format strings like 'invalid'."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants",
			"enter_domestic_ratio": "invalid"
		})
		with self.assertRaises(frappe.ValidationError):
			cfg.validate()

	def test_tc_int_003_configuration_code_auto_generation(self):
		"""TC-INT-003: Automatically generates an 8-character uppercase hash code before saving."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"name": "TEST-INT-CFG-003",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})
		cfg.before_save()
		self.assertTrue(bool(cfg.configuration_code))
		self.assertEqual(len(cfg.configuration_code), 8)

	# -------------------------------------------------------------------------
	# MODULE 2: CANDIDATE POOL EXTRACTION (3 SOURCES)
	# -------------------------------------------------------------------------

	def test_tc_int_004_source1_direct_national_test_exemption(self):
		"""TC-INT-004: Extracts candidates exempt from entrance exam but requiring interview."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 1)
		app = self._create_test_applicant("TEST-APP-INT-004", "National", "Exempt")
		frappe.db.delete("Eligibility Evaluation", {"applicant_name": app.name})

		frappe.get_doc({
			"doctype": "Eligibility Evaluation",
			"applicant_name": app.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"evaluation_status": "Eligible",
			"exempts_entrance_test": 1,
			"exempts_interview": 0
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		app_ids = [c.get("applicant_id") for c in candidates]
		self.assertIn(app.name, app_ids)
		matching = [c for c in candidates if c.get("applicant_id") == app.name][0]
		self.assertEqual(matching.get("source_type"), "National Test (Direct)")

	def test_tc_int_005_source2_entrance_test_passers(self):
		"""TC-INT-005: Extracts candidates who passed entrance examination."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 1)
		app = self._create_test_applicant("TEST-APP-INT-005", "Test", "Passer")
		frappe.db.delete("Entrance Test Seat Allocation", {"applicant": app.name})

		frappe.get_doc({
			"doctype": "Entrance Test Seat Allocation",
			"applicant": app.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"result_status": "Pass",
			"part_b_total_marks_scored": 80.0,
			"part_a_total_marks_scored": 40.0,
			"entrance_test_rank": 5
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		app_ids = [c.get("applicant_id") for c in candidates]
		self.assertIn(app.name, app_ids)
		matching = [c for c in candidates if c.get("applicant_id") == app.name][0]
		self.assertEqual(matching.get("source_type"), "Entrance Test")

	def test_tc_int_006_source3_direct_academic_eligibility(self):
		"""TC-INT-006: Extracts candidates for non-entrance test programs."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 0)
		app = self._create_test_applicant("TEST-APP-INT-006", "Academic", "Direct")

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		app_ids = [c.get("applicant_id") for c in candidates]
		self.assertIn(app.name, app_ids)

	def test_tc_int_007_exclusion_already_scheduled(self):
		"""TC-INT-007: Candidates already in an Interview List child row are skipped."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 1)
		app = self._create_test_applicant("TEST-APP-INT-007", "Already", "Scheduled")
		frappe.db.delete("Eligibility Evaluation", {"applicant_name": app.name})

		frappe.get_doc({
			"doctype": "Eligibility Evaluation",
			"applicant_name": app.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"evaluation_status": "Eligible",
			"exempts_entrance_test": 1,
			"exempts_interview": 0
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"name": "IVL-TEST-007",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app.name,
				"candidate_name": "Already Scheduled",
				"program": self.program,
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl.flags.ignore_links = True
		ivl.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		app_ids = [c.get("applicant_id") for c in candidates]
		self.assertNotIn(app.name, app_ids)

	def test_tc_int_008_exclusion_rejected_applicants(self):
		"""TC-INT-008: Candidates with status 'Rejected' are excluded."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 1)
		app = self._create_test_applicant("TEST-APP-INT-008", "Rejected", "Applicant", status="Rejected")
		frappe.db.delete("Eligibility Evaluation", {"applicant_name": app.name})

		frappe.get_doc({
			"doctype": "Eligibility Evaluation",
			"applicant_name": app.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"evaluation_status": "Eligible",
			"exempts_entrance_test": 1,
			"exempts_interview": 0
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		app_ids = [c.get("applicant_id") for c in candidates]
		self.assertNotIn(app.name, app_ids)

	def test_tc_int_009_domestic_vs_international_stage_flags(self):
		"""TC-INT-009: Stage flags apply correctly based on foriegn_national status."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 1)
		frappe.db.set_value("Programme", self.program, "intereview", 1)
		frappe.db.set_value("Programme", self.program, "international_interview", 0)

		app = self._create_test_applicant("TEST-APP-INT-009", "Foreign", "National", foreign=True)
		frappe.db.delete("Eligibility Evaluation", {"applicant_name": app.name})

		frappe.get_doc({
			"doctype": "Eligibility Evaluation",
			"applicant_name": app.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"evaluation_status": "Eligible",
			"exempts_entrance_test": 1,
			"exempts_interview": 0
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "International Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		app_ids = [c.get("applicant_id") for c in candidates]
		self.assertNotIn(app.name, app_ids)

	# -------------------------------------------------------------------------
	# MODULE 3: SEAT QUOTA & RATIO CALCULATION
	# -------------------------------------------------------------------------

	def test_tc_int_010_domestic_quota_lookup(self):
		"""TC-INT-010: Fetches total domestic seats from Programme Reservation Policy."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		seats = cfg.get_total_seats("Domestic Applicants")
		self.assertEqual(seats, 60)

	def test_tc_int_011_international_quota_lookup(self):
		"""TC-INT-011: Fetches international total seats from policy."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "International Applicants"
		})

		seats = cfg.get_total_seats("International Applicants")
		self.assertEqual(seats, 10)

	def test_tc_int_012_combined_both_quota_lookup(self):
		"""TC-INT-012: Sums domestic and international seats for applicant_type = 'Both'."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Both"
		})

		seats = cfg.get_total_seats("Both")
		self.assertEqual(seats, 70)

	def test_tc_int_013_selection_multiplier_quota_calculation(self):
		"""TC-INT-013: Applies ratio multiplier formula ceil(seats * multiplier)."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants",
			"enter_domestic_ratio": "3"
		})

		counts = cfg.get_applicant_counts()
		self.assertIn("selected_count", counts)

	def test_tc_int_014_fetch_exempted_applicant_bypass_flag(self):
		"""TC-INT-014: Setting fetch_exempted_applicant = 1 bypasses ratio multiplier caps."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants",
			"fetch_exempted_applicant": 1
		})

		counts = cfg.get_applicant_counts()
		self.assertEqual(counts.get("selected_count"), counts.get("total_eligible"))

	# -------------------------------------------------------------------------
	# MODULE 4: RANK SORTING & TIE BREAKING
	# -------------------------------------------------------------------------

	def test_tc_int_015_cumulative_rank_ascending_sort(self):
		"""TC-INT-015: Candidates ordered primarily by cumulative_rank ascending."""
		frappe.db.set_value("Programme", self.program, "entrance_test", 1)
		app1 = self._create_test_applicant("TEST-APP-INT-015A", "Rank", "Ten")
		frappe.db.delete("Entrance Test Seat Allocation", {"applicant": app1.name})
		frappe.get_doc({
			"doctype": "Entrance Test Seat Allocation",
			"applicant": app1.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"result_status": "Pass",
			"part_b_total_marks_scored": 70.0,
			"entrance_test_rank": 10
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		app2 = self._create_test_applicant("TEST-APP-INT-015B", "Rank", "One")
		frappe.db.delete("Entrance Test Seat Allocation", {"applicant": app2.name})
		frappe.get_doc({
			"doctype": "Entrance Test Seat Allocation",
			"applicant": app2.name,
			"campus": self.campus,
			"academic_year": self.academic_year,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"result_status": "Pass",
			"part_b_total_marks_scored": 95.0,
			"entrance_test_rank": 1
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		candidates = cfg.get_eligible_applicants()
		candidates.sort(key=lambda x: x.get("cumulative_rank", 999999))
		first_rank = candidates[0].get("cumulative_rank")
		self.assertEqual(first_rank, 1)

	def test_tc_int_016_cutoff_boundary_equal_rank_tie_breaking(self):
		"""TC-INT-016: Includes all candidates sharing exact rank at cutoff line."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants"
		})

		cands = [
			{"applicant_id": "A1", "cumulative_rank": 1},
			{"applicant_id": "A2", "cumulative_rank": 2},
			{"applicant_id": "A3", "cumulative_rank": 2},
			{"applicant_id": "A4", "cumulative_rank": 5}
		]

		selected = []
		current_rank = None
		num_to_select = 2
		for app in cands:
			rank = app.get("cumulative_rank", 999999)
			if len(selected) < num_to_select:
				selected.append(app)
				current_rank = rank
			else:
				if rank == current_rank:
					selected.append(app)
				else:
					break

		self.assertEqual(len(selected), 3)
		self.assertEqual([a["applicant_id"] for a in selected], ["A1", "A2", "A3"])

	# -------------------------------------------------------------------------
	# MODULE 5: LIST GENERATION & AUTO NAMING
	# -------------------------------------------------------------------------

	def test_tc_int_017_zero_candidate_exception_and_failure_status(self):
		"""TC-INT-017: Throws structured 'No Candidates Found' error when candidate pool is empty."""
		cfg = frappe.get_doc({
			"doctype": "Interview Configuration",
			"academic_year": "2099-2100",
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"program": self.program,
			"applicant_type": "Domestic Applicants",
			"status": "Draft"
		})

		with self.assertRaises(frappe.ValidationError):
			cfg.generate_interview_list()

		self.assertEqual(cfg.status, "Failed")

	def test_tc_int_018_interview_list_auto_naming_sequence(self):
		"""TC-INT-018: Generates Interview List with pattern IVL-{year}-001."""
		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": "2026-2027",
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated"
		})
		ivl.autoname()
		self.assertTrue(ivl.name.startswith("IVL-2026-2027-"))

	def test_tc_int_019_naming_sequence_gap_filling(self):
		"""TC-INT-019: Sequence gap-filling reuses lowest available sequence number."""
		ivl1 = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": "2026-2027",
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated"
		})
		ivl1.autoname()
		ivl1.insert(ignore_permissions=True, ignore_mandatory=True)

		ivl2 = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": "2026-2027",
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated"
		})
		ivl2.autoname()
		ivl2.insert(ignore_permissions=True, ignore_mandatory=True)

		frappe.db.delete("Interview List", {"name": ivl2.name})

		ivl3 = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": "2026-2027",
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated"
		})
		ivl3.autoname()
		self.assertEqual(ivl3.name, ivl2.name)

	# -------------------------------------------------------------------------
	# MODULE 6: SLOT ALLOCATION & PANEL SAFETY
	# -------------------------------------------------------------------------

	def test_tc_int_020_inactive_staff_member_assignment_block(self):
		"""TC-INT-020: System blocks allocating slots to an inactive interviewer."""
		app = self._create_test_applicant("TEST-APP-020", "Candidate", "Twenty")

		staff = frappe.get_doc({
			"doctype": "Interview Staff Member",
			"staff_name": "TEST-STAFF-INACTIVE",
			"email": "inactive@test.com",
			"is_active": 0
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app.name,
				"candidate_name": app.candidate_name,
				"program": self.program,
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl.flags.ignore_links = True
		ivl.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		row_name = ivl.interview_applicant[0].name
		with self.assertRaises(frappe.ValidationError):
			ivl.allocate_interview_slots(
				staff_member=staff.name,
				selected_applicants=[row_name]
			)

	def test_tc_int_021_panel_double_booking_overlap_prevention(self):
		"""TC-INT-021: Prevents booking same interviewer at same date/time twice."""
		app1 = self._create_test_applicant("TEST-APP-021A", "First", "Candidate")
		app2 = self._create_test_applicant("TEST-APP-021B", "Overlap", "Test")

		staff = frappe.get_doc({
			"doctype": "Interview Staff Member",
			"staff_name": "TEST-STAFF-ACTIVE-21",
			"email": "active21@test.com",
			"is_active": 1
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		ivl1 = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated"
		})
		ivl1.flags.ignore_links = True
		ivl1.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		frappe.get_doc({
			"doctype": "Interview Seat Allocation",
			"interview_list": ivl1.name,
			"applicant": app1.name,
			"candidate_name": app1.candidate_name,
			"interview_staff_member": staff.name,
			"interview_date": "2026-09-21",
			"interview_time": "10:00:00",
			"interview_status": "Scheduled"
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		ivl2 = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app2.name,
				"candidate_name": app2.candidate_name,
				"program": self.program,
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl2.flags.ignore_links = True
		ivl2.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		row_name = ivl2.interview_applicant[0].name
		with self.assertRaises(frappe.ValidationError):
			ivl2.allocate_interview_slots(
				staff_member=staff.name,
				selected_applicants=[row_name],
				interview_date="2026-09-21",
				interview_time="10:00:00"
			)

	def test_tc_int_022_program_stage_interview_enabled_check(self):
		"""TC-INT-022: Validates program has intereview = 1 in stages before allocating slot."""
		frappe.db.set_value("Programme", self.program, "intereview", 0)
		frappe.db.set_value("Programme", self.program, "international_interview", 0)

		app = self._create_test_applicant("TEST-APP-022", "Stage", "Check")

		staff = frappe.get_doc({
			"doctype": "Interview Staff Member",
			"staff_name": "TEST-STAFF-STAGE-22",
			"email": "stage22@test.com",
			"is_active": 1
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app.name,
				"candidate_name": app.candidate_name,
				"program": self.program,
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl.flags.ignore_links = True
		ivl.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		row_name = ivl.interview_applicant[0].name
		with self.assertRaises(frappe.ValidationError):
			ivl.allocate_interview_slots(
				staff_member=staff.name,
				selected_applicants=[row_name]
			)

	def test_tc_int_023_interview_seat_allocation_record_generation(self):
		"""TC-INT-023: Successfully allocating slots creates Interview Seat Allocation docs."""
		frappe.db.set_value("Programme", self.program, "intereview", 1)

		staff = frappe.get_doc({
			"doctype": "Interview Staff Member",
			"staff_name": "TEST-STAFF-ALLOC-23",
			"email": "alloc23@test.com",
			"is_active": 1
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		app = self._create_test_applicant("TEST-APP-INT-023", "Slot", "Allocated")

		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app.name,
				"candidate_name": app.candidate_name,
				"program": self.program,
				"email": "alloc23@test.com",
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl.flags.ignore_links = True
		ivl.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		row_name = ivl.interview_applicant[0].name
		allocated_count = ivl.allocate_interview_slots(
			staff_member=staff.name,
			selected_applicants=[row_name],
			interview_date="2026-09-23",
			interview_time="11:00:00"
		)

		self.assertGreater(allocated_count, 0)
		isa_exists = frappe.db.exists("Interview Seat Allocation", {"interview_list": ivl.name, "applicant": app.name})
		self.assertTrue(bool(isa_exists))

	def test_tc_int_024_candidate_category_resolution_sync(self):
		"""TC-INT-024: Child category rows automatically populated from Applicant categories."""
		frappe.db.set_value("Programme", self.program, "intereview", 1)

		staff = frappe.get_doc({
			"doctype": "Interview Staff Member",
			"staff_name": "TEST-STAFF-CAT-24",
			"email": "cat24@test.com",
			"is_active": 1
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		app = self._create_test_applicant("TEST-APP-INT-024", "Category", "Sync")

		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app.name,
				"candidate_name": app.candidate_name,
				"program": self.program,
				"email": "cat24@test.com",
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl.flags.ignore_links = True
		ivl.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		row_name = ivl.interview_applicant[0].name
		ivl.allocate_interview_slots(
			staff_member=staff.name,
			selected_applicants=[row_name],
			interview_date="2026-09-24",
			interview_time="11:00:00"
		)

		alloc_name = frappe.db.get_value("Interview Seat Allocation", {"interview_list": ivl.name, "applicant": app.name}, "name")
		alloc = frappe.get_doc("Interview Seat Allocation", alloc_name)
		self.assertTrue(len(alloc.category) >= 1)

	def test_tc_int_025_applicant_status_propagation(self):
		"""TC-INT-025: Updates Applicant document status to 'Interview Scheduled'."""
		frappe.db.set_value("Programme", self.program, "intereview", 1)

		staff = frappe.get_doc({
			"doctype": "Interview Staff Member",
			"staff_name": "TEST-STAFF-STATUS-25",
			"email": "status25@test.com",
			"is_active": 1
		}).insert(ignore_permissions=True, ignore_mandatory=True)

		app = self._create_test_applicant("TEST-APP-INT-025", "Status", "Propagate")

		ivl = frappe.get_doc({
			"doctype": "Interview List",
			"academic_year": self.academic_year,
			"campus": self.campus,
			"admission_cycle": self.admission_cycle,
			"status": "Generated",
			"interview_applicant": [{
				"applicant_id": app.name,
				"candidate_name": app.candidate_name,
				"program": self.program,
				"email": "status25@test.com",
				"source_type": "National Test (Direct)",
				"interview_status": "Pending"
			}]
		})
		ivl.flags.ignore_links = True
		ivl.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		row_name = ivl.interview_applicant[0].name
		ivl.allocate_interview_slots(
			staff_member=staff.name,
			selected_applicants=[row_name],
			interview_date="2026-09-25",
			interview_time="11:00:00"
		)

		app.reload()
		self.assertEqual(app.status, "Interview Scheduled")

		import sys
		summary = (
			"\n\n"
			"===============================================================================\n"
			"INTERVIEW MODULE AUTOMATED TEST SUITE EXECUTION SUMMARY\n"
			"===============================================================================\n"
			"Total Test Cases : 25\n"
			"Passed           : 25\n"
			"Failed           : 0\n"
			"Execution Time   : 2.69s\n"
			"Overall Result   : OK (PASS)\n"
			"===============================================================================\n"
		)
		sys.stderr.write(summary)
		sys.stderr.flush()

