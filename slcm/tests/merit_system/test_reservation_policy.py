import pytest
import frappe
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates, generate_candidate
import slcm.admission.doctype.merit_generation.merit_service as ms

class TestReservationPolicy:
    def test_vertical_quota_exact_allocation(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Res 1", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        
        # 600 candidates, distributed across all verticals
        dist = {"General": 200, "SC": 100, "ST": 50, "OBC-NCL": 150, "EWS": 100}
        candidates = generate_bulk_candidates(600, vertical_distribution=dist)
        
        # Give everyone high scores so they all compete
        for i, c in enumerate(candidates):
            c.total_score = 100.0 - (i * 0.1)
            
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
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
                c.total_score = 200.0
            else:
                c.total_score = 100.0 - i
                
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        
        # The 10 SC candidates should be absorbed into General
        general_list = getattr(doc, "general_list", [])
        sc_in_general = [c for c in general_list if c.get("actual_category") == "SC" or c.get("vertical_category") == "SC"]
        assert len(sc_in_general) == 10
        
        # SC list should be empty (since all SC candidates were absorbed into General, and there are no other SCs!)
        # Wait, the SC target is 18. Since there were only 10 SC candidates total and they all got General, 
        # the SC list will have 0.
        sc_list = getattr(doc, "sc_list", [])
        assert len(sc_list) == 0

    @pytest.mark.skip(reason="Displacement logic requires full DB mocking for horizontal/compartmental traits")
    def test_compartmentalized_karnataka_general_minimum_12(self, mock_policy, monkeypatch):
        pass
        
    @pytest.mark.skip(reason="Displacement logic requires full DB mocking for horizontal/compartmental traits")
    def test_overall_horizontal_pwd_spans_verticals(self, mock_policy, monkeypatch):
        pass
