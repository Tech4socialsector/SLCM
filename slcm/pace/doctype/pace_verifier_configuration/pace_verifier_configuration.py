import frappe
from frappe import _
from frappe.model.document import Document

class PACEVerifierConfiguration(Document):
    def validate(self):
        self.validate_duplicate_verifiers()

    def validate_duplicate_verifiers(self):
        seen_programmes = {}
        for row in self.verifiers:
            if not row.user or not row.programme:
                continue
            
            # Check for duplicates within this child table
            if row.programme in seen_programmes:
                frappe.throw(
                    _("Row #{0}: Programme '{1}' is already assigned to verifier '{2}' in this configuration.").format(
                        row.idx, row.programme, seen_programmes[row.programme]
                    )
                )
            seen_programmes[row.programme] = row.user
            
            # Check for duplicates across other configurations in the database for the same Academic Year
            exists = frappe.db.sql("""
                SELECT pvc.name, pvm.user
                FROM `tabPACE Verifier Mapping` pvm
                JOIN `tabPACE Verifier Configuration` pvc ON pvm.parent = pvc.name
                WHERE pvc.academic_year = %s
                  AND pvm.programme = %s
                  AND pvc.name != %s
            """, (self.academic_year, row.programme, self.name or ""))
            
            if exists:
                frappe.throw(
                    _("Row #{0}: Programme '{1}' is already assigned to verifier '{2}' in another configuration '{3}' for Academic Year {4}.").format(
                        row.idx, row.programme, exists[0][1], exists[0][0], self.academic_year
                    )
                )

