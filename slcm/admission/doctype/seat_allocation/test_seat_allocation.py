# Copyright (c) 2026, TFSS and Contributors
# See license.txt

import frappe
import unittest


class TestSeatAllocation(unittest.TestCase):
    def test_seat_allocation_sorting(self):
        doc_names = frappe.get_all("Seat Allocation", order_by="creation desc", limit=1)
        if not doc_names:
            self.skipTest("No Seat Allocation records found in the database.")
            
        doc_name = doc_names[0].name
        doc = frappe.get_doc("Seat Allocation", doc_name)
        
        if not doc.selection_applicant:
            self.skipTest(f"Seat Allocation {doc_name} has no selection applicants to test.")
            
        # Reset overall_rank/idx of selection applicants
        # to ensure it gets re-allocated and re-sorted
        for r in doc.selection_applicant:
            r.idx = 999
            
        doc.status = "Draft"
        doc.allocate_seats()
        doc.save()
        doc.reload()
        
        # Check that top rank 1 candidates are sorted as:
        # 1. Suresh Das
        # 2. Vikram Joshi
        # 3. Anjali Reddy
        rank_1_candidates = [
            (r.candidate_name, r.idx)
            for r in doc.selection_applicant
            if r.overall_rank == 1
        ]
        
        self.assertEqual(len(rank_1_candidates), 3)
        self.assertEqual(rank_1_candidates[0][0], "Suresh Das")
        self.assertEqual(rank_1_candidates[1][0], "Vikram Joshi")
        self.assertEqual(rank_1_candidates[2][0], "Anjali Reddy")
