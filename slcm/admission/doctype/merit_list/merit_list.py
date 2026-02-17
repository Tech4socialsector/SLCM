import frappe
from frappe.model.document import Document

class MeritList(Document):

    def autoname(self):
        if not self.admission_cycle or not self.campus:
            frappe.throw("Admission Cycle and Campus are required for naming.")

        cycle = self.admission_cycle.replace(" ", "").upper()
        campus = self.campus.replace(" ", "").upper()

        self.name = f"ML-{cycle}-{campus}"
