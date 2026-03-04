# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now


class EligibilityResultConfiguration(Document):

    def before_save(self):
        if not self.configuration_code:
            yr = getdate().strftime("%y")
            code = frappe.generate_hash("EligibilityResultConfiguration", 8).upper()[:8]
            self.configuration_code = f"ERC-{yr}-{code}"

    @frappe.whitelist()
    def generate_result(self):
        """
        Generates Eligibility Result records from:
        1. Interview Seat Allocation (interview_result_status = 'Pass')
        2. Applicant (dual exemption: entrance test & interview)
        
        Also enriches each record with academic marks from the Applicant DocType:
        hsc_percentage, ug_cgpa, pg_cgpa, entrance_percentage, interview_percentage
        """
        if self.status not in ["Draft", "In Progress", "Failed"]:
            frappe.throw("Document must be in Draft, In Progress, or Failed to generate results.")

        # ─── Source 1: Interview Passers ──────────────────────────────────────
        passed_interviewees = frappe.db.sql("""
            SELECT
                itsa.applicant AS applicant_id,
                itsa.candidate_name,
                itsa.email,
                itsa.gender,
                itsa.reservation_category,
                itsa.program,
                itsa.program_level,
                itsa.academic_year,
                itsa.admission_cycle,
                itsa.campus,
                itsa.entrance_test_score,
                itsa.interview_score
            FROM `tabInterview Seat Allocation` itsa
            WHERE
                itsa.academic_year = %(academic_year)s
                AND itsa.campus = %(campus)s
                AND itsa.admission_cycle = %(admission_cycle)s
                AND itsa.program_level = %(program_level)s
                AND itsa.interview_result_status = 'Pass'
        """, {
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level
        }, as_dict=True)

        # ─── Source 2: Dual Exempted Applicants ───────────────────────────────
        exempted_applicants = frappe.db.sql("""
            SELECT
                app.name AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.reservation_category,
                app.program,
                app.program_level,
                app.academic_year,
                app.admission_cycle,
                app.campus
            FROM `tabApplicant` app
            INNER JOIN `tabEligibility Evaluation` ee ON ee.applicant_name = app.name
            WHERE
                app.academic_year = %(academic_year)s
                AND app.campus = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                AND app.program_level = %(program_level)s
                AND ee.exempts_entrance_test = 1
                AND ee.exempts_interview = 1
                AND app.application_status != 'Rejected'
        """, {
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level
        }, as_dict=True)

        def get_applicant_marks(applicant_id):
            """Fetch academic mark fields from Applicant DocType."""
            return frappe.db.get_value(
                "Applicant",
                applicant_id,
                ["hsc_percentage", "ug_cgpa", "pg_cgpa"],
                as_dict=True
            ) or {}

        def compute_percentage(score, max_score=100):
            """Convert raw score to percentage with safe fallback."""
            try:
                return round((float(score or 0) / float(max_score or 100)) * 100, 4)
            except Exception:
                return 0.0

        count = 0

        def upsert_result(data, source_type):
            nonlocal count
            existing = frappe.db.get_value("Eligibility Result", {"applicant_id": data.applicant_id}, "name")
            if existing:
                res = frappe.get_doc("Eligibility Result", existing)
            else:
                res = frappe.new_doc("Eligibility Result")
                res.applicant_id = data.applicant_id

            # Fetch academic marks from Applicant DocType
            marks = get_applicant_marks(data.applicant_id)

            res.candidate_name = data.candidate_name
            res.email = data.email
            res.gender = data.gender
            res.reservation_category = data.get("reservation_category") or "General"
            res.program = data.program
            res.program_level = data.program_level
            res.academic_year = data.academic_year
            res.admission_cycle = data.admission_cycle
            res.campus = data.campus

            # Raw scores from Interview/Entrance Test Seat Allocation
            res.entrance_test_score = data.get("entrance_test_score") or 0
            res.interview_score = data.get("interview_score") or 0

            # Derive percentages (if not directly on the source doc, compute from raw score)
            res.entrance_percentage = compute_percentage(res.entrance_test_score)
            res.interview_percentage = compute_percentage(res.interview_score)

            # Academic marks from Applicant
            res.hsc_percentage = marks.get("hsc_percentage") or 0
            res.ug_cgpa = marks.get("ug_cgpa") or 0
            res.pg_cgpa = marks.get("pg_cgpa") or 0

            res.source_type = source_type
            res.result_status = "Qualified"
            res.configuration_reference = self.name

            res.flags.ignore_mandatory = True
            res.save(ignore_permissions=True)
            count += 1

        # Track applicant IDs that came from interview passers to avoid duplicates
        interview_applicant_ids = set()

        for app in passed_interviewees:
            upsert_result(app, "Interview Pass")
            interview_applicant_ids.add(app.applicant_id)

        for app in exempted_applicants:
            if app.applicant_id not in interview_applicant_ids:
                upsert_result(app, "Exempted")

        if count > 0:
            frappe.db.commit()
            self.db_set({
                "status": "Completed",
                "generated_on": now(),
                "generated_by": frappe.session.user
            })
            frappe.msgprint(
                f"Successfully generated <b>{count}</b> Eligibility Result records.",
                title="Generation Complete",
                indicator="green"
            )
        else:
            self.db_set("status", "Failed")
            frappe.throw("No eligible applicants found for the given criteria.")

        return count
