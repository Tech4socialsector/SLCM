import pytest
import time
from slcm.tests.merit_system.fixtures.candidate_fixtures import MockDoc, generate_bulk_candidates
import slcm.admission.doctype.merit_generation.merit_service as ms
from slcm.admission.doctype.merit_generation.merit_service import execute_part_a_shortlisting

class TestPerformanceLoad:
    def test_shortlisting_performance_2500_candidates(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Perf 1", program="BA", admission_cycle="2026", merit_processing_stage="Part A Ranking")
        candidates = generate_bulk_candidates(2500, vertical_distribution={"General": 1250, "SC": 500, "ST": 250, "OBC": 500})
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        start_time = time.time()
        execute_part_a_shortlisting(doc)
        end_time = time.time()
        
        # Benchmark: Completes in < 5 seconds
        duration = end_time - start_time
        assert duration < 5.0
        
    def test_seat_allocation_performance_600_candidates(self, mock_policy, monkeypatch):
        doc = MockDoc("Merit List", "Test Perf 2", program="BA", admission_cycle="2026", merit_processing_stage="Final Allotment Ranking")
        candidates = generate_bulk_candidates(600, vertical_distribution={"General": 300, "SC": 100, "ST": 50, "OBC": 150})
        doc.merit_applicants = candidates
        import slcm.admission.doctype.merit_generation.merit_service as ms
        monkeypatch.setattr(ms, "_has_trait", lambda *args, **kwargs: False)
        
        start_time = time.time()
        ms.execute_advanced_allocation_logic(doc, is_shortlist_allocation=False)
        end_time = time.time()
        
        # Benchmark: Completes in < 1 second
        duration = end_time - start_time
        assert duration < 1.0
