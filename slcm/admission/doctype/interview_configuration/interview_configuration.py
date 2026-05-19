# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now


class InterviewConfiguration(Document):

    def before_save(self):
        if not self.configuration_code:
            yr = getdate().strftime("%y")
            code = frappe.generate_hash("InterviewConfiguration", 8).upper()[:8]
            self.configuration_code = f"IVC-{yr}-{code}"

    @frappe.whitelist()
    def generate_interview_list(self):
        """
        Fetches eligible applicants from two sources and creates an Interview List.

        SOURCE 1 — Applicant Doctype (National Test Exempt, NOT exempt from interview):
          Students who passed via a national test rule (exempts_entrance_test = 1)
          but whose rule does NOT exempt them from interview (exempts_interview = 0).
          → source_type = "National Test (Direct)"

        SOURCE 2 — Entrance Test Seat Allocation (Passed the entrance test):
          Students who appeared for the entrance test and got result_status = 'Pass'.
          They are now eligible for the interview stage.
          → source_type = "Entrance Test"

        EXCLUSIONS:
          - Applicants with exempts_interview = 1 are excluded from ALL sources.
          - Rejected applicants are excluded.
          - Duplicates across sources are deduplicated by applicant_id.
        """
        if self.status not in ["Draft", "In Progress", "Failed"]:
            frappe.throw(
                "Document must be in Draft, In Progress, or Failed to generate interview list"
            )

        # Ensure schema is synced (updatedb is not a standard Frappe method)
        # frappe.db.updatedb("Interview List")
        # frappe.db.updatedb("Interview Applicant")

        # ─── SOURCE 1: National Test (Direct) ────────────────────────────────
        # Applicants who cleared a national test that exempts them from the
        # entrance test (exempts_entrance_test = 1), but the rule does NOT
        # exempt them from the interview (exempts_interview = 0).
        # We also ensure they are not independently flagged as exempted from
        # interview in the Eligibility Evaluation record.
        source1_applicants = frappe.db.sql("""
            SELECT
                app.name          AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview
            FROM `tabApplicant` app
            INNER JOIN `tabEligibility Evaluation` ee
                    ON ee.applicant_name = app.name
            INNER JOIN `tabProgram` p
                    ON p.name = app.program
            WHERE
                app.academic_year    = %(academic_year)s
                AND app.campus       = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                AND app.program_level   = %(program_level)s
                AND app.application_status != 'Rejected'
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
                AND ee.exempts_entrance_test = 1
                AND (ee.exempts_interview IS NULL OR ee.exempts_interview = 0)
                AND p.intereview = 1
        """, {
            "academic_year":   self.academic_year,
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level":   self.program_level
        }, as_dict=True)

        # ─── SOURCE 2: Entrance Test Passers ─────────────────────────────────
        # Students who sat the entrance test and have result_status = 'Pass'
        # in EntranceTestSeatAllocation. Fetch their details via the
        # Applicant link stored in the allocation record.
        # We use the carry-forward checkbox etsa.exempts_interview
        source2_applicants = frappe.db.sql("""
            SELECT
                app.name          AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview,
                COALESCE(etsa.total_marks_secured_in_part_a_b, 0) AS entrance_test_score
            FROM `tabEntrance Test Seat Allocation` etsa
            INNER JOIN `tabApplicant` app
                    ON app.name = etsa.applicant
            INNER JOIN `tabProgram` p
                    ON p.name = app.program
            WHERE
                etsa.academic_year    = %(academic_year)s
                AND etsa.campus       = %(campus)s
                AND etsa.admission_cycle = %(admission_cycle)s
                AND etsa.program_level   = %(program_level)s
                AND etsa.result_status   = 'Pass'
                AND app.application_status != 'Rejected'
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
                AND COALESCE(etsa.exempts_interview, 0) = 0
                AND p.intereview = 1
        """, {
            "academic_year":   self.academic_year,
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level":   self.program_level
        }, as_dict=True)

        # ─── SOURCE 3: No Entrance Test, but Interview Required ──────────────
        # Applicants whose program does NOT have an entrance test (p.entrance_test = 0)
        # but DOES have an interview (p.intereview = 1).
        source3_applicants = frappe.db.sql("""
            SELECT
                app.name          AS applicant_id,
                app.candidate_name,
                app.email,
                app.gender,
                app.program,
                app.program_level,
                app.entrance_test,
                app.intereview
            FROM `tabApplicant` app
            INNER JOIN `tabProgram` p
                    ON p.name = app.program
            WHERE
                app.academic_year    = %(academic_year)s
                AND app.campus       = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                AND app.program_level   = %(program_level)s
                AND app.application_status != 'Rejected'
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
                AND p.entrance_test = 0
                AND p.intereview = 1
                AND (app.exempts_interview IS NULL OR app.exempts_interview = 0)
        """, {
            "academic_year":   self.academic_year,
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level":   self.program_level
        }, as_dict=True)

        # ─── Merge & deduplicate ──────────────────────────────────────────────
        # Priority: if the same applicant appears in both sources, we tag them
        # as "Entrance Test" (more specific / recent stage).
        seen = {}

        for app in source1_applicants:
            seen[app.applicant_id] = {
                "applicant_id":         app.applicant_id,
                "candidate_name":       app.candidate_name or "Unknown",
                "email":                app.email,
                "gender":               app.gender,
                "program":              app.program,
                "program_level":        app.program_level,
                "entrance_test":        app.entrance_test,
                "intereview":           app.intereview,
                "source_type":          "National Test (Direct)"
            }

        for app in source3_applicants:
            seen[app.applicant_id] = {
                "applicant_id":         app.applicant_id,
                "candidate_name":       app.candidate_name or "Unknown",
                "email":                app.email,
                "gender":               app.gender,
                "program":              app.program,
                "program_level":        app.program_level,
                "entrance_test":        app.entrance_test,
                "intereview":           app.intereview,
                "source_type":          "Academic Eligibility"
            }

        for app in source2_applicants:
            # Overrides source1/3 entry if same applicant passed entrance test too
            seen[app.applicant_id] = {
                "applicant_id":         app.applicant_id,
                "candidate_name":       app.candidate_name or "Unknown",
                "email":                app.email,
                "gender":               app.gender,
                "program":              app.program,
                "program_level":        app.program_level,
                "entrance_test":        app.entrance_test,
                "intereview":           app.intereview,
                "source_type":          "Entrance Test"
            }

        all_applicants = list(seen.values())

        if not all_applicants:
            self.db_set("status", "Failed")

            # Diagnostic counts
            count_total = frappe.db.count("Applicant", {
                "academic_year":    self.academic_year,
                "campus":           self.campus,
                "admission_cycle":  self.admission_cycle,
                "program_level":    self.program_level
            })
            count_et_pass = frappe.db.count("Entrance Test Seat Allocation", {
                "academic_year":    self.academic_year,
                "campus":           self.campus,
                "admission_cycle":  self.admission_cycle,
                "program_level":    self.program_level,
                "result_status":    "Pass"
            })

            # Frappe Default Failure Message
            msg = (
                f"<b style='color: #dc3545;'>{_('No Candidates Found')}</b><br>"
                f"{_('Eligibility results')}:<br><br>"
                f"• {_('Total Applicants Evaluated')}: {count_total}<br>"
                f"• {_('Entrance Test Passers Found')}: {count_et_pass}<br><br>"
                f"<div style='font-size: 12px; color: #666; line-height: 1.6;'>"
                f"<b>{_('Possible reasons for no candidates')}:</b><br>"
                f"• {_('Applicants are already included in an existing Interview List.')}<br>"
                f"• {_('Applicants are exempted from the Interview stage.')}<br>"
                f"• {_('The selected Programs do not offer an Interview stage.')}<br>"
                f"• {_('Applicants have an incomplete application or were rejected.')}<br>"
                f"</div>"
            )
            frappe.throw(msg, title=_("Generation Failed"))

        # ─── Create Interview List ────────────────────────────────────────────
        interview_list = frappe.get_doc({
            "doctype":              "Interview List",
            "academic_year":        self.academic_year,
            "campus":               self.campus,
            "admission_cycle":      self.admission_cycle,
            "program_level":        self.program_level,
            "generated_on":         now(),
            "status":               "Generated",
            "interview_applicant":  []
        })

        for app in all_applicants:
            interview_list.append("interview_applicant", {
                "applicant_id":         app["applicant_id"],
                "candidate_name":       app["candidate_name"],
                "program":              app["program"],
                "program_level":        app["program_level"],
                "email":                app["email"],
                "gender":               app["gender"],
                "entrance_test":        app["entrance_test"],
                "intereview":           app["intereview"],
                "source_type":          app["source_type"],
                "interview_status":     "Pending"
            })

        interview_list.insert(ignore_permissions=True)

        self.db_set("status", "Completed")
        self.db_set("generated_on", now())
        self.db_set("generated_by", frappe.session.user)

        # Count per source for the success message
        cnt_national = sum(1 for a in all_applicants if a["source_type"] == "National Test (Direct)")
        cnt_et       = sum(1 for a in all_applicants if a["source_type"] == "Entrance Test")
        cnt_academic = sum(1 for a in all_applicants if a["source_type"] == "Academic Eligibility")

        # Frappe Default Centered Message
        msg = (
            f"<div style='text-align: center; padding: 10px;'>"
            f"<h4>{_('Interview List Generated Successfully')}</h4>"
            f"<p>{_('Details Below')}:</p>"
            f"<p style='font-size: 16px;'><b>{_('Eligible Candidates')}: {len(all_applicants)}</b></p>"
            f"<p>{_('National Test')}: {cnt_national} &nbsp;&middot;&nbsp; {_('Entrance Pass')}: {cnt_et} &nbsp;&middot;&nbsp; {_('Academic')}: {cnt_academic}</p>"
            f"<br>"
            f"<a href='/app/interview-list/{interview_list.name}' class='btn btn-primary btn-sm' style='color: #fff !important; text-decoration: none;'>"
            f"{_('View Interview List')}</a>"
            f"</div>"
        )
        
        frappe.msgprint(msg, indicator="green")

        return interview_list.name
