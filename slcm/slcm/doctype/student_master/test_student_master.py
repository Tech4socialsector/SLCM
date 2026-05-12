# Copyright (c) 2025, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from slcm.slcm.doctype.student_master.student_master import (
    VALID_TRANSITIONS,
    TRANSITION_ROLES,
    _validate_transition_requirements,
)


class TestStudentMaster(FrappeTestCase):
    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def test_valid_transitions_are_complete(self):
        """Every state in VALID_TRANSITIONS must also appear as a key or value."""
        all_states = set(VALID_TRANSITIONS.keys())
        for nexts in VALID_TRANSITIONS.values():
            all_states.update(nexts)
        # Every state reachable must have a transition defined or be a terminal
        for state in all_states:
            if state not in ("Completed",):
                self.assertIn(state, VALID_TRANSITIONS, f"{state} has no outgoing transition")

    def test_no_duplicate_valid_transition_dicts(self):
        """VALID_TRANSITIONS must be a single module-level constant, not duplicated."""
        import inspect, slcm.slcm.doctype.student_master.student_master as mod
        source = inspect.getsource(mod)
        count = source.count("VALID_TRANSITIONS = {")
        self.assertEqual(count, 1, "VALID_TRANSITIONS should be defined exactly once")

    def test_transition_roles_cover_all_target_states(self):
        """Every forward transition target should have a role mapping."""
        for _from, tos in VALID_TRANSITIONS.items():
            for to in tos:
                if to not in ("Selected",):   # Initial state, no role gate
                    self.assertIn(
                        to, TRANSITION_ROLES,
                        f"No TRANSITION_ROLES entry for target state '{to}'"
                    )

    # ------------------------------------------------------------------
    # validate_transition_requirements
    # ------------------------------------------------------------------
    def test_completed_requires_id_card(self):
        student = frappe._dict({
            "aadhaar_card": "/files/aadhar.pdf",
            "aadhaar_verified": 1,
            "pan_card": "/files/pan.pdf",
            "pan_verified": 1,
            "offer_letter": "/files/offer.pdf",
            "offer_letter_verified": 1,
            "student_declaration": "/files/decl.pdf",
            "student_declaration_verified": 1,
            "id_card_issued": 0,          # <-- missing
            "official_email_id": "s@institution.edu",
        })
        with self.assertRaises(frappe.exceptions.ValidationError):
            _validate_transition_requirements(student, "Completed")

    def test_completed_requires_official_email(self):
        student = frappe._dict({
            "aadhaar_card": "/files/aadhar.pdf",
            "aadhaar_verified": 1,
            "pan_card": "/files/pan.pdf",
            "pan_verified": 1,
            "offer_letter": "/files/offer.pdf",
            "offer_letter_verified": 1,
            "student_declaration": "/files/decl.pdf",
            "student_declaration_verified": 1,
            "id_card_issued": 1,
            "official_email_id": "",       # <-- missing
        })
        with self.assertRaises(frappe.exceptions.ValidationError):
            _validate_transition_requirements(student, "Completed")

    def test_pending_fino_requires_documents(self):
        student = frappe._dict({
            "aadhaar_card": "",
            "pan_card": "",
            "std_x_marksheet": "",
            "passport_size_photo": "",
        })
        with self.assertRaises(frappe.exceptions.ValidationError):
            _validate_transition_requirements(student, "Pending FINO")
