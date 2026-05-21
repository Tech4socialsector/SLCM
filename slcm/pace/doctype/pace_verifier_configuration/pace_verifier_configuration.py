import frappe
from frappe import _
from frappe.model.document import Document

class PACEVerifierConfiguration(Document):
    def validate(self):
        self.validate_duplicate_verifiers()

    def validate_duplicate_verifiers(self):
        seen = set()
        for row in self.verifiers:
            if not row.user or not row.programme:
                continue
            
            # Check for duplicates within this child table
            key = (row.user, row.programme)
            if key in seen:
                frappe.throw(
                    _("Row #{0}: Verifier '{1}' is already assigned to programme '{2}' in this configuration.").format(
                        row.idx, row.user, row.programme
                    )
                )
            seen.add(key)
            
            # Check for duplicates across other configurations in the database for the same Academic Year
            exists = frappe.db.sql("""
                SELECT pvc.name 
                FROM `tabPACE Verifier Mapping` pvm
                JOIN `tabPACE Verifier Configuration` pvc ON pvm.parent = pvc.name
                WHERE pvc.academic_year = %s
                  AND pvm.user = %s
                  AND pvm.programme = %s
                  AND pvc.name != %s
            """, (self.academic_year, row.user, row.programme, self.name or ""))
            
            if exists:
                frappe.throw(
                    _("Row #{0}: Verifier '{1}' is already assigned to programme '{2}' in another configuration '{3}' for Academic Year {4}.").format(
                        row.idx, row.user, row.programme, exists[0][0], self.academic_year
                    )
                )
