import pytest
from slcm.tests.merit_system.fixtures.candidate_fixtures import generate_candidate
from slcm.admission.doctype.merit_generation.merit_service import _rank_applicants

class TestTiebreakLogic:
    def test_tiebreak_part_b_when_total_same(self):
        c1 = generate_candidate("APP-001", part_a=55, part_b=45) # Total 100
        c2 = generate_candidate("APP-002", part_a=60, part_b=40) # Total 100
        c1.total_score = 100
        c2.total_score = 100
        
        candidates = [c1, c2]
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # c1 has higher Part B (45 > 40), so c1 ranks higher
        assert candidates[0].applicant_id == "APP-001"
        assert candidates[0].overall_rank == 1
        assert candidates[1].overall_rank == 2

    def test_same_rank_when_total_and_part_b_same(self):
        c1 = generate_candidate("APP-001", part_a=50, part_b=50, dob="2005-01-01") 
        c2 = generate_candidate("APP-002", part_a=50, part_b=50, dob="2004-01-01") 
        c3 = generate_candidate("APP-003", part_a=50, part_b=40, dob="2006-01-01") 
        
        c1.total_score = c2.total_score = 100
        c3.total_score = 90
        candidates = [c1, c2, c3]
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # c1 and c2 have same Total Score (100) and same Part B (50), so they get same rank 1
        # c3 has lower score, so c3 gets rank 3
        ranks = {c.applicant_id: c.overall_rank for c in candidates}
        assert ranks["APP-001"] == 1
        assert ranks["APP-002"] == 1
        assert ranks["APP-003"] == 3
        
    def test_tiebreak_precedence_total_before_partb(self):
        c1 = generate_candidate("APP-001", part_a=60.5, part_b=40) # Total 100.5
        c2 = generate_candidate("APP-002", part_a=50.4, part_b=50) # Total 100.4
        
        c1.total_score = 100.5
        c2.total_score = 100.4
        candidates = [c1, c2]
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # Total overrides Part B
        assert candidates[0].applicant_id == "APP-001"
        
    def test_full_tiebreak_chain(self):
        c1 = generate_candidate("APP-10", part_a=50, part_b=40, dob="2000-01-01")
        c2 = generate_candidate("APP-09", part_a=50, part_b=40, dob="2000-01-01")
        c3 = generate_candidate("APP-08", part_a=50, part_b=40, dob="1999-01-01")
        c4 = generate_candidate("APP-07", part_a=50, part_b=45, dob="2000-01-01")
        c5 = generate_candidate("APP-06", part_a=55, part_b=45, dob="2000-01-01")
        
        for c in [c1, c2, c3, c4]: c.total_score = 90
        c5.total_score = 100
        
        candidates = [c1, c2, c3, c4, c5]
        import random
        random.shuffle(candidates)
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # Order should be:
        # 1. c5 (highest total: 100) -> Rank 1
        # 2. c4 (total: 90, part B: 45) -> Rank 2
        # 3. c1, c2, c3 (total: 90, part B: 40) -> Tied Rank 3
        ranks = {c.applicant_id: c.overall_rank for c in candidates}
        assert ranks["APP-06"] == 1
        assert ranks["APP-07"] == 2
        assert ranks["APP-08"] == 3
        assert ranks["APP-09"] == 3
        assert ranks["APP-10"] == 3

    def test_no_dob_or_applicant_id_tiebreak(self):
        # Candidates with different DOBs and different Applicant IDs but identical scores get exact same rank
        c1 = generate_candidate("APP-999", part_a=50, part_b=50, dob="2005-12-31")
        c2 = generate_candidate("APP-001", part_a=50, part_b=50, dob="1990-01-01")
        c1.total_score = 100
        c2.total_score = 100

        candidates = [c1, c2]
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")

        # Both candidates must receive rank 1
        assert candidates[0].overall_rank == 1
        assert candidates[1].overall_rank == 1

