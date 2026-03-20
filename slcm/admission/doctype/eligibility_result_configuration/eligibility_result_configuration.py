# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
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

        # ─── Source 3: ET Pass + Interview Exempted ───────────────────────────
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

        # Previously we gathered academic marks (HSC, UG/PG CGPA) from
        # the Applicant document and its child tables.  The current
        # Eligibility Result doctype no longer contains any of those
        # fields, so there's no need to fetch them; attempting to read
        # non‑existent columns was causing SQL errors.  All scoring
        # information is now taken directly from the source records.

        count = 0
        source_counts = {
            "Interview Pass": 0,
            "ET Pass (Interview Exempt)": 0,
            "Exempted": 0
        }

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
                "pg_degree_details": [],
                "categories": ""
            }

            try:
                app = frappe.get_doc("Applicant", applicant_id)
            except Exception:
                return edu

            edu["hsc_group"] = getattr(app, "hsc_group", None)
            edu["hsc_percentage"] = getattr(app, "hsc_percentage", None)

            # Collect raw category rows from the Applicant's categories child table
            cats = [row.category for row in getattr(app, "categories", []) if row.category]
            edu["categories"] = cats  # kept as a list for child-table population

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
            source_counts[source_type] += 1
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

            # Fetch and populate education details from Applicant
            edu = get_applicant_education(data.applicant_id, data.program_level)

            # Populate the `category` child table from Applicant's categories
            res.set("category", [])
            for cat_name in (edu.get("categories") or []):
                res.append("category", {"category": cat_name})
            res.program = data.program
            res.program_level = data.program_level
            res.academic_year = data.academic_year
            res.admission_cycle = data.admission_cycle
            res.campus = data.campus

            # Populate scores. For exempted stages, assign 100 as per user request.
            if source_type == "Exempted":
                res.entrance_test_score = 100
                res.interview_score = 100
            elif source_type == "ET Pass (Interview Exempt)":
                res.entrance_test_score = data.get("entrance_test_score") or 0
                res.interview_score = 100
            else:
                res.entrance_test_score = data.get("entrance_test_score") or 0
                res.interview_score = data.get("interview_score") or 0

            # res.hsc_group already set via 'edu' above
            # res.hsc_percentage already set via 'edu' above
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
            
            # Send eligibility result notification email
            if res.email:
                try:
                    _send_eligibility_result_email(res)
                except Exception:
                    frappe.log_error(title=f"Eligibility Result Email Failed: {res.name}")

            # MASTER PIECE: Update Applicant Status to "Interview Completed"
            # Using direct SQL for maximum reliability and bypassing potentially stale caches
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

        # Track applicant IDs to avoid duplicates via a set
        finalized_applicant_ids = set()

        # Priority 1: Interview Passers
        for app in passed_interviewees:
            upsert_result(app, "Interview Pass")
            finalized_applicant_ids.add(app.applicant_id)

        # Priority 2: ET Pass + Interview Exempt (Source 3)
        for app in et_pass_interview_exempt:
            if app.applicant_id not in finalized_applicant_ids:
                upsert_result(app, "ET Pass (Interview Exempt)")
                finalized_applicant_ids.add(app.applicant_id)

        # Priority 3: Dual Exempted Applicants (Source 2)
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
            
            # Return detailed counts for the UI popup
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
                    
                    <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    
                    <div style="font-size: 12px; color: #64748b;">
                        <strong>Potential solutions:</strong>
                        <ul style="margin: 8px 0; padding-left: 20px;">
                            <li>Verify if applicants have passed their respective assessment stages.</li>
                            <li>Check exemption flags in <i>Eligibility Evaluation</i> for relevant applicants.</li>
                            <li>Ensure applicants are not in 'Rejected' status.</li>
                        </ul>
                    </div>
                </div>
            """
            frappe.throw(msg, title=_("Generation Failed"))

        return count


def _send_eligibility_result_email(res):
    """Send eligibility result notification to the applicant."""
    from frappe.utils import get_url
    url = get_url(f"/merit-and-scholarship/admission_dashboard?panel=applications")

    msg = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 20px auto; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); color: #1e293b;">
        <div style="background: #7b1c1c; padding: 30px 20px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 1px;">Eligibility Result</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0 0; font-size: 14px;">Office of Admissions</p>
        </div>
        
        <div style="padding: 30px 25px;">
            <p style="font-size: 16px; margin-bottom: 20px;">Dear <strong>{res.candidate_name or res.applicant_id}</strong>,</p>
            <p style="font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                Congratulations! We are pleased to inform you that your eligibility assessment for the academic session has been completed. Your result is now available for review.
            </p>
            
            <div style="background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 12px; padding: 20px; margin-bottom: 25px;">
                <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">Assessment Summary</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr><td style="padding: 8px 0; color: #64748b;">Programme:</td><td style="padding: 8px 0; font-weight: 700; text-align: right;">{res.program or '—'}</td></tr>
                    <tr><td style="padding: 8px 0; color: #64748b;">Academic Year:</td><td style="padding: 8px 0; font-weight: 700; text-align: right;">{res.academic_year or '—'}</td></tr>
                    <tr><td style="padding: 8px 0; color: #64748b;">Campus:</td><td style="padding: 8px 0; font-weight: 700; text-align: right;">{res.campus or '—'}</td></tr>
                    <tr><td style="padding: 8px 0; color: #64748b;">Entrance Score:</td><td style="padding: 8px 0; font-weight: 700; text-align: right; color: #1a73e8;">{res.entrance_test_score or 0} / 100</td></tr>
                    <tr><td style="padding: 8px 0; color: #64748b;">Interview Score:</td><td style="padding: 8px 0; font-weight: 700; text-align: right; color: #1a73e8;">{res.interview_score or 0} / 100</td></tr>
                    <tr><td style="padding: 12px 0 0 0; color: #64748b; font-weight: 700;">Result Status:</td><td style="padding: 12px 0 0 0; font-weight: 800; text-align: right; color: #16a34a; font-size: 16px;">{res.result_status or 'Qualified'}</td></tr>
                </table>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{url}" style="display: inline-block; padding: 14px 32px; background: #7b1c1c; color: #ffffff; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 16px; box-shadow: 0 4px 10px rgba(123, 28, 28, 0.25);">View Full Result & Portal</a>
            </div>
            
            <p style="font-size: 14px; color: #64748b; font-style: italic; text-align: center; margin-top: 20px;">
                Please log in to the portal to download your official Mark Sheet and view the next steps in your admission process.
            </p>
        </div>
        
        <div style="background: #f1f5f9; padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
            <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                Application Ref: {res.applicant_id} &nbsp;|&nbsp; Record: {res.name}<br>
                This is a system-generated email. Please do not reply.
            </p>
        </div>
    </div>
    """

    frappe.sendmail(
        recipients=[res.email],
        subject=f"Eligibility Result  — {res.candidate_name or res.applicant_id}",
        message=msg,
        reference_doctype="Eligibility Result",
        reference_name=res.name
    )