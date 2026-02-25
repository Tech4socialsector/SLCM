import frappe
import unittest

class TestEvaluationConfig(unittest.TestCase):
    def test_weightage_must_equal_100(self):
        doc = frappe.new_doc("Evaluation Config")
        doc.config_name = "Test Eval"
        doc.evaluation_type = "Panel Interview"
        doc.append("scoring_components", {"component_name": "Communication", "max_score": 50, "weightage": 60})
        doc.append("scoring_components", {"component_name": "Knowledge", "max_score": 50, "weightage": 60})
        self.assertRaises(frappe.ValidationError, doc.validate)
