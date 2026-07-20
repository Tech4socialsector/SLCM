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

    def test_tiebreak_dob_older_wins(self):
        c1 = generate_candidate("APP-001", part_a=50, part_b=50, dob="2005-01-01") 
        c2 = generate_candidate("APP-002", part_a=50, part_b=50, dob="2004-01-01") 
        c3 = generate_candidate("APP-003", part_a=50, part_b=50, dob="2006-01-01") 
        
        c1.total_score = c2.total_score = c3.total_score = 100
        candidates = [c1, c2, c3]
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # Older DOB ranks better (2004 < 2005 < 2006)
        assert candidates[0].applicant_id == "APP-002"
        assert candidates[1].applicant_id == "APP-001"
        assert candidates[2].applicant_id == "APP-003"
        
    def test_tiebreak_dob_leap_year_handling(self):
        c1 = generate_candidate("APP-001", part_a=50, part_b=50, dob="2004-02-29") 
        c2 = generate_candidate("APP-002", part_a=50, part_b=50, dob="2004-03-01") 
        
        c1.total_score = c2.total_score = 100
        candidates = [c1, c2]
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # 2004-02-29 is older than 2004-03-01
        assert candidates[0].applicant_id == "APP-001"
        assert candidates[1].applicant_id == "APP-002"

    def test_tiebreak_applicant_id_when_dob_same(self):
        c1 = generate_candidate("APP-2026-00100", part_a=50, part_b=50, dob="2000-01-01")
        c2 = generate_candidate("APP-2026-00099", part_a=50, part_b=50, dob="2000-01-01")
        
        c1.total_score = c2.total_score = 100
        candidates = [c1, c2]
        
        _rank_applicants(candidates, use_advanced_ranking=True, processing_stage="Final Allotment Ranking")
        
        # ID 00099 ranks higher than 00100
        assert candidates[0].applicant_id == "APP-2026-00099"
        
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
        # 1. c5 (highest total)
        # 2. c4 (highest part B among total 90)
        # 3. c3 (older dob among total 90, part B 40)
        # 4. c2 (lower ID among total 90, part B 40, same dob)
        # 5. c1
        assert candidates[0].applicant_id == "APP-06"
        assert candidates[1].applicant_id == "APP-07"
        assert candidates[2].applicant_id == "APP-08"
        assert candidates[3].applicant_id == "APP-09"
        assert candidates[4].applicant_id == "APP-10"
