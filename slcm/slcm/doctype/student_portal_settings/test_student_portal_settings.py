# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from slcm.slcm.doctype.student_portal_settings.student_portal_settings import (
    get_student_portal_settings,
    _hex_to_rgba,
    _darken_hex,
    _is_valid_hex,
)


class TestStudentPortalSettings(FrappeTestCase):
    def test_defaults_returned_when_not_configured(self):
        settings = get_student_portal_settings()
        self.assertEqual(settings["primary_color"], "#1a3c6e")
        self.assertEqual(settings["sidebar_position"], "Left")
        self.assertIn("body_classes", settings)

    def test_hex_to_rgba(self):
        result = _hex_to_rgba("#1a3c6e", 0.1)
        self.assertEqual(result, "rgba(26, 60, 110, 0.1)")

    def test_darken_hex(self):
        result = _darken_hex("#1a3c6e", 0.82)
        self.assertTrue(result.startswith("#"))
        self.assertEqual(len(result), 7)

    def test_is_valid_hex(self):
        self.assertTrue(_is_valid_hex("#1a3c6e"))
        self.assertTrue(_is_valid_hex("#fff"))
        self.assertFalse(_is_valid_hex("red"))
        self.assertFalse(_is_valid_hex("1a3c6e"))

    def test_body_classes_right_sidebar(self):
        doc = frappe.get_single("Student Portal Settings")
        doc.sidebar_position = "Right"
        doc.font_size = "Large"
        doc.corner_style = "Pill"
        doc.layout_density = "Compact"
        doc.sidebar_width = "Wide"
        doc.save(ignore_permissions=True)

        settings = get_student_portal_settings()
        self.assertIn("sp-right-sidebar", settings["body_classes"])
        self.assertIn("sp-font-lg", settings["body_classes"])
        self.assertIn("sp-corners-pill", settings["body_classes"])
        self.assertIn("sp-compact", settings["body_classes"])
        self.assertIn("sp-sidebar-wide", settings["body_classes"])

        # Reset
        doc.sidebar_position = "Left"
        doc.font_size = "Normal"
        doc.corner_style = "Normal"
        doc.layout_density = "Normal"
        doc.sidebar_width = "Normal"
        doc.save(ignore_permissions=True)
