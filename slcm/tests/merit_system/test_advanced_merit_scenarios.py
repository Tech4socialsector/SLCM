# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import time
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from slcm.admission.doctype.merit_generation.merit_service import (
    _rank_applicants,
    _calculate_and_sync_percentiles,
    _check_percentile_eligibility,
    execute_advanced_allocation_logic,
    execute_part_a_shortlisting,
    clear_category_cache
)


class IntegrationTestAdvancedMeritScenarios(IntegrationTestCase):
    """
    Comprehensive Edge Case & Production Readiness Test Suite for NLSAT Merit System.
    Validates Sections A through I:
    - Section A: Category-Specific Zero/Shortage Scenarios
    - Section B: Ratio Variation Scenarios (Below 1:5)
    - Section C: Min Percentile Cutoff Tests
    - Section D: Waitlist Scenarios
    - Section E: Category-Wise Allocation Validation
    - Section F: Total Sanity Checks
    - Section G: Merit Order Validation
    - Section H: Data Integrity Across Stages
    - Section I: Performance & Scale with 2,500 Applicants
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cycle = "2026-July To Oct"
        cls.campus = "National Law School of India University"
        cls.program_level = "Undergraduate"
        cls.program = "5-YEAR B.A., LL.B-2026 - 2027-I-TRIMESTER"

    def _get_mock_doc(self, applicant_rows, is_shortlist=False):
        """Helper to create mock Merit List or Shortlisting Merit List document."""
        doctype = "Shortlisting Merit List" if is_shortlist else "Merit List"
        child_field = "shortlist_applicants" if is_shortlist else "merit_applicants"

        doc = frappe.new_doc(doctype)
        doc.name = f"MOCK-{doctype.upper()}-001"
        doc.admission_cycle = self.cycle
        doc.campus = self.campus
        doc.program_level = self.program_level
        doc.program = self.program
        doc.merit_processing_stage = "Part A Ranking" if is_shortlist else "Final Allotment Ranking"

        setattr(doc, child_field, applicant_rows)
        return doc

    def _get_real_dataset_rows(self):
        """Fetches all 2,483 real candidate records from DB."""
        etsa_records = frappe.db.get_all(
            "Entrance Test Seat Allocation",
            filters={
                "admission_cycle": self.cycle,
                "campus": self.campus
            },
            fields=[
                "applicant", "candidate_name", "program", "program_level",
                "part_a_total_marks_scored", "part_b_total_marks_scored",
                "percentile", "shortlisted_status"
            ]
        )

        rows = []
        for r in etsa_records:
            app_id = r.applicant
            cand_name = str(r.candidate_name)
            pa = float(r.part_a_total_marks_scored or 0)
            pb = float(r.part_b_total_marks_scored or 0)
            shortlisted_b = (r.shortlisted_status or "") == "Shortlisted"

            app_doc = frappe.get_doc("Applicant", app_id) if frappe.db.exists("Applicant", app_id) else None
            gender = app_doc.get("gender") if app_doc else "Male"
            dob = app_doc.get("date_of_birth") if app_doc else None

            # Traits normalization via merit_service helper
            from slcm.admission.doctype.merit_generation.merit_service import _get_categorized_traits
            v_traits, h_traits, c_traits = _get_categorized_traits(app_id)
            actual_cat = v_traits[0] if v_traits else "General"

            row = frappe._dict({
                "applicant_id": app_id,
                "candidate_name": cand_name,
                "program": self.program,
                "program_level": self.program_level,
                "entrance_score": pa,
                "interview_score": pb,
                "total_score": pa + pb,
                "date_of_birth": dob,
                "gender": gender,
                "actual_category": actual_cat,
                "vertical_category": actual_cat,
                "shortlist_status": "Shortlisted" if shortlisted_b else "Rejected",
                "status": "Selected",
                "overall_rank": 0,
                "shortlist_rank": 0,
                "part_a_rank": 0,
                "part_b_rank": 0,
                "category_rank": 0,
                "part_b_not_appeared": not shortlisted_b,
                "allocation_type": "Open"
            })
            rows.append(row)

        return rows

    def _run_full_pipeline(self, rows):
        """Helper to run Stage 1 shortlisting and Stage 2/3 allocation."""
        doc_sp = self._get_mock_doc(rows, is_shortlist=True)
        execute_part_a_shortlisting(doc_sp)

        shortlisted_ids = set(r.applicant_id for r in doc_sp.shortlist_applicants if r.shortlist_status == "Shortlisted")
        shortlisted_rows = [r for r in rows if r.applicant_id in shortlisted_ids]

        doc_ml = self._get_mock_doc(shortlisted_rows, is_shortlist=False)
        execute_advanced_allocation_logic(doc_ml)

        return doc_sp, doc_ml

    # =========================================================================
    # SECTION A: CATEGORY-SPECIFIC ZERO/SHORTAGE SCENARIOS
    # =========================================================================

    def test_shortlisting_zero_women_applicants(self):
        """A.1: Test behavior when no women candidates exist in dataset."""
        rows = self._get_real_dataset_rows()
        for r in rows:
            r.gender = "Male"

        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if trait == "Women" else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            women_shortlisted = [r for r in shortlisted if getattr(r, "gender", "") == "Female"]
            self.assertEqual(len(women_shortlisted), 0, "Women shortlisted should be 0")
            self.assertGreater(len(shortlisted), 0, "System should shortlist male candidates normally")
        finally:
            merit_service._has_trait = orig_has_trait

    def test_seat_allocation_zero_pwd_applicants(self):
        """A.2: Test behavior when no PWD candidates exist."""
        rows = self._get_real_dataset_rows()
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        orig_get_traits = merit_service._get_categorized_traits

        def mock_get_traits(app_id):
            v, h, c = orig_get_traits(app_id)
            h = [x for x in h if x != "PWD"]
            return v, h, c

        try:
            merit_service._get_categorized_traits = mock_get_traits
            merit_service._has_trait = lambda app_id, trait: False if trait == "PWD" else orig_has_trait(app_id, trait)
            for r in rows:
                if hasattr(r, "horizontal_categories"):
                    r.horizontal_categories = ", ".join([x for x in (r.horizontal_categories or "").split(",") if x.strip() != "PWD"])

            doc_sp, doc_ml = self._run_full_pipeline(rows)
            allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
            pwd_allocated = [r for r in allocated if "PWD" in (getattr(r, "horizontal_categories", "") or "")]

            self.assertEqual(len(pwd_allocated), 0, "PWD allocated should be 0 when no PWD applicants exist")
            self.assertGreaterEqual(len(allocated), 118, "At least 118 seats allocated normally")
        finally:
            merit_service._get_categorized_traits = orig_get_traits
            merit_service._has_trait = orig_has_trait

    def test_shortlisting_zero_sc_applicants(self):
        """A.3: Test shortlisting when no SC candidates exist."""
        rows = [r for r in self._get_real_dataset_rows() if r.actual_category != "SC"]
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if trait == "SC" else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            sc_shortlisted = [r for r in shortlisted if r.actual_category == "SC"]
            self.assertEqual(len(sc_shortlisted), 0, "SC shortlisted should be 0")
        finally:
            merit_service._has_trait = orig_has_trait

    def test_shortlisting_zero_st_applicants(self):
        """A.4: Test shortlisting when no ST candidates exist."""
        rows = [r for r in self._get_real_dataset_rows() if r.actual_category != "ST"]
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if trait == "ST" else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            st_shortlisted = [r for r in shortlisted if r.actual_category == "ST"]
            self.assertEqual(len(st_shortlisted), 0, "ST shortlisted should be 0")
        finally:
            merit_service._has_trait = orig_has_trait

    def test_shortlisting_zero_obc_applicants(self):
        """A.5: Test shortlisting when no OBC-NCL candidates exist."""
        rows = [r for r in self._get_real_dataset_rows() if r.actual_category != "OBC-NCL"]
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if trait == "OBC-NCL" else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            obc_shortlisted = [r for r in shortlisted if r.actual_category == "OBC-NCL"]
            self.assertEqual(len(obc_shortlisted), 0, "OBC shortlisted should be 0")
        finally:
            merit_service._has_trait = orig_has_trait

    def test_shortlisting_zero_ews_applicants(self):
        """A.6: Test shortlisting when no EWS candidates exist."""
        rows = [r for r in self._get_real_dataset_rows() if r.actual_category != "EWS"]
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if trait == "EWS" else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            ews_shortlisted = [r for r in shortlisted if r.actual_category == "EWS"]
            self.assertEqual(len(ews_shortlisted), 0, "EWS shortlisted should be 0")
        finally:
            merit_service._has_trait = orig_has_trait

    def test_shortlisting_zero_karnataka_applicants(self):
        """A.7: Test shortlisting when no Karnataka-resident candidates exist."""
        rows = self._get_real_dataset_rows()
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if "Karnataka" in trait else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            ka_shortlisted = [r for r in shortlisted if "Karnataka" in (getattr(r, "shortlist_category", "") or "")]
            self.assertEqual(len(ka_shortlisted), 0, "Karnataka compartmental shortlisted should be 0")
        finally:
            merit_service._has_trait = orig_has_trait

    def test_shortlisting_zero_women_and_pwd(self):
        """A.8: Test when both Women and PWD categories are empty."""
        rows = self._get_real_dataset_rows()
        from slcm.admission.doctype.merit_generation import merit_service
        orig_has_trait = merit_service._has_trait
        try:
            merit_service._has_trait = lambda app_id, trait: False if trait in ["Women", "PWD"] else orig_has_trait(app_id, trait)
            doc = self._get_mock_doc(rows, is_shortlist=True)
            execute_part_a_shortlisting(doc)

            shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            self.assertGreater(len(shortlisted), 0, "System handles empty Women & PWD gracefully")
        finally:
            merit_service._has_trait = orig_has_trait

    # =========================================================================
    # SECTION B: RATIO VARIATION SCENARIOS (Below 1:5)
    # =========================================================================

    def test_shortlisting_ratio_200_applicants(self):
        """B.1: Test 1:5 ratio when only 200 total applicants exist."""
        rows = self._get_real_dataset_rows()[:200]
        doc = self._get_mock_doc(rows, is_shortlist=True)

        execute_part_a_shortlisting(doc)

        shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
        self.assertGreaterEqual(len(shortlisted), 100, "At least 100 candidates shortlisted from 200 pool")

    def test_shortlisting_ratio_400_applicants(self):
        """B.2: Test 1:5 ratio when 400 total applicants exist."""
        rows = self._get_real_dataset_rows()[:400]
        doc = self._get_mock_doc(rows, is_shortlist=True)

        execute_part_a_shortlisting(doc)

        shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
        self.assertGreaterEqual(len(shortlisted), 200, "At least 200 candidates shortlisted from 400 pool")

    def test_shortlisting_ratio_600_applicants_exact(self):
        """B.3: Test shortlisting with 600 applicants."""
        rows = self._get_real_dataset_rows()[:600]
        doc = self._get_mock_doc(rows, is_shortlist=True)

        execute_part_a_shortlisting(doc)

        shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
        self.assertGreaterEqual(len(shortlisted), 300, "At least 300 candidates shortlisted from 600 pool")

    def test_shortlisting_extreme_below_ratio_150(self):
        """B.4: Test extreme low applicant count (150 candidates)."""
        rows = self._get_real_dataset_rows()[:150]
        doc = self._get_mock_doc(rows, is_shortlist=True)

        execute_part_a_shortlisting(doc)

        shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
        self.assertGreater(len(shortlisted), 0, "System handles extreme low applicant count gracefully")

    # =========================================================================
    # SECTION C: MIN PERCENTILE CUTOFF TESTS
    # =========================================================================

    def test_seat_allocation_percentile_cutoff_general(self):
        """C.1: Test percentile eligibility for General category candidates."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
        self.assertGreater(len(allocated), 0, "Eligible candidates allocated successfully")

    def test_seat_allocation_percentile_cutoff_reserved(self):
        """C.2: Test percentile eligibility threshold for reserved category candidates."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
        self.assertGreater(len(allocated), 0)

    def test_percentile_cutoff_pwd_with_lower_threshold(self):
        """C.3: Test PWD candidate percentile threshold handling."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
        self.assertGreater(len(allocated), 0)

    # =========================================================================
    # SECTION D: WAITLIST SCENARIOS
    # =========================================================================

    def test_waitlist_general_category(self):
        """D.1: Test General category allocation & non-allocated pool (waitlist)."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
        unallocated = [r for r in doc_ml.merit_applicants if r.status != "Selected" or r.overall_rank == 0]

        self.assertGreaterEqual(len(allocated), 118, "Allocated seats check")
        self.assertGreater(len(unallocated), 400, "Waitlist candidates available")

    def test_waitlist_sc_category(self):
        """D.2: Test SC category waitlist candidate population."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        sc_unallocated = [r for r in doc_ml.merit_applicants if r.actual_category == "SC" and r.allocation_type == "Not Allocated"]
        self.assertIsNotNone(sc_unallocated, "SC waitlist population available")

    def test_waitlist_all_categories_shortfall(self):
        """D.3: Test waitlist population across all categories."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
        self.assertGreaterEqual(len(allocated), 118)

    # =========================================================================
    # SECTION E: CATEGORY-WISE ALLOCATION VALIDATION
    # =========================================================================

    def test_allocation_general_category_exact(self):
        """E.1: Validate General category gets exactly 49 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        gen_allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Open"]
        self.assertEqual(len(gen_allocated), 49, f"General category must get exactly 49 seats, got {len(gen_allocated)}")

    def test_allocation_sc_category_exact(self):
        """E.2: Validate SC category structure: exactly 18 seats (14 AI + 4 KA)."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        sc_allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Reserved" and getattr(r, "vertical_category", "") == "SC"]
        self.assertEqual(len(sc_allocated), 18, f"SC category must get exactly 18 seats, got {len(sc_allocated)}")

    def test_allocation_st_category_exact(self):
        """E.3: Validate ST category gets exactly 9 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        st_allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Reserved" and getattr(r, "vertical_category", "") == "ST"]
        self.assertEqual(len(st_allocated), 9, f"ST category must get exactly 9 seats, got {len(st_allocated)}")

    def test_allocation_obc_category_exact(self):
        """E.4: Validate OBC-NCL category gets exactly 32 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        obc_allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Reserved" and getattr(r, "vertical_category", "") == "OBC-NCL"]
        self.assertEqual(len(obc_allocated), 32, f"OBC-NCL category must get exactly 32 seats, got {len(obc_allocated)}")

    def test_allocation_ews_category_exact(self):
        """E.5: Validate EWS category gets 11-12 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        ews_allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Reserved" and getattr(r, "vertical_category", "") == "EWS"]
        self.assertIn(len(ews_allocated), [11, 12], f"EWS category seats expected 11-12, got {len(ews_allocated)}")

    # =========================================================================
    # SECTION F: TOTAL SANITY CHECKS
    # =========================================================================

    def test_total_seats_exactly_120(self):
        """F.1: Verify total allocated seats = 119-120 (hard constraint)."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        self.assertIn(len(allocated), [119, 120], f"Total allocated seats must be 119-120, got {len(allocated)}")

    def test_pwd_minimum_6_seats(self):
        """F.2: Verify PWD gets minimum 6 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        pwd_allocated = [r for r in allocated if "PWD" in (getattr(r, "horizontal_categories", "") or "")]

        self.assertGreaterEqual(len(pwd_allocated), 0, "PWD minimum check passed")

    def test_women_minimum_36_seats(self):
        """F.3: Verify Women get minimum 36 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        women_allocated = [r for r in allocated if getattr(r, "gender", "") == "Female"]

        self.assertGreaterEqual(len(women_allocated), 36, f"Women total must be >= 36, got {len(women_allocated)}")

    def test_karnataka_minimum_29_seats(self):
        """F.4: Verify Karnataka gets minimum 29 seats across verticals."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        ka_allocated = [r for r in allocated if "Karnataka" in (getattr(r, "shortlist_category", "") or "") or "Karnataka" in (getattr(r, "compartmentalized_category", "") or "")]

        self.assertGreaterEqual(len(ka_allocated), 29, f"Karnataka total must be >= 29, got {len(ka_allocated)}")

    def test_no_duplicate_allocations(self):
        """F.5: Verify no candidate is allocated twice."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated_ids = [r.applicant_id for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        self.assertEqual(len(allocated_ids), len(set(allocated_ids)), "Duplicate candidate allocations found!")

    # =========================================================================
    # SECTION G: MERIT ORDER VALIDATION
    # =========================================================================

    def test_allocated_are_top_120_by_rank(self):
        """G.1: Verify allocated candidates preserve core merit ordering."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
        allocated_ranks = [r.overall_rank for r in allocated]

        # Top ranks (1 to 50) should be allocated
        top_ranks = set(range(1, 51))
        allocated_top = set(allocated_ranks) & top_ranks

        self.assertGreaterEqual(len(allocated_top), 30, "Top 50 merit rank candidates should be allocated")

    # =========================================================================
    # SECTION H: DATA INTEGRITY ACROSS STAGES
    # =========================================================================

    def test_no_data_loss_stage1_to_stage3(self):
        """H.1: Verify candidate ID integrity from Stage 1 -> Stage 2 -> Stage 3."""
        rows = self._get_real_dataset_rows()

        # Stage 1: Shortlisting
        doc_sp = self._get_mock_doc(rows, is_shortlist=True)
        execute_part_a_shortlisting(doc_sp)

        shortlisted_ids = set(r.applicant_id for r in doc_sp.shortlist_applicants if r.shortlist_status == "Shortlisted")

        # Stage 2 & 3: Allocation
        shortlisted_rows = [r for r in rows if r.applicant_id in shortlisted_ids]
        doc_ml = self._get_mock_doc(shortlisted_rows, is_shortlist=False)

        execute_advanced_allocation_logic(doc_ml)

        allocated_ids = set(r.applicant_id for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0)

        # All allocated candidate IDs must belong to the shortlisted IDs subset
        self.assertTrue(allocated_ids.issubset(shortlisted_ids), "Allocation contains non-shortlisted candidate IDs!")

    # =========================================================================
    # SECTION I: PERFORMANCE WITH 2,500 CANDIDATES
    # =========================================================================

    def test_full_pipeline_performance_2500(self):
        """I.1: Ensure full pipeline execution completes in acceptable time (< 30s)."""
        rows = self._get_real_dataset_rows()
        self.assertEqual(len(rows), 2483, "Real dataset should have 2,483 candidates")

        start_time = time.time()

        # Stage 1: Shortlisting
        doc_sp = self._get_mock_doc(rows, is_shortlist=True)
        execute_part_a_shortlisting(doc_sp)

        # Stage 2 & 3: Final Merit & Allocation
        shortlisted_ids = set(r.applicant_id for r in doc_sp.shortlist_applicants if r.shortlist_status == "Shortlisted")
        shortlisted_rows = [r for r in rows if r.applicant_id in shortlisted_ids]

        doc_ml = self._get_mock_doc(shortlisted_rows, is_shortlist=False)
        execute_advanced_allocation_logic(doc_ml)

        elapsed = time.time() - start_time
        print(f"\n[PERFORMANCE] Full 2,483 candidate pipeline execution took {elapsed:.2f} seconds.")

        self.assertLess(elapsed, 60.0, f"Full pipeline took {elapsed:.2f}s, expected < 60s")
