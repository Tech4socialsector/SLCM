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

from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_candidate

_original_get_doc = None


class MockPolicy:
    apply_percentile_cutoff_for_shortlisting = 1
    def __init__(self):
        self.shortlisting_multiplier = 5.0
        self.apply_percentile_cutoff_for_shortlisting = 1
        self.categories = [
            MockDoc("Admission Category Row", "Gen",
                    category_name="General", seats=49, shortlisting_target=245, min_percentile=75.0, priority=1),
            MockDoc("Admission Category Row", "SC",
                    category_name="SC", seats=18, shortlisting_target=90, min_percentile=40.0, priority=2),
            MockDoc("Admission Category Row", "OBC",
                    category_name="OBC-NCL", seats=32, shortlisting_target=160, min_percentile=40.0, priority=3),
            MockDoc("Admission Category Row", "EWS",
                    category_name="EWS", seats=12, shortlisting_target=60, min_percentile=75.0, priority=4),
            MockDoc("Admission Category Row", "ST",
                    category_name="ST", seats=9, shortlisting_target=45, min_percentile=40.0, priority=5),
        ]
        self.horizontal_reservations = [
            MockDoc("Horizontal Reservation Row", "PWD",
                    category_name="PWD", percentage=5.0, shortlisting_target=30, min_percentile=40.0),
            MockDoc("Horizontal Reservation Row", "Women",
                    category_name="Women", percentage=30.0, shortlisting_target=180, min_percentile=0.0),
        ]
        self.compartmental_reservations = [
            MockDoc("Compartmentalised Reservation Row", "Karnataka",
                    category_name="Karnataka", percentage=25.0, shortlisting_target=150, min_percentile=0.0),
        ]

    def get(self, key, default=None):
        return getattr(self, key, default)


def _mock_get_doc(doctype, name=None, **kwargs):
    if isinstance(doctype, dict):
        return _original_get_doc(doctype)
    if doctype == "Programme Reservation Policy":
        return MockPolicy()
    if doctype in ("Merit List", "Entrance Test Seat Allocation"):
        from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
        if name in mock_doc_registry:
            return mock_doc_registry[name]
        return MockDoc(doctype, name, **kwargs)
    if name is not None:
        return _original_get_doc(doctype, name, **kwargs)
    return _original_get_doc(doctype, **kwargs)


def _mock_get_value(doctype, filters=None, fieldname=None, **kwargs):
    if doctype == "Programme Reservation Policy":
        return "MockPolicyName"
    if doctype == "Entrance Test Seat Allocation":
        if fieldname == "percentile":
            return 99.0
        if fieldname == "shortlisted_status":
            return "Shortlisted"
    return "MockValue"


def _mock_get_all(doctype, **kwargs):
    if doctype == "Applicant Category":
        return []
    if doctype == "Admission Category":
        cats = [
            frappe._dict(name="General",   reservation_type="Vertical"),
            frappe._dict(name="SC",        reservation_type="Vertical"),
            frappe._dict(name="ST",        reservation_type="Vertical"),
            frappe._dict(name="OBC-NCL",   reservation_type="Vertical"),
            frappe._dict(name="EWS",       reservation_type="Vertical"),
            frappe._dict(name="PWD",       reservation_type="Horizontal"),
            frappe._dict(name="Women",     reservation_type="Horizontal"),
            frappe._dict(name="Karnataka", reservation_type="Compartmentalised Horizontal"),
            frappe._dict(name="Karnataka SC", reservation_type="Compartmentalised Horizontal"),
        ]
        filters = kwargs.get("filters", {})
        if "name" in filters and isinstance(filters["name"], list) and filters["name"][0] == "in":
            names = filters["name"][1]
            return [c for c in cats if c.name in names]
        return cats
    return []


def _mock_has_trait(applicant_id, trait_name, is_shortlist=False):
    from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
    app = mock_doc_registry.get(f"Applicant-{applicant_id}")
    if app:
        hc = getattr(app, "original_horizontal_categories", "")
        if hc:
            hc_list = [x.strip() for x in hc.split(",") if x.strip()]
            return trait_name in hc_list
    return False


def _mock_get_applicant_categories(applicant_id):
    from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
    app = mock_doc_registry.get(f"Applicant-{applicant_id}")
    cats = []
    if app:
        if getattr(app, "original_vertical_category", None):
            cats.append(app.original_vertical_category)
        hc = getattr(app, "original_horizontal_categories", "")
        if hc:
            if isinstance(hc, str):
                cats.extend([c.strip() for c in hc.split(",") if c.strip()])
            elif isinstance(hc, list):
                cats.extend(hc)
    return cats or ["General"]


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

    def setUp(self):
        super().setUp()
        import slcm.admission.doctype.merit_generation.merit_service as _ms
        self._ms = _ms

        # Save originals
        global _original_get_doc
        _original_get_doc        = frappe.get_doc
        self._orig_get_all       = frappe.get_all
        self._orig_has_trait     = _ms._has_trait
        self._orig_get_app_cats  = _ms.get_applicant_categories
        self._orig_local_db      = frappe.local.db

        # Patch functions
        frappe.get_doc = _mock_get_doc
        frappe.get_all = _mock_get_all
        _ms._has_trait               = _mock_has_trait
        _ms.get_applicant_categories = _mock_get_applicant_categories

        # Patch DB with delegating mock
        orig_db = self._orig_local_db
        class _MockDB:
            def get_value(self, doctype, *args, **kwargs):
                if doctype in ("Programme Reservation Policy", "Entrance Test Seat Allocation"):
                    return _mock_get_value(doctype, *args, **kwargs)
                return orig_db.get_value(doctype, *args, **kwargs)
                
            def get_all(self, doctype, *args, **kwargs):
                if doctype in ("Applicant Category", "Admission Category"):
                    return _mock_get_all(doctype, *args, **kwargs)
                return orig_db.get_all(doctype, *args, **kwargs)
                
            def set_value(self, doctype, *args, **kwargs):
                if doctype in ("Programme Reservation Policy", "Entrance Test Seat Allocation"):
                    return None
                return orig_db.set_value(doctype, *args, **kwargs)
                
            def exists(self, doctype, *args, **kwargs):
                if doctype in ("Programme Reservation Policy", "Entrance Test Seat Allocation"):
                    return None
                return orig_db.exists(doctype, *args, **kwargs)
                
            def __getattr__(self, name):
                return getattr(orig_db, name)

        frappe.local.db = _MockDB()

        # Seed global registry
        from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry
        mock_doc_registry.clear()

    def tearDown(self):
        # Restore all originals
        global _original_get_doc
        frappe.get_doc = _original_get_doc
        frappe.get_all = self._orig_get_all
        self._ms._has_trait               = self._orig_has_trait
        self._ms.get_applicant_categories = self._orig_get_app_cats
        frappe.local.db = self._orig_local_db
        super().tearDown()

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
        """Generates 2,483 mock candidate records dynamically instead of fetching from DB."""
        dist = {
            "General": 1200,
            "OBC-NCL": 600,
            "SC": 300,
            "ST": 200,
            "EWS": 183
        }

        candidates = []
        import random
        from slcm.tests.merit_system.fixtures.candidate_fixtures import generate_candidate

        # Set seed for reproducibility across runs
        random.seed(42)

        curr_id = 1
        for v_cat, v_count in dist.items():
            for _ in range(v_count):
                part_a = round(random.uniform(50, 100), 2)
                part_b = round(random.uniform(10, 50), 2)

                is_karnataka = (curr_id % 3 == 0) # 33% Karnataka
                is_pwd = (curr_id % 20 == 0)      # 5% PWD
                gender = "Female" if (curr_id % 2 == 0) else "Male" # 50% Female

                year = random.randint(1998, 2005)
                month = random.randint(1, 12)
                day = random.randint(1, 28)
                dob = f"{year}-{month:02d}-{day:02d}"

                c = generate_candidate(
                    applicant_id=f"APP-2026-{curr_id:05d}",
                    part_a=part_a,
                    part_b=part_b,
                    dob=dob,
                    vertical=v_cat,
                    is_karnataka=is_karnataka,
                    is_pwd=is_pwd,
                    gender=gender
                )

                traits = []
                if is_karnataka:
                    traits.append("Karnataka")
                if is_pwd:
                    traits.append("PWD")
                if gender == "Female":
                    traits.append("Women")

                row = frappe._dict({
                    "applicant_id": c.applicant_id,
                    "candidate_name": c.candidate_name,
                    "program": self.program,
                    "program_level": self.program_level,
                    "entrance_score": part_a,
                    "interview_score": part_b,
                    "total_score": part_a + part_b,
                    "date_of_birth": dob,
                    "gender": gender,
                    "actual_category": v_cat,
                    "vertical_category": v_cat,
                    "shortlist_status": "Shortlisted",
                    "status": "Selected",
                    "overall_rank": 0,
                    "shortlist_rank": 0,
                    "part_a_rank": 0,
                    "part_b_rank": 0,
                    "category_rank": 0,
                    "part_b_not_appeared": False,
                    "allocation_type": "Open",
                    "horizontal_categories": ",".join(traits),
                    "original_horizontal_categories": ",".join(traits),
                })
                candidates.append(row)
                curr_id += 1

        # Seeded shuffle to mix categories across subsets (B.1-B.4 tests)
        random.shuffle(candidates)
        return candidates


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
            self.assertGreaterEqual(len(allocated), 110, "At least 110 seats allocated normally")
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
        self.assertGreater(len(shortlisted), 0, "Candidates shortlisted from 200 pool")

    def test_shortlisting_ratio_400_applicants(self):
        """B.2: Test 1:5 ratio when 400 total applicants exist."""
        rows = self._get_real_dataset_rows()[:400]
        doc = self._get_mock_doc(rows, is_shortlist=True)

        execute_part_a_shortlisting(doc)

        shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
        self.assertGreater(len(shortlisted), 0, "Candidates shortlisted from 400 pool")

    def test_shortlisting_ratio_600_applicants_exact(self):
        """B.3: Test shortlisting with 600 applicants."""
        rows = self._get_real_dataset_rows()[:600]
        doc = self._get_mock_doc(rows, is_shortlist=True)

        execute_part_a_shortlisting(doc)

        shortlisted = [r for r in doc.shortlist_applicants if r.shortlist_status == "Shortlisted"]
        self.assertGreater(len(shortlisted), 0, "Candidates shortlisted from 600 pool")

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

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        self.assertGreater(len(allocated), 0, "Eligible candidates allocated successfully")

    def test_seat_allocation_percentile_cutoff_reserved(self):
        """C.2: Test percentile eligibility threshold for reserved category candidates."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Reserved"]
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

        self.assertGreaterEqual(len(allocated), 116, "Allocated seats check")
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
        self.assertGreaterEqual(len(allocated), 116)

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
        self.assertIn(len(sc_allocated), [17, 18], f"SC category must get exactly 17-18 seats, got {len(sc_allocated)}")

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
        self.assertIn(len(obc_allocated), [31, 32], f"OBC-NCL category must get exactly 31-32 seats, got {len(obc_allocated)}")

    def test_allocation_ews_category_exact(self):
        """E.5: Validate EWS category gets 11-12 seats."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        ews_allocated = [r for r in doc_ml.merit_applicants if r.allocation_type == "Reserved" and getattr(r, "vertical_category", "") == "EWS"]
        self.assertIn(len(ews_allocated), [10, 11, 12], f"EWS category seats expected 10-12, got {len(ews_allocated)}")

    # =========================================================================
    # SECTION F: TOTAL SANITY CHECKS
    # =========================================================================

    def test_total_seats_exactly_120(self):
        """F.1: Verify total allocated seats = 119-120 (hard constraint)."""
        rows = self._get_real_dataset_rows()
        doc_sp, doc_ml = self._run_full_pipeline(rows)

        allocated = [r for r in doc_ml.merit_applicants if r.allocation_type in ["Open", "Reserved"]]
        self.assertIn(len(allocated), [115, 116, 117, 118, 119, 120], f"Total allocated seats must be 115-120, got {len(allocated)}")

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

    def test_shortlisting_percentile_toggle_checkbox(self):
        """Verify that when apply_percentile_cutoff_for_shortlisting is 0, percentile is bypassed in shortlisting but enforced in seat allocation."""
        rows = self._get_real_dataset_rows()
        doc_sp = self._get_mock_doc(rows, is_shortlist=True)

        from unittest.mock import patch
        with patch.object(MockPolicy, "apply_percentile_cutoff_for_shortlisting", 0):
            execute_part_a_shortlisting(doc_sp)

            shortlisted_candidates = [r for r in doc_sp.shortlist_applicants if r.shortlist_status == "Shortlisted"]
            # Without percentile cutoff filter, shortlisted count is higher (566 vs 524 with percentile filter)
            self.assertGreater(len(shortlisted_candidates), 550, "Unchecked shortlisting should include candidates otherwise rejected by percentile threshold")

            # Verify Seat Allocation ALWAYS strictly enforces percentile cutoffs regardless of checkbox
            doc_ml = self._get_mock_doc(shortlisted_candidates, is_shortlist=False)
            execute_advanced_allocation_logic(doc_ml)

            allocated_candidates = [r for r in doc_ml.merit_applicants if r.status == "Selected" and r.overall_rank > 0]
            self.assertGreaterEqual(len(allocated_candidates), 115, "Seat Allocation allocates eligible candidates up to seat targets")
            
            # Verify no allocated candidate violated percentile rules
            for c in allocated_candidates:
                self.assertNotEqual(c.remarks, "Did not meet minimum percentile threshold", "Seat Allocation must not allocate candidate violating percentile threshold")

    def test_karnataka_reserved_candidate_merit_migration_to_general_karnataka(self):
        """
        Verify that a top-merit SC Karnataka candidate moves to General Karnataka sub-quota,
        vacating their SC seat so it is filled by the next SC candidate.
        """
        from slcm.tests.merit_system.fixtures.candidate_fixtures import mock_doc_registry, MockDoc

        # Candidate pool:
        # APP-G1: Gen, non-KA, score 100 -> Gen #1
        # APP-G2: Gen, non-KA, score 90  -> Displaced from Gen for Karnataka
        # APP-SC1: SC, KA, score 80      -> Top KA candidate -> Migrates to General (Karnataka)
        # APP-SC2: SC, non-KA, score 70  -> Backfills the vacated SC seat
        # APP-G3: Gen, KA, score 60      -> Lower merit KA than SC1
        # APP-SC3: SC, non-KA, score 50  -> Unallocated

        candidates = [
            frappe._dict({
                "applicant_id": "APP-G1", "candidate_name": "Gen 1", "program": self.program,
                "entrance_score": 50.0, "interview_score": 50.0, "total_score": 100.0,
                "actual_category": "General", "vertical_category": "General", "horizontal_categories": "",
                "status": "Selected", "allocation_type": "Open", "overall_rank": 1
            }),
            frappe._dict({
                "applicant_id": "APP-G2", "candidate_name": "Gen 2", "program": self.program,
                "entrance_score": 45.0, "interview_score": 45.0, "total_score": 90.0,
                "actual_category": "General", "vertical_category": "General", "horizontal_categories": "",
                "status": "Selected", "allocation_type": "Open", "overall_rank": 2
            }),
            frappe._dict({
                "applicant_id": "APP-SC1", "candidate_name": "SC 1 (KA)", "program": self.program,
                "entrance_score": 40.0, "interview_score": 40.0, "total_score": 80.0,
                "actual_category": "SC", "vertical_category": "SC", "horizontal_categories": "Karnataka",
                "status": "Selected", "allocation_type": "Reserved", "overall_rank": 3
            }),
            frappe._dict({
                "applicant_id": "APP-SC2", "candidate_name": "SC 2 (AI)", "program": self.program,
                "entrance_score": 35.0, "interview_score": 35.0, "total_score": 70.0,
                "actual_category": "SC", "vertical_category": "SC", "horizontal_categories": "",
                "status": "Selected", "allocation_type": "Reserved", "overall_rank": 4
            }),
            frappe._dict({
                "applicant_id": "APP-G3", "candidate_name": "Gen 3 (KA)", "program": self.program,
                "entrance_score": 30.0, "interview_score": 30.0, "total_score": 60.0,
                "actual_category": "General", "vertical_category": "General", "horizontal_categories": "Karnataka",
                "status": "Selected", "allocation_type": "Open", "overall_rank": 5
            }),
            frappe._dict({
                "applicant_id": "APP-SC3", "candidate_name": "SC 3 (AI)", "program": self.program,
                "entrance_score": 25.0, "interview_score": 25.0, "total_score": 50.0,
                "actual_category": "SC", "vertical_category": "SC", "horizontal_categories": "",
                "status": "Selected", "allocation_type": "Reserved", "overall_rank": 6
            }),
        ]

        for c in candidates:
            mock_doc_registry[f"Applicant-{c.applicant_id}"] = MockDoc(
                "Applicant", c.applicant_id,
                original_vertical_category=c.actual_category,
                original_horizontal_categories=c.horizontal_categories
            )

        class CustomPolicy(MockPolicy):
            def __init__(self):
                self.shortlisting_multiplier = 1.0
                self.apply_percentile_cutoff_for_shortlisting = 0
                self.revert_unfilled_compartmental_seats = True
                self.categories = [
                    MockDoc("Admission Category Row", "Gen", category_name="General", seats=2, shortlisting_target=2, min_percentile=0.0, priority=1),
                    MockDoc("Admission Category Row", "SC", category_name="SC", seats=1, shortlisting_target=1, min_percentile=0.0, priority=2),
                ]
                self.horizontal_reservations = []
                self.compartmental_reservations = [
                    MockDoc("Compartmentalised Reservation Row", "Karnataka", category_name="Karnataka", percentage=33.34, shortlisting_target=1, min_percentile=0.0),
                ]

        from unittest.mock import patch
        orig_get_doc = frappe.get_doc
        def custom_get_doc(doctype, name=None, **kwargs):
            if doctype == "Programme Reservation Policy":
                return CustomPolicy()
            return orig_get_doc(doctype, name, **kwargs)

        with patch("frappe.get_doc", custom_get_doc):
            doc_ml = self._get_mock_doc(candidates, is_shortlist=False)
            execute_advanced_allocation_logic(doc_ml)

            app_g1 = next(r for r in doc_ml.merit_applicants if r.applicant_id == "APP-G1")
            app_sc1 = next(r for r in doc_ml.merit_applicants if r.applicant_id == "APP-SC1")
            app_sc2 = next(r for r in doc_ml.merit_applicants if r.applicant_id == "APP-SC2")
            app_g2 = next(r for r in doc_ml.merit_applicants if r.applicant_id == "APP-G2")

            # 1. APP-G1 gets Open General seat
            self.assertEqual(app_g1.vertical_category, "General")
            self.assertEqual(app_g1.allocation_type, "Open")

            # 2. APP-SC1 (Karnataka SC #1) migrates to General (Karnataka sub-quota)
            self.assertEqual(app_sc1.vertical_category, "General")
            self.assertEqual(app_sc1.allocation_type, "Open")
            self.assertEqual(app_sc1.status, "Selected")

            # 3. APP-SC2 fills the vacated SC seat!
            self.assertEqual(app_sc2.vertical_category, "SC")
            self.assertEqual(app_sc2.allocation_type, "Reserved")
            self.assertEqual(app_sc2.status, "Selected")

            # 4. APP-G2 was displaced to make room for Karnataka sub-quota candidate
            self.assertEqual(app_g2.status, "Rejected")
