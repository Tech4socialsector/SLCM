# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


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

        # Force schema sync
        frappe.db.updatedb("Interview List")
        frappe.db.updatedb("Interview Applicant")

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
                app.reservation_category,
                app.program,
                app.program_level
            FROM `tabApplicant` app
            INNER JOIN `tabEligibility Evaluation` ee
                    ON ee.applicant_name = app.name
            WHERE
                app.academic_year    = %(academic_year)s
                AND app.campus       = %(campus)s
                AND app.admission_cycle = %(admission_cycle)s
                AND app.program_level   = %(program_level)s
                AND app.application_status != 'Rejected'
                AND ee.exempts_entrance_test = 1
                AND (ee.exempts_interview IS NULL OR ee.exempts_interview = 0)
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
                app.reservation_category,
                app.program,
                app.program_level,
                COALESCE(etsa.score_obtained, 0) AS entrance_test_score
            FROM `tabEntrance Test Seat Allocation` etsa
            INNER JOIN `tabApplicant` app
                    ON app.name = etsa.applicant
            WHERE
                etsa.academic_year    = %(academic_year)s
                AND etsa.campus       = %(campus)s
                AND etsa.admission_cycle = %(admission_cycle)s
                AND etsa.program_level   = %(program_level)s
                AND etsa.result_status   = 'Pass'
                AND app.application_status != 'Rejected'
                AND COALESCE(etsa.exempts_interview, 0) = 0
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
                "reservation_category": app.reservation_category,
                "program":              app.program,
                "program_level":        app.program_level,
                "source_type":          "National Test (Direct)",
                "entrance_test_score":  100  # Exempted via national test → treated as full marks
            }

        for app in source2_applicants:
            # Overrides source1 entry if same applicant passed entrance test too
            seen[app.applicant_id] = {
                "applicant_id":         app.applicant_id,
                "candidate_name":       app.candidate_name or "Unknown",
                "email":                app.email,
                "gender":               app.gender,
                "reservation_category": app.reservation_category,
                "program":              app.program,
                "program_level":        app.program_level,
                "source_type":          "Entrance Test",
                "entrance_test_score":  app.get("entrance_test_score") or 0
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

            msg = f"""
                <div style="font-size: 14px;">
                    <p><b>{_("No eligible applicants were found matching the selected criteria.")}</b></p>
                    <hr>
                    <p><b>{_("Applied Filters:")}</b></p>
                    <ul>
                        <li><b>{_("Year")}:</b> {self.academic_year}</li>
                        <li><b>{_("Campus")}:</b> {self.campus}</li>
                        <li><b>{_("Cycle")}:</b> {self.admission_cycle}</li>
                        <li><b>{_("Level")}:</b> {self.program_level}</li>
                    </ul>
                    <p><b>{_("System Diagnostic:")}</b></p>
                    <ul>
                        <li>{_("Total applicants matching filters")}: <b>{count_total}</b></li>
                        <li>{_("Applicants who passed the Entrance Test")}: <b>{count_et_pass}</b></li>
                    </ul>
                    <p><b>{_("Possible Reasons:")}</b></p>
                    <ol>
                        <li>{_("Applicants may be flagged as 'Exempt from Interview' in Eligibility Evaluation or Entrance Test results.")}</li>
                        <li>{_("Applicants might have an 'Application Status' of 'Rejected'.")}</li>
                        <li>{_("Entrance Test results for this cycle might not have been processed yet.")}</li>
                    </ol>
                </div>
            """
            frappe.throw(msg, title=_("Generation Failed"))

        # ─── Create Interview List ────────────────────────────────────────────
        interview_list = frappe.get_doc({
            "doctype":              "Interview List",
            "academic_year":        self.academic_year,
            "campus":               self.campus,
            "admission_cycle":      self.admission_cycle,
            "program_level":        self.program_level,
            "generated_on":         frappe.utils.now(),
            "status":               "Generated",
            "interview_applicant":  []
        })

        for app in all_applicants:
            interview_list.append("interview_applicant", {
                "applicant_id":         app["applicant_id"],
                "candidate_name":       app["candidate_name"],
                "program":              app["program"],
                "program_level":        app["program_level"],
                "reservation_category": app["reservation_category"],
                "email":                app["email"],
                "gender":               app["gender"],
                "source_type":          app["source_type"],
                "entrance_test_score":  app.get("entrance_test_score", 0),
                "interview_status":     "Pending"
            })

        interview_list.insert(ignore_permissions=True)

        self.db_set({
            "status":       "Completed",
            "generated_on": frappe.utils.now(),
            "generated_by": frappe.session.user
        })

        # Count per source for the success message
        cnt_national = sum(1 for a in all_applicants if a["source_type"] == "National Test (Direct)")
        cnt_et       = sum(1 for a in all_applicants if a["source_type"] == "Entrance Test")

        frappe.msgprint(
            f"<b>Success!</b> Created Interview List with {len(all_applicants)} applicants.<br>"
            f"<ul>"
            f"<li>National Test (Direct): <b>{cnt_national}</b></li>"
            f"<li>Entrance Test Passers: <b>{cnt_et}</b></li>"
            f"</ul>"
            f"<a href='/app/interview-list/{interview_list.name}'>{interview_list.name}</a>",
            title="Interview List Generated",
            indicator="green"
        )

        return interview_list.name
