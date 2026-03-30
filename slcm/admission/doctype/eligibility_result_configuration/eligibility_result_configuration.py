# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now, get_url
import traceback


class EligibilityResultConfiguration(Document):

    def before_save(self):
        if not self.configuration_code:
            yr = getdate().strftime("%y")
            code = frappe.generate_hash("EligibilityResultConfiguration", 8).upper()[:8]
            self.configuration_code = f"ERC-{yr}-{code}"

    @frappe.whitelist()
    def generate_result(self):
        """
        Generates Eligibility Result records.
        """
        # Force reload the doctype to ensure the latest source_type options are picked up
        frappe.reload_doc("admission", "doctype", "eligibility_result")

        if self.status not in ["Draft", "In Progress", "Failed"]:
            frappe.throw("Document must be in Draft, In Progress, or Failed to generate results.")

        # ─── Source 1: Interview Passers ──────────────────────────────────────
        passed_interviewees = frappe.db.sql("""
            SELECT
                itsa.applicant AS applicant_id,
                itsa.candidate_name,
                itsa.email,
                itsa.gender,
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

        et_pass_interview_exempt = frappe.db.sql("""
            SELECT
                etsa.applicant AS applicant_id,
                etsa.candidate_name,
                etsa.email,
                etsa.gender,
                etsa.program,
                etsa.program_level,
                etsa.academic_year,
                etsa.admission_cycle,
                etsa.campus,
                etsa.score_obtained AS entrance_test_score
            FROM `tabEntrance Test Seat Allocation` etsa
            WHERE
                etsa.academic_year = %(academic_year)s
                AND etsa.campus = %(campus)s
                AND etsa.admission_cycle = %(admission_cycle)s
                AND etsa.program_level = %(program_level)s
                AND etsa.result_status = 'Pass'
                AND COALESCE(etsa.exempts_interview, 0) = 1
        """, {
            "academic_year": self.academic_year,
            "campus": self.campus,
            "admission_cycle": self.admission_cycle,
            "program_level": self.program_level
        }, as_dict=True)

        count = 0
        source_counts = {
            "Interview Pass": 0,
            "ET Pass (Interview Exempt)": 0,
            "Exempted": 0
        }

        def get_applicant_education(applicant_id, program_level):
            edu = {
                "hsc_group": None,
                "hsc_percentage": None,
                "ug_degree_details": [],
                "pg_degree_details": [],
                "categories": ""
            }
            try:
                app = frappe.get_doc("Applicant", applicant_id)
            except Exception:
                return edu

            edu["hsc_group"] = getattr(app, "hsc_group", None)
            edu["hsc_percentage"] = getattr(app, "hsc_percentage", None)
            edu["categories"] = [row.category for row in getattr(app, "categories", []) if row.category]

            if (program_level or "").strip() in ("PG", "Research Course"):
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
                # Do not update existing results as per user request
                return

            source_counts[source_type] += 1

            res = frappe.new_doc("Eligibility Result")
            res.applicant_id = data.applicant_id
            res.candidate_name = data.candidate_name
            res.email = data.email
            res.gender = data.gender

            edu = get_applicant_education(data.applicant_id, data.program_level)
            res.set("category", [])
            for cat_name in (edu.get("categories") or []):
                res.append("category", {"category": cat_name})
            res.program = data.program
            res.program_level = data.program_level
            res.academic_year = data.academic_year
            res.admission_cycle = data.admission_cycle
            res.campus = data.campus

            if source_type == "Exempted":
                res.entrance_test_score = 100
                res.interview_score = 100
            elif source_type == "ET Pass (Interview Exempt)":
                res.entrance_test_score = data.get("entrance_test_score") or 0
                res.interview_score = 100
            else:
                res.entrance_test_score = data.get("entrance_test_score") or 0
                res.interview_score = data.get("interview_score") or 0

            res.hsc_group = edu.get("hsc_group")
            res.hsc_percentage = edu.get("hsc_percentage")

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
            
            if res.email:
                try:
                    _send_eligibility_result_email(res)
                except Exception:
                    frappe.log_error(message=traceback.format_exc(), title=f"Eligibility Result Email Failed: {res.name}")

            frappe.db.sql("""
                UPDATE `tabApplicant` 
                SET application_status = 'Interview Completed', modified = %(now)s 
                WHERE name = %(name)s
            """, {"now": now(), "name": data.applicant_id})
            frappe.clear_document_cache("Applicant", data.applicant_id)
            frappe.publish_realtime(
                "applicant_application_status_updated",
                {"docname": data.applicant_id, "application_status": "Interview Completed"},
            )
            count += 1

        finalized_applicant_ids = set()
        for app in passed_interviewees:
            upsert_result(app, "Interview Pass")
            finalized_applicant_ids.add(app.applicant_id)
        for app in et_pass_interview_exempt:
            if app.applicant_id not in finalized_applicant_ids:
                upsert_result(app, "ET Pass (Interview Exempt)")
                finalized_applicant_ids.add(app.applicant_id)
        for app in exempted_applicants:
            if app.applicant_id not in finalized_applicant_ids:
                upsert_result(app, "Exempted")
                finalized_applicant_ids.add(app.applicant_id)

        if count > 0:
            frappe.db.commit()
            self.db_set({
                "status": "Completed",
                "generated_on": now(),
                "generated_by": frappe.session.user
            })
            return {
                "total": count,
                "interview_pass": source_counts["Interview Pass"],
                "et_pass_exempt": source_counts["ET Pass (Interview Exempt)"],
                "dual_exempt": source_counts["Exempted"]
            }
        else:
            self.db_set("status", "Failed")
            msg = f"""
                <div style="padding: 10px; font-family: sans-serif;">
                    <div style="font-size: 16px; font-weight: 700; color: #dc2626; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <i class="fa fa-exclamation-triangle"></i> No eligible applicants found
                    </div>
                    <p style="font-size: 13px; color: #64748b; margin-bottom: 20px;">
                        No applicants matching the selected criteria were found for result generation.
                    </p>
                    <div style="background: #fef2f2; border: 1px solid #fee2e2; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                        <h4 style="margin: 0 0 10px 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #991b1b;">Diagnostic Summary</h4>
                        <table style="width: 100%; font-size: 12px; color: #991b1b;">
                            <tr><td style="padding: 4px 0;">Interview Passers</td><td style="padding: 4px 0; font-weight: 700; text-align: right;">{len(passed_interviewees)}</td></tr>
                            <tr><td style="padding: 4px 0;">ET Pass (Exempt Interview)</td><td style="padding: 4px 0; font-weight: 700; text-align: right;">{len(et_pass_interview_exempt)}</td></tr>
                            <tr><td style="padding: 4px 0;">Dual Exempted</td><td style="padding: 4px 0; font-weight: 700; text-align: right;">{len(exempted_applicants)}</td></tr>
                        </table>
                    </div>
                    <div style="font-size: 13px; color: #475569;">
                        <strong>Filters Applied:</strong><br>
                        <span style="font-size: 12px; color: #64748b;">Year: {self.academic_year} | Campus: {self.campus} | Cycle: {self.admission_cycle} | Level: {self.program_level}</span>
                    </div>
                </div>
            """
            frappe.throw(msg, title=_("Generation Failed"))

        return count


def _send_eligibility_result_email(res):
    """Send an eligibility result notification using a configurable template."""
    try:
        template_name = "Eligibility Result"
        if not frappe.db.exists("Email Template", template_name):
            frappe.log_error(f"Email Template '{template_name}' not found.", "Email Sending Error")
            return

        template = frappe.get_doc("Email Template", template_name)
        
        # Prepare arguments for Jinja
        doc_dict = res.as_dict()
        args = {
            "doc": doc_dict,
            "portal_url": get_url("/merit-and-scholarship/admission_dashboard?panel=applications")
        }

        subject = frappe.render_template(template.subject, args)
        message_body = template.response_html if template.use_html else template.response
        
        if message_body:
            message = frappe.render_template(message_body, args)
            frappe.sendmail(
                recipients=[res.email],
                subject=subject,
                content=message,
                reference_doctype="Eligibility Result",
                reference_name=res.name,
                now=True
            )
    except Exception:
        frappe.log_error(message=traceback.format_exc(), title=f"Eligibility Result Email Failed: {res.name}")
