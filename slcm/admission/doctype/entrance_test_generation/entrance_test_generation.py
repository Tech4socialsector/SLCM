# hooks.py → add this to override / extend
# But better to put in custom app → doctype/entrance_test_generation/entrance_test_generation.py

import frappe
from frappe.model.document import Document

class EntranceTestGeneration(Document):

    def before_save(self):
        if not self.generation_code:
            # optional: auto generate code like ETG-YY-#### 
            from frappe.utils import now_datetime, getdate
            yr = getdate().strftime("%y")
            self.generation_code = frappe.generate_hash("EntranceTestGeneration", 8).upper()[:8]
            self.generation_code = f"ETG-{yr}-{self.generation_code}"

   # in entrance_test_generation.py

    @frappe.whitelist()
    def generate_test_list(self):
        if self.status not in ["Draft", "In Progress", "Failed"]: # Included Failed as well
            frappe.throw("Document must be in Draft, In Progress or Failed to generate test list")

        # Force schema sync for Entrance Test List and child table
        frappe.db.updatedb("Entrance Test List")
        frappe.db.updatedb("Entrance Test Applicant")

        # 1. Fetch Applicants based on Year, Campus, Cycle, and Level
        # 2. Filter out those who are EXEMPT from the entrance test (ee.exempts_entrance_test = 1)
        
        # User Logic:
        # National Test Passed | Exempts Entrance Test | Fetch Student?
        # No                   | -                    | ✅ YES
        # Yes                  | Unchecked            | ✅ YES
        # Yes                  | Checked              | ❌ NO
        
        applicants = frappe.db.sql("""
            SELECT 
                app.name as applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.reservation_category,
                app.program,
                app.program_level
            FROM `tabApplicant` app
            LEFT JOIN `tabEligibility Evaluation` ee ON ee.applicant_name = app.name
            WHERE 
                app.academic_year = %(academic_year)s
                AND app.campus = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                AND app.program_level = %(program_level)s
                AND (ee.exempts_entrance_test IS NULL OR ee.exempts_entrance_test = 0)
                AND app.application_status != 'Rejected'
        """, {
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level
        }, as_dict=True)

        if not applicants:
            self.db_set("status", "Failed")
            # Diagnostic for user:
            count_total = frappe.db.count("Applicant", {
                "academic_year": self.academic_year,
                "campus": self.campus,
                "admission_cycle": self.admission_cycle
            })
            
            frappe.throw(
                f"No eligible applicants found for the selected criteria.<br><br>"
                f"<b>Year:</b> {self.academic_year}<br>"
                f"<b>Campus:</b> {self.campus}<br>"
                f"<b>Cycle:</b> {self.admission_cycle}<br>"
                f"<b>Level:</b> {self.program_level}<br><br>"
                f"DIAGNOSTIC: Found {count_total} total applicants for this Cycle/Campus/Year, "
                "but none match the Program Level or they are all exempt/rejected."
            )

        # Create Entrance Test List
        test_list = frappe.get_doc({
            "doctype": "Entrance Test List",
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level,
            "generated_on": frappe.utils.now(),
            "status": "Generated",
            "entrance_test_applicant": []
        })

        for app in applicants:
            test_list.append("entrance_test_applicant", {
                "applicant_id": app.applicant_id,
                "candidate_name": app.candidate_name or "Unknown",
                "program": app.program,
                "program_level": app.program_level,
                "reservation_category": app.reservation_category,
                "email": app.email,
                "gender": app.gender,
            })

        test_list.insert(ignore_permissions=True)

        self.db_set({
            "status": "Completed",
            "generated_on": frappe.utils.now(),
            "generated_by": frappe.session.user
        })

        frappe.msgprint(
            f"<b>Success!</b> Created Entrance Test List with {len(applicants)} applicants.<br>"
            f"<a href='/app/entrance-test-list/{test_list.name}'>{test_list.name}</a>",
            title="Test List Generated",
            indicator="green"
        )

        return test_list.name