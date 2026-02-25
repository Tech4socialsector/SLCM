import frappe
import unittest
from slcm.admission.utils.institution import get_institution_settings, is_multi_campus_enabled

class TestInstitutionUtils(unittest.TestCase):
	def setUp(self):
		self.settings = frappe.get_single("Institution Settings")
		self.settings.enable_multi_campus = 0
		self.settings.save()

	def test_is_multi_campus_enabled(self):
		self.assertFalse(is_multi_campus_enabled())
		
		self.settings.enable_multi_campus = 1
		self.settings.save()
		self.assertTrue(is_multi_campus_enabled())

	def test_get_institution_settings(self):
		settings = get_institution_settings()
		self.assertEqual(settings.doctype, "Institution Settings")
