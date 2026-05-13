# hooks.py → add this to override / extend
# But better to put in custom app → doctype/entrance_test_generation/entrance_test_generation.py

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate, now

class EntranceTestGeneration(Document):

    def before_save(self):
        if not self.generation_code:
            # optional: auto generate code like ETG-YY-#### 
            yr = getdate().strftime("%y")
            self.generation_code = frappe.generate_hash("EntranceTestGeneration", 8).upper()[:8]
            self.generation_code = f"ETG-{yr}-{self.generation_code}"



    @frappe.whitelist()
    def generate_test_list(self):
        if self.status not in ["Draft", "In Progress", "Failed"]: # Included Failed as well
            frappe.throw("Document must be in Draft, In Progress or Failed to generate test list")


        # Ensure schema is synced (updatedb is not a standard Frappe method)
        # frappe.db.updatedb("Entrance Test List")
        # frappe.db.updatedb("Entrance Test Applicant")

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
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview,
                COALESCE(ee.exempts_interview, 0) AS exempts_interview
            FROM `tabApplicant` app
            LEFT JOIN `tabEligibility Evaluation` ee ON ee.applicant_name = app.name
            INNER JOIN `tabProgram` p ON p.name = app.program
            WHERE 
                app.academic_year = %(academic_year)s
                AND app.campus = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                AND app.program_level = %(program_level)s
                AND IFNULL(app.center_filled, 0) = 1
                AND (ee.exempts_entrance_test IS NULL OR ee.exempts_entrance_test = 0)
                AND app.name NOT IN (SELECT applicant_id FROM `tabEntrance Test Applicant`)
                AND app.name NOT IN (SELECT applicant FROM `tabEntrance Test Seat Allocation`)
                AND app.application_status != 'Rejected'
                AND p.entrance_test = 1
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
            
            msg = f"""
                <div style="padding: 15px; background-color: #fffaf0; border-left: 5px solid #ff8c00; border-radius: 8px;">
                    <h3 style="margin-top: 0; color: #d35400; font-size: 16px;">
                        ⚠️ No Eligible Applicants Found
                    </h3>
                    <p style="font-size: 14px; color: #333; margin-bottom: 12px;">
                        We couldn't find any applicants matching your selected criteria who are currently eligible for the Entrance Test list generation.
                    </p>
                    <div style="background: white; padding: 10px; border: 1px solid #ffe0b2; border-radius: 6px; margin-bottom: 15px;">
                        <table style="width: 100%; font-size: 13px; color: #555; border-collapse: collapse;">
                            <tr><td style="padding: 3px 0; font-weight: 600; width: 35%;">Year:</td><td>{self.academic_year}</td></tr>
                            <tr><td style="padding: 3px 0; font-weight: 600;">Campus:</td><td>{self.campus}</td></tr>
                            <tr><td style="padding: 3px 0; font-weight: 600;">Cycle:</td><td>{self.admission_cycle}</td></tr>
                            <tr><td style="padding: 3px 0; font-weight: 600;">Level:</td><td>{self.program_level}</td></tr>
                        </table>
                    </div>
                    <div style="font-size: 12.5px; line-height: 1.5; color: #666;">
                        <strong style="color: #444;">Diagnostic Summary:</strong><br>
                        The system identified <b>{count_total} total applicants</b> for this Campus and Cycle. However, none were selected because they may be:
                        <ul style="margin-top: 5px; padding-left: 18px;">
                            <li>Assigned to a different Program Level</li>
                            <li>Already included in an existing Entrance Test List</li>
                            <li>Marked as 'Exempt' from the Entrance Test</li>
                            <li>Rejected or in an ineligible application status</li>
                        </ul>
                    </div>
                </div>
            """
            frappe.throw(msg, title=_("Generation Failed"))

        test_list = frappe.get_doc({
            "doctype": "Entrance Test List",
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level,
            "generated_on": now(),
            "status": "Generated",
            "entrance_test_applicant": []
        })

        for app in applicants:
            test_list.append("entrance_test_applicant", {
                "applicant_id": app.applicant_id,
                "candidate_name": app.candidate_name or "Unknown",
                "program": app.program,
                "program_level": app.program_level,
                "email": app.email,
                "gender": app.gender,
                "entrance_test": app.entrance_test,
                "intereview": app.intereview,
                "exempts_entrance_test": 0,  # These students are NOT exempt from entrance test
                "exempts_interview": app.get("exempts_interview") or 0,
            })

        test_list.insert(ignore_permissions=True)

        self.db_set("status", "Completed")
        self.db_set("generated_on", now())
        self.db_set("generated_by", frappe.session.user)

        return test_list.name