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

        # Previously we gathered academic marks (HSC, UG/PG CGPA) from
        # the Applicant document and its child tables.  The current
        # Eligibility Result doctype no longer contains any of those
        # fields, so there's no need to fetch them; attempting to read
        # non‑existent columns was causing SQL errors.  All scoring
        # information is now taken directly from the source records.

        count = 0

        def get_applicant_education(applicant_id, program_level):
            """Fetch education-related fields from the Applicant doc.
            Rules:
            - UG: only return `hsc_group` and `hsc_percentage`.
            - PG / Research Course: return `hsc_group`, `hsc_percentage`
              and copy `pg_degree_details` rows (if any).
            """
            edu = {
                "hsc_group": None,
                "hsc_percentage": None,
                "ug_degree_details": [],
                "pg_degree_details": []
            }

            try:
                app = frappe.get_doc("Applicant", applicant_id)
            except Exception:
                return edu

            edu["hsc_group"] = getattr(app, "hsc_group", None)
            edu["hsc_percentage"] = getattr(app, "hsc_percentage", None)

            if (program_level or "").strip() in ("PG", "Research Course"):
                # copy UG degree rows if present (PG applicants need their UG transcript)
                for row in getattr(app, "ug_degree_details", []) or []:
                    edu["ug_degree_details"].append({
                        "ug_program": getattr(row, "ug_program", None),
                        "ug_cgpa": getattr(row, "ug_cgpa", None),
                        "percentage_cgpa_obtained": getattr(row, "percentage_cgpa_obtained", None),
                        "year_of_completion": getattr(row, "year_of_completion", None),
                        "college": getattr(row, "college", None),
                        "degree_certificate": getattr(row, "degree_certificate", None),
                        "marksheets": getattr(row, "marksheets", None)
                    })

                # also copy any PG degree details they may have entered (rare)
                for row in getattr(app, "pg_degree_details", []) or []:
                    edu["pg_degree_details"].append({
                        "pg_program": getattr(row, "pg_program", None),
                        "pg_cgpa": getattr(row, "pg_cgpa", None),
                        "percentagecgpa_obtained": getattr(row, "percentagecgpa_obtained", None),
                        "year_of_completion": getattr(row, "year_of_completion", None),
                        "collegeuniversity": getattr(row, "collegeuniversity", None),
                        "pg_degree_certificatebonafide_certificate_to_be_uploaded": getattr(row, "pg_degree_certificatebonafide_certificate_to_be_uploaded", None),
                        "transcriptsmarksheets_to_be_uploaded": getattr(row, "transcriptsmarksheets_to_be_uploaded", None)
                    })

            return edu
        def upsert_result(data, source_type):
            nonlocal count
            existing = frappe.db.get_value("Eligibility Result", {"applicant_id": data.applicant_id}, "name")
            if existing:
                res = frappe.get_doc("Eligibility Result", existing)
            else:
                res = frappe.new_doc("Eligibility Result")
                res.applicant_id = data.applicant_id

            # Populate only the fields that actually exist on the
            # Eligibility Result doctype.  Marks and percentages were
            # removed from the schema earlier, so we no longer store them.
            res.candidate_name = data.candidate_name
            res.email = data.email
            res.gender = data.gender
            res.reservation_category = data.get("reservation_category")
            res.program = data.program
            res.program_level = data.program_level
            res.academic_year = data.academic_year
            res.admission_cycle = data.admission_cycle
            res.campus = data.campus

            # retain the raw scores if provided (these fields are still
            # defined on Eligibility Result)
            res.entrance_test_score = data.get("entrance_test_score") or 0
            res.interview_score = data.get("interview_score") or 0

            # Fetch and populate education details from Applicant
            edu = get_applicant_education(data.applicant_id, data.program_level)
            # always write HSC values (may be blank)
            res.hsc_group = edu.get("hsc_group")
            res.hsc_percentage = edu.get("hsc_percentage")

            # clear existing child tables first
            if getattr(res, "ug_degree_details", None):
                res.set("ug_degree_details", [])
            if getattr(res, "pg_degree_details", None):
                res.set("pg_degree_details", [])

            # populate both UG and PG rows for PG/Research applicants
            if (data.program_level or "").strip() in ("PG", "Research Course"):
                for row in edu.get("ug_degree_details", []) or []:
                    res.append("ug_degree_details", row)
                for row in edu.get("pg_degree_details", []) or []:
                    res.append("pg_degree_details", row)

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
