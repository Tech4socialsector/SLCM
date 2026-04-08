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
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
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
                AND app.name NOT IN (SELECT applicant_id FROM `tabInterview Applicant`)
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

            # Masterpiece Failure Message
            msg = f"""
                <div style="text-align: center; padding: 15px;">
                    <div style="color: #dc3545; font-size: 40px; margin-bottom: 15px;">
                        <i class="fa fa-exclamation-circle"></i>
                    </div>
                    <h3 style="font-weight: 800; margin-bottom: 10px; color: #171717;">{_("No Candidates Found")}</h3>
                    <p style="color: #666; margin-bottom: 25px;">{_("We couldn't find any new eligible candidates matching this configuration.")}</p>
                    
                    <div style="display: flex; justify-content: center; gap: 15px; margin-bottom: 25px;">
                        <div style="background: #f8f9fa; border: 1px solid #eef0f2; border-radius: 12px; padding: 12px 20px; min-width: 120px;">
                            <div style="font-size: 22px; font-weight: 900; color: #171717;">{count_total}</div>
                            <div style="font-size: 10px; font-weight: 700; color: #adb5bd; text-transform: uppercase;">{_("Evaluated")}</div>
                        </div>
                        <div style="background: #f8f9fa; border: 1px solid #eef0f2; border-radius: 12px; padding: 12px 20px; min-width: 120px;">
                            <div style="font-size: 22px; font-weight: 900; color: #171717;">{count_et_pass}</div>
                            <div style="font-size: 10px; font-weight: 700; color: #adb5bd; text-transform: uppercase;">{_("Test Passers")}</div>
                        </div>
                    </div>

                    <div style="text-align: left; background: #fff5f5; border-radius: 10px; padding: 15px; border: 1px solid #ffe3e3;">
                         <p style="margin: 0 0 8px 0; color: #dc3545; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">{_("Validation Checks Completed:")}</p>
                         <ul style="margin: 0; padding-left: 18px; color: #495057; font-size: 12px; line-height: 1.6;">
                            <li>{_("Exclusion of already generated applicants")}</li>
                            <li>{_("Verification of successful entrance test status")}</li>
                            <li>{_("Check for interview exemptions/rejections")}</li>
                         </ul>
                    </div>
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
                "source_type":          app["source_type"],
                "entrance_test_score":  app.get("entrance_test_score", 0),
                "interview_status":     "Pending"
            })

        interview_list.insert(ignore_permissions=True)

        self.db_set("status", "Completed")
        self.db_set("generated_on", now())
        self.db_set("generated_by", frappe.session.user)

        # Count per source for the success message
        cnt_national = sum(1 for a in all_applicants if a["source_type"] == "National Test (Direct)")
        cnt_et       = sum(1 for a in all_applicants if a["source_type"] == "Entrance Test")

        # Masterpiece Success Message
        msg = f"""
            <div style="text-align: center; padding: 15px;">
                <div style="color: #28a745; font-size: 40px; margin-bottom: 15px;">
                    <i class="fa fa-check-circle"></i>
                </div>
                <h3 style="font-weight: 800; margin-bottom: 10px; color: #171717;">{_("Generation Successful")}</h3>
                <p style="color: #666; margin-bottom: 25px;">{_("The interview list has been created with candidates who cleared the eligibility criteria.")}</p>
                
                <div style="display: flex; justify-content: center; gap: 15px; margin-bottom: 30px;">
                    <div style="background: #f8f9fa; border: 1px solid #eef0f2; border-radius: 12px; padding: 12px 20px; min-width: 100px;">
                        <div style="font-size: 24px; font-weight: 900; color: #171717;">{len(all_applicants)}</div>
                        <div style="font-size: 10px; font-weight: 700; color: #adb5bd; text-transform: uppercase; letter-spacing: 0.5px;">{_("Total Eligible")}</div>
                    </div>
                    <div style="background: #f8f9fa; border: 1px solid #eef0f2; border-radius: 12px; padding: 12px 20px; min-width: 100px;">
                        <div style="font-size: 24px; font-weight: 900; color: #171717;">{cnt_national}</div>
                        <div style="font-size: 10px; font-weight: 700; color: #adb5bd; text-transform: uppercase; letter-spacing: 0.5px;">{_("National Test")}</div>
                    </div>
                    <div style="background: #f8f9fa; border: 1px solid #eef0f2; border-radius: 12px; padding: 12px 20px; min-width: 100px;">
                        <div style="font-size: 24px; font-weight: 900; color: #171717;">{cnt_et}</div>
                        <div style="font-size: 10px; font-weight: 700; color: #adb5bd; text-transform: uppercase; letter-spacing: 0.5px;">{_("Entrance Pass")}</div>
                    </div>
                </div>

                <a href='/app/interview-list/{interview_list.name}' class="btn btn-primary" style="background-color: #171717; border-color: #171717; padding: 10px 35px; font-weight: 700; border-radius: 8px; color: #fff !important; text-decoration: none;">
                    {_("View Interview List")}
                </a>
            </div>
        """
        frappe.msgprint(msg, title="", indicator="green")

        return interview_list.name
