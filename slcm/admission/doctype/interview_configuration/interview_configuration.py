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

            msg = f"""
                <div style="font-family: inherit; padding: 15px; background: #fff; border-radius: 12px; border: 1px solid #ffccd5; border-left: 6px solid #dc3545;">
                    <div style="display: flex; align-items: center; margin-bottom: 20px;">
                        <div style="background: #dc3545; color: #fff; width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 24px;">
                            <i class="fa fa-exclamation-triangle"></i>
                        </div>
                        <div>
                            <h4 style="margin: 0; color: #dc3545; font-weight: 700; font-size: 18px;">Generation Incomplete</h4>
                            <p style="margin: 0; color: #6c757d; font-size: 13px;">No eligible candidates were found</p>
                        </div>
                    </div>

                    <div style="margin-bottom: 20px; font-size: 14px;">
                        <p style="margin: 0 0 10px 0; color: #495057; font-weight: 600;">System Breakdown:</p>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                                <span style="display: block; font-size: 9px; color: #adb5bd;">Total Applicants</span>
                                <span style="font-size: 16px; font-weight: 700;">{count_total}</span>
                            </div>
                            <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                                <span style="display: block; font-size: 9px; color: #adb5bd;">Entrance Test Passers</span>
                                <span style="font-size: 16px; font-weight: 700;">{count_et_pass}</span>
                            </div>
                        </div>
                    </div>

                    <div style="background: #fff5f5; border-radius: 10px; padding: 15px; border: 1px solid #ffe3e3;">
                         <p style="margin: 0 0 10px 0; color: #dc3545; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">Potential Blockers:</p>
                         <ul style="margin: 0; padding-left: 18px; color: #495057; font-size: 13px; line-height: 1.6;">
                            <li>Already Generated? <b>{_("Validated")}</b></li>
                            <li>Rejected Status? <b>{_("Validated")}</b></li>
                            <li>Exempted from Interview? <b>{_("Validated")}</b></li>
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
            <div style="font-family: inherit; padding: 15px; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 12px; border: 1px solid #e9ecef; box-shadow: 0 10px 30px rgba(0,0,0,0.08);">
                <div style="display: flex; align-items: center; margin-bottom: 20px;">
                    <div style="background: #28a745; color: #fff; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 24px; box-shadow: 0 4px 12px rgba(40,167,69,0.2);">
                        <i class="fa fa-check-circle"></i>
                    </div>
                    <div>
                        <h4 style="margin: 0; color: #212529; font-weight: 800; font-size: 20px; line-height: 1.2;">Interview List Generated Successfully</h4>
                        <p style="margin: 0; color: #6c757d; font-size: 13px; font-weight: 500;">Details Below</p>
                    </div>
                </div>

                <div style="background: #f8f9fa; border-radius: 12px; padding: 18px; border: 1px solid #f1f3f5; margin-bottom: 25px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1.5px solid #dee2e6; padding-bottom: 12px;">
                        <span style="font-size: 14px; font-weight: 700; color: #495057; text-transform: uppercase; letter-spacing: 0.5px;">Eligible Candidates</span>
                        <span style="background: #28a745; color: #fff; font-weight: 800; font-size: 16px; padding: 4px 16px; border-radius: 20px; box-shadow: 0 2px 6px rgba(40,167,69,0.15);">{len(all_applicants)}</span>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <div style="background: #fff; border-radius: 10px; padding: 12px; text-align: center; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
                            <div style="font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: #adb5bd; margin-bottom: 6px;">National Test</div>
                            <div style="font-size: 20px; font-weight: 900; color: #007bff;">{cnt_national}</div>
                        </div>
                        <div style="background: #fff; border-radius: 10px; padding: 12px; text-align: center; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
                            <div style="font-size: 9px; text-transform: uppercase; letter-spacing: 1px; color: #adb5bd; margin-bottom: 6px;">Entrance Pass</div>
                            <div style="font-size: 20px; font-weight: 900; color: #007bff;">{cnt_et}</div>
                        </div>
                    </div>
                </div>

                <div style="text-align: center;">
                    <a href='/app/interview-list/{interview_list.name}' style="display: inline-block; background: #212529; color: #fff !important; text-decoration: none !important; font-weight: 700; font-size: 14px; padding: 12px 32px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: all 0.2s ease;">
                         <i class="fa fa-eye"></i> &nbsp; View Interview List
                    </a>
                </div>
            </div>
        """
        frappe.msgprint(msg, title="", indicator="green")

        return interview_list.name
