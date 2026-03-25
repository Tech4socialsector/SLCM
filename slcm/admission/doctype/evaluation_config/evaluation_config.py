import frappe
from frappe.model.document import Document

class EvaluationConfig(Document):

    def validate(self):
        if self.scoring_components:
            total_weight = sum(c.weightage for c in self.scoring_components if c.weightage)
            if abs(total_weight - 100.0) > 0.01:
                frappe.throw(
                    f"Total weightage of scoring components must equal 100%. "
                    f"Current total: {total_weight}%"
                )
            names = [c.component_name for c in self.scoring_components]
            if len(names) != len(set(names)):
                frappe.throw("Scoring component names must be unique.")
        if self.min_evaluators and self.max_evaluators:
            if self.min_evaluators > self.max_evaluators:
                frappe.throw("Min evaluators cannot exceed max evaluators.")
        if self.auto_shortlist_cutoff and self.scoring_components:
            max_possible = sum(c.max_score for c in self.scoring_components if c.max_score)
            if self.auto_shortlist_cutoff > max_possible:
                frappe.throw(
                    f"Auto-shortlist cutoff ({self.auto_shortlist_cutoff}) "
                    f"cannot exceed maximum possible score ({max_possible})."
                )
