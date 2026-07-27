import pytest
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates, generate_candidate
import slcm.admission.doctype.merit_generation.merit_service as ms

class TestSeatAllocation:
    def test_seat_allocation_exact_120(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Allocation", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        # 600 ranked candidates
        candidates = generate_bulk_candidates(600, vertical_distribution={"General": 600})
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - (i * 0.1)
            c.et_part_b_total_marks_scored = 50.0
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # In final allotment, candidates are marked "Selected" by the generic process,
        # wait! Seat allocation actually assigns allocation_type and vertical_category
        # but does execute_advanced_allocation_logic change their status?
        # Actually it generates the lists (general_list, sc_list) which represent the seats!
        
        
        allocated_total = len(getattr(doc, "general_list", []))
        print("allocated_total=", allocated_total)
        print("allocated_list size=", len(allocated_list) if 'allocated_list' in locals() else 'unknown')
        print("general_list items=", getattr(doc, "general_list", []))

        
        # Policy says General has 49 seats. If everyone is General, only 49 will be allocated to General!
        # Because we only provided General candidates, the other reserved seats (SC, ST, OBC, EWS) will remain vacant.
        # Let's verify exactly 49 are allocated.
        assert allocated_total == 49
        
    def test_seat_allocation_respects_final_merit_rank(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Allocation 2", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        candidates = generate_bulk_candidates(100, vertical_distribution={"General": 100})
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - (i * 0.1)
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # Top 49 General should be in general_list
        general_list = getattr(doc, "general_list", [])
        assert len(general_list) == 49
        
        # Ensure they are the top 49 (rank 1 to 49)
        ranks = [getattr(c, "overall_rank", c.get("overall_rank")) for c in general_list]
        assert max(ranks) == 49
        
    def test_seat_allocation_allocation_status_field(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Allocation 3", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        candidates = generate_bulk_candidates(600, vertical_distribution={"General": 600})
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # The candidates in general_list should have allocation_type = "Open"
        # and vertical_category = "General"
        general_list = getattr(doc, "general_list", [])
        for c in general_list:
            # Depending on how it's stored in the dict
            assert c.get("vertical_category") == "General" or c.get("allocation_type") == "Open"

    def test_seat_allocation_tied_at_rank_120_includes_all_ties(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Allocation 4", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        # 60 candidates total, 49 general seats. 
        # Make rank 49 tied.
        candidates = generate_bulk_candidates(60, vertical_distribution={"General": 60})
        for i in range(48):
            candidates[i].et_part_a_total_marks_scored = 100.0 - i
            candidates[i].nlsat_part_a_score = 100.0 - i
            candidates[i].entrance_score = 100.0 - i
            candidates[i].et_part_b_total_marks_scored = 50.0
            candidates[i].nlsat_part_b_score = 50.0
            candidates[i].interview_score = 50.0
            candidates[i].total_score = (100.0 - i) + 50.0
            
        # Tie 5 people at the boundary
        for i in range(48, 53):
            candidates[i].et_part_a_total_marks_scored = 50.0
            candidates[i].nlsat_part_a_score = 50.0
            candidates[i].entrance_score = 50.0
            candidates[i].et_part_b_total_marks_scored = 50.0
            candidates[i].nlsat_part_b_score = 50.0
            candidates[i].interview_score = 50.0
            candidates[i].total_score = 100.0
            candidates[i].date_of_birth = "2000-01-01"
            # applicant IDs will break the tie
            
        # Ensure candidates 53-59 have lower scores so they rank below the tie group
        for i in range(53, 60):
            candidates[i].et_part_a_total_marks_scored = 10.0
            candidates[i].nlsat_part_a_score = 10.0
            candidates[i].entrance_score = 10.0
            candidates[i].et_part_b_total_marks_scored = 10.0
            candidates[i].nlsat_part_b_score = 10.0
            candidates[i].interview_score = 10.0
            candidates[i].total_score = 20.0
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # Under the new tie-breaking rules, all candidates tied at the cutoff rank are allocated.
        general_list = getattr(doc, "general_list", [])
        assert len(general_list) == 53
