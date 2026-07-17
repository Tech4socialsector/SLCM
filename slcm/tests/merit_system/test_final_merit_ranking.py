import pytest
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates, generate_candidate
from slcm.admission.doctype.merit_generation.merit_service import _rank_applicants

class TestFinalMeritRanking:
    def test_final_merit_total_score_calculation(self):
        # We calculate the total in generate_candidate but let's assert it manually
        c = generate_candidate("APP-001", part_a=75.5, part_b=40.25)
        # Assuming the caller adds them
        total = c.et_part_a_total_marks_scored + c.et_part_b_total_marks_scored
        assert round(total, 2) == 115.75

    def test_final_merit_ranking_by_total_desc(self):
        candidates = generate_bulk_candidates(600)
        # Ensure distinct scores
        for i, c in enumerate(candidates):
            c.total_score = 200.0 - (i * 0.1)
            
        # Shuffle them
        import random
        random.shuffle(candidates)
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        for i in range(len(candidates) - 1):
            assert candidates[i].total_score >= candidates[i+1].total_score
            assert candidates[i].overall_rank < candidates[i+1].overall_rank

    def test_final_merit_rank_1_to_n_sequential(self):
        candidates = generate_bulk_candidates(600)
        # Distinct totals
        for i, c in enumerate(candidates):
            c.total_score = 200.0 - i
            
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        ranks = [c.overall_rank for c in candidates]
        assert min(ranks) == 1
        assert max(ranks) == 600
        assert len(set(ranks)) == 600
        assert list(ranks) == list(range(1, 601))

    def test_final_merit_with_all_candidates_same_score(self):
        candidates = generate_bulk_candidates(600)
        # Same total, part b, and DOB
        for c in candidates:
            c.total_score = 100.0
            c.interview_score = 50.0 # Part B
            c.date_of_birth = "2005-01-01"
            
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # Tiebreak falls back to Applicant ID (which is sequential in our generator)
        # The generator made IDs like APP-2026-00001, 00002...
        # So they should be perfectly ordered 1 to 600
        ranks = [c.overall_rank for c in candidates]
        assert len(set(ranks)) == 600
        
        # Check that ID ordering matches rank ordering
        for i in range(len(candidates) - 1):
            assert candidates[i].applicant_id < candidates[i+1].applicant_id
