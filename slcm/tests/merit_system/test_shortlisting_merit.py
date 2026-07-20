import pytest
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates, generate_candidate
from slcm.admission.doctype.merit_generation.merit_service import _rank_applicants, execute_part_a_shortlisting



class TestShortlistingMerit:
    
    def test_shortlisting_basic_1_to_5_ratio(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test 1")
        doc.program = "BA LLB"
        doc.admission_cycle = "2026"
        doc.merit_processing_stage = "Part A Ranking"
        
        candidates = generate_bulk_candidates(2500, vertical_distribution={"General": 2500})
        for c in candidates[:60]:
            c.is_karnataka = True
            c.horizontal_categories = "Karnataka"
            c.original_horizontal_categories = "Karnataka"
        
        # Ensure all distinct scores so exactly 245 General are taken
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - (i * 0.01)
            c.vertical_category = "General"
            
        doc.merit_applicants = candidates
        
        # Patch trait lookup
        import slcm.admission.doctype.merit_generation.merit_service as ms
        def mock_has_trait(app_id, trait, is_shortlist=False):
            return False
        monkeypatch.setattr(ms, "_has_trait", mock_has_trait)
        
        execute_part_a_shortlisting(doc)
        
        shortlisted = [c for c in doc.merit_applicants if c.status == "Selected"]
        # Wait, shortlisting_target for General in our mock policy is 245!
        # The prompt says 1:5 ratio of 100 seats = 500, but general is 49 * 5 = 245.
        assert len(shortlisted) == 245
        for c in shortlisted:
            assert c.status == "Selected"

    def test_shortlisting_ranking_desc_by_part_a(self):
        # Direct test of _rank_applicants
        candidates = generate_bulk_candidates(10, vertical_distribution={"General": 10})
        scores = [10, 50, 30, 20, 100, 90, 80, 40, 60, 70]
        for i, c in enumerate(candidates):
            c.total_score = scores[i]
            
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Part A Ranking")
        
        assert candidates[0].overall_rank == 1
        assert candidates[0].total_score == 100
        assert candidates[-1].overall_rank == 10
        assert candidates[-1].total_score == 10
        
        for i in range(len(candidates) - 1):
            assert candidates[i].total_score >= candidates[i+1].total_score

    def test_shortlisting_competition_ranking(self):
        candidates = generate_bulk_candidates(5, vertical_distribution={"General": 5})
        scores = [100, 95, 95, 90, 85]
        for i, c in enumerate(candidates):
            c.total_score = scores[i]
            # Must ensure applicant ids are deterministic for tiebreakers if needed, 
            # but Part A ranking uses same rank for same score.
            
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Part A Ranking")
        
        ranks = [c.overall_rank for c in candidates]
        assert ranks == [1, 2, 2, 4, 5]

    def test_shortlisting_tied_group_inclusion_small(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test 2", program="BA", admission_cycle="2026")
        candidates = generate_bulk_candidates(300, vertical_distribution={"General": 300})
        for c in candidates[:60]:
            c.is_karnataka = True
            c.horizontal_categories = "Karnataka"
            c.original_horizontal_categories = "Karnataka"
        
        # 244 candidates with distinct high scores
        for i in range(244):
            candidates[i].et_part_a_total_marks_scored = 100.0 - (i * 0.1)
            
        # 5 candidates tied at the boundary (rank 245)
        for i in range(244, 249):
            candidates[i].et_part_a_total_marks_scored = 50.0
            
        # Rest have lower scores
        for i in range(249, 300):
            candidates[i].et_part_a_total_marks_scored = 40.0 - (i * 0.1)
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        execute_part_a_shortlisting(doc)
        shortlisted = [c for c in doc.merit_applicants if c.status == "Selected"]
        
        # Target was 245, but the 245th rank has 5 people. All 5 should be included.
        # Total = 244 + 5 = 249
        assert len(shortlisted) == 249

    def test_shortlisting_tied_group_inclusion_large(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test 3", program="BA", admission_cycle="2026")
        candidates = generate_bulk_candidates(350, vertical_distribution={"General": 350})
        for c in candidates[:60]:
            c.is_karnataka = True
            c.horizontal_categories = "Karnataka"
            c.original_horizontal_categories = "Karnataka"
        
        for i in range(200):
            candidates[i].et_part_a_total_marks_scored = 100.0 - (i * 0.1)
            
        # 50 candidates tied at the boundary
        for i in range(200, 250):
            candidates[i].et_part_a_total_marks_scored = 60.0
            
        for i in range(250, 350):
            candidates[i].et_part_a_total_marks_scored = 30.0 - (i * 0.1)
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        execute_part_a_shortlisting(doc)
        shortlisted = [c for c in doc.merit_applicants if c.status == "Selected"]
        assert len(shortlisted) == 250

    def test_shortlisting_no_arbitrary_split_of_ties(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test 4", program="BA", admission_cycle="2026")
        candidates = generate_bulk_candidates(260, vertical_distribution={"General": 260})
        for c in candidates:
            # Clear random horizontal traits so we don't accidentally absorb remaining candidates for Women/PWD quota
            c.is_female = False
            c.is_pwd = False
            c.horizontal_categories = ""
            c.original_horizontal_categories = ""
            
        for c in candidates[:60]:
            c.is_karnataka = True
            c.horizontal_categories = "Karnataka"
            c.original_horizontal_categories = "Karnataka"
        
        for i in range(240):
            candidates[i].et_part_a_total_marks_scored = 100.0 - (i * 0.1)
            
        # 15 candidates tied at the boundary rank 241
        for i in range(240, 255):
            candidates[i].et_part_a_total_marks_scored = 50.0
            
        # Set rest to lower scores to avoid interfering
        for i in range(255, 260):
            candidates[i].et_part_a_total_marks_scored = 40.0
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        execute_part_a_shortlisting(doc)
        shortlisted = [c for c in doc.merit_applicants if c.status == "Selected"]
        assert len(shortlisted) == 255
        # Ensure tie group wasn't split
        tied_candidates = [c for c in shortlisted if c.et_part_a_total_marks_scored == 50.0]
        assert len(tied_candidates) == 15

    def test_category_rank_within_vertical_sc(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test 5", program="BA", admission_cycle="2026")
        candidates = generate_bulk_candidates(100, vertical_distribution={"SC": 100})
        
        for i in range(100):
            candidates[i].et_part_a_total_marks_scored = 100.0 - i
            candidates[i].nlsat_part_a_score = 100.0 - i
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        execute_part_a_shortlisting(doc)
        shortlisted = [c for c in doc.merit_applicants if c.status == "Selected"]
        
        # Target for SC is 90, but they all fit in General's 245 quota, so all 100 are selected
        assert len(shortlisted) == 100
        
        _rank_applicants(shortlisted, use_advanced_ranking=True, processing_stage="Part A Ranking")
        # Category rank should be 1 to 100
        ranks = [c.category_rank for c in shortlisted]
        assert max(ranks) == 100

    def test_general_absorption_ignores_underlying_vertical(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test 6", program="BA", admission_cycle="2026")
        
        candidates = generate_bulk_candidates(300, vertical_distribution={"General": 200, "SC": 100})
        # Make SC candidates score VERY HIGH (top 50)
        for i in range(200, 250):
            candidates[i].et_part_a_total_marks_scored = 200.0  # Beat all generals
            candidates[i].nlsat_part_a_score = 200.0
            
        # Make other SC candidates score VERY LOW so they don't accidentally get absorbed
        for i in range(250, 300):
            candidates[i].et_part_a_total_marks_scored = 10.0
            candidates[i].nlsat_part_a_score = 10.0

        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms

        execute_part_a_shortlisting(doc)

        absorbed_sc = [c for c in doc.merit_applicants if c.actual_category == "SC" and getattr(c, "allocation_type", "") == "Open"]
        # In shortlisting, do we use allocation_type="Open"? Yes, the merit logic does merit absorption
        assert len(absorbed_sc) == 50

    def test_shortlisting_with_zero_part_a_scores(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Zero", program="BA", admission_cycle="2026")
        candidates = generate_bulk_candidates(10, vertical_distribution={"General": 10})
        for c in candidates[:5]:
            c.et_part_a_total_marks_scored = 0
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        # Note: The processing skip is inside generate_merit_for_level, but execute_part_a_shortlisting
        # also naturally drops them if they are not selected, or they rank at bottom.
        # If the test is meant to ensure they are excluded, we can verify their status.
        execute_part_a_shortlisting(doc)
        
        selected = [c for c in doc.merit_applicants if c.status == "Selected"]
        for c in selected:
            assert c.et_part_a_total_marks_scored > 0

    def test_shortlisting_all_candidates_identical_score(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Identical", program="BA", admission_cycle="2026")
        candidates = generate_bulk_candidates(2500, vertical_distribution={"General": 2500})
        for c in candidates[:60]:
            c.is_karnataka = True
            c.horizontal_categories = "Karnataka"
            c.original_horizontal_categories = "Karnataka"
        for c in candidates:
            c.et_part_a_total_marks_scored = 50.0
            c.nlsat_part_a_score = 50.0
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        execute_part_a_shortlisting(doc)
        
        selected = [c for c in doc.merit_applicants if c.status == "Selected"]
        # All 2500 should be selected since they all tie at Rank 1
        assert len(selected) == 2500
