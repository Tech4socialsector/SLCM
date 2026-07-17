import pytest
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates, generate_candidate
from slcm.admission.doctype.merit_generation.merit_service import execute_advanced_allocation_logic

class TestReservationPolicy:
    def test_vertical_quota_exact_allocation(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Res 1", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        
        # 600 candidates, distributed across all verticals
        dist = {"General": 200, "SC": 100, "ST": 50, "OBC": 150, "EWS": 100}
        candidates = generate_bulk_candidates(600, vertical_distribution=dist)
        
        # Give everyone high scores so they all compete
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - (i * 0.1)
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda a, t, i: False)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # Check quotas match the policy defined in mock_policy
        assert len(getattr(doc, "general_list", [])) == 49
        assert len(getattr(doc, "sc_list", [])) == 18
        assert len(getattr(doc, "st_list", [])) == 9
        assert len(getattr(doc, "obc_list", [])) == 32
        assert len(getattr(doc, "ews_list", [])) == 12
        
        total_allocated = sum([
            len(getattr(doc, "general_list", [])),
            len(getattr(doc, "sc_list", [])),
            len(getattr(doc, "st_list", [])),
            len(getattr(doc, "obc_list", [])),
            len(getattr(doc, "ews_list", []))
        ])
        assert total_allocated == 120

    def test_merit_absorption_at_allocation_stage(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Res 2", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        
        # 10 SC candidates who score higher than everyone else
        candidates = generate_bulk_candidates(110, vertical_distribution={"General": 100, "SC": 10})
        for i, c in enumerate(candidates):
            if c.vertical_category == "SC":
                c.et_part_a_total_marks_scored = 200.0
            else:
                c.et_part_a_total_marks_scored = 100.0 - i
                
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda a, t, i: False)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # The 10 SC candidates should be absorbed into General
        general_list = getattr(doc, "general_list", [])
        sc_in_general = [c for c in general_list if c.get("actual_category") == "SC" or c.get("vertical_category") == "SC"]
        assert len(sc_in_general) == 10
        
        # SC list should be empty (since all SC candidates were absorbed into General, and there are no other SCs!)
        # Wait, the SC target is 18. Since there were only 10 SC candidates total and they all got General, 
        # the SC list will have 0.
        sc_list = getattr(doc, "sc_list", [])
        assert len(sc_list) == 0

    def test_compartmentalized_karnataka_general_minimum_12(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Res 3", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        candidates = generate_bulk_candidates(100, vertical_distribution={"General": 100})
        
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - i
            # Give Karnataka trait to lower ranking candidates (rank 50 to 80)
            if 50 <= i <= 80:
                c.horizontal_categories = "Karnataka"
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        def mock_has_trait(app_id, trait, is_shortlist=False):
            # mock look up
            for c in doc.merit_applicants:
                if c.applicant_id == app_id:
                    return trait in c.horizontal_categories
            return False
            
        monkeypatch.setattr(ms, "_has_trait", mock_has_trait)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # General quota is 49. Karnataka minimum is 25% of 49 = 12.
        general_list = getattr(doc, "general_list", [])
        assert len(general_list) == 49
        
        # Check how many have Karnataka trait in general list
        kar_in_general = [c for c in general_list if "Karnataka" in c.get("horizontal_categories", "")]
        assert len(kar_in_general) >= 12
        
        # Displacement should have occurred. The lowest ranked non-karnataka (ranks ~38-49) 
        # should have been displaced by the Karnataka candidates (ranks 50-61).
        
    def test_overall_horizontal_pwd_spans_verticals(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Res 4", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        
        dist = {"General": 100, "SC": 50}
        candidates = generate_bulk_candidates(150, vertical_distribution=dist)
        
        for i, c in enumerate(candidates):
            c.et_part_a_total_marks_scored = 100.0 - i
            # Give PWD to some low ranked candidates across verticals
            if 60 <= i <= 65: # 6 candidates
                c.horizontal_categories = "PWD"
                
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        
        def mock_has_trait(app_id, trait, is_shortlist=False):
            for c in doc.merit_applicants:
                if c.applicant_id == app_id:
                    return trait in c.horizontal_categories
            return False
            
        monkeypatch.setattr(ms, "_has_trait", mock_has_trait)
        
        execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        pwd_list = getattr(doc, "pwd_list", [])
        # Target for PWD is 6
        assert len(pwd_list) >= 6
