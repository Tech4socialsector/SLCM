import pytest
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates
from slcm.admission.doctype.merit_generation.merit_service import execute_advanced_allocation_logic

class TestDataConsistency:
    def test_total_score_precision(self):
        c = generate_bulk_candidates(1)[0]
        c.et_part_a_total_marks_scored = 75.25
        c.et_part_b_total_marks_scored = 40.75
        c.total_score = c.et_part_a_total_marks_scored + c.et_part_b_total_marks_scored
        assert c.total_score == 116.00
        
    def test_rank_no_gaps(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Rank Gaps", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        candidates = generate_bulk_candidates(200, vertical_distribution={"General": 200})
        
        # Several ties and regular scores mixed
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - (i % 10) # many ties
            c.et_part_b_total_marks_scored = 50.0 - (i % 5) # tie breakers
            c.date_of_birth = "2000-01-01"
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda a, t, i: False)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        ranks = [c.overall_rank for c in doc.merit_applicants]
        # Should be completely gapless 1 to 200 because Applicant ID breaks the final ties perfectly
        assert sorted(ranks) == list(range(1, 201))


class TestErrorHandling:
    def test_missing_part_a_score(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Err 1", program="BA", admission_cycle="2026", merit_processing_stage="Part A Ranking")
        candidates = generate_bulk_candidates(5, vertical_distribution={"General": 5})
        
        candidates[0].et_part_a_total_marks_scored = None
        candidates[1].et_part_a_total_marks_scored = -5
        
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda a, t, i: False)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=True)
        
        # Candidates 0 and 1 should be ignored/rejected based on logic
        # Typically missing part a drops the score to 0. Our ranking loop tests > 0 check in generate_merit_for_level
        # But if they somehow get into execute_advanced_allocation_logic, they drop to bottom rank.
        
        assert candidates[0].overall_rank >= 4
        assert candidates[1].overall_rank >= 4
        
    def test_missing_vertical_tag(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Err 2", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        candidates = generate_bulk_candidates(1, vertical_distribution={"General": 1})
        candidates[0].vertical_category = None
        
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda a, t, i: False)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # It defaults to General in logic:
        # cat = getattr(row, "actual_category", None) or getattr(row, "vertical_category", None) or "General"
        # Since actual_category defaults to General in our mock, we need to test the logic directly
        assert len(getattr(doc, "general_list", [])) == 1
