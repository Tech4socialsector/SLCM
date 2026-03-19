# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
import base64
import mimetypes
from frappe.model.document import Document
from frappe.utils import formatdate, nowdate, get_url, escape_html
from frappe.utils.pdf import get_pdf


class EligibilityResult(Document):

    def before_save(self):
        """
        Fetch the Applicant's multi-category child table and populate
        the local `category` table if it is currently empty.
        This mirrors the same pattern used in Entrance Test Seat Allocation
        and Interview Seat Allocation.
        """
        if self.applicant_id and not self.category:
            from slcm.admission.doctype.applicant.applicant import Applicant
            app_doc = frappe.get_doc("Applicant", self.applicant_id)
            app_categories = app_doc._get_applicant_categories()
            for cat in app_categories:
                self.append("category", {"category": cat})

    def on_update(self):
        """
        Generate and store the Eligibility Result Mark Sheet PDF.
        """
        if not self.flags.in_card_generation:
            self.generate_eligibility_card()

    def generate_eligibility_card(self):
        self.flags.in_card_generation = True
        try:
            html = self.get_card_html()
            pdf_content = get_pdf(html)
            
            filename = f"Eligibility_Result_{self.applicant_id}.pdf"
            
            # Check if file already exists for this document to avoid duplicates
            existing_file = frappe.get_all("File", filters={
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
                "attached_to_field": "eligibility_result_card"
            }, limit=1)
            
            if existing_file:
                _file = frappe.get_doc("File", existing_file[0].name)
                _file.content = pdf_content
                _file.save(ignore_permissions=True)
                file_url = _file.file_url
            else:
                _file = frappe.get_doc({
                    "doctype": "File",
                    "file_name": filename,
                    "attached_to_doctype": self.doctype,
                    "attached_to_name": self.name,
                    "attached_to_field": "eligibility_result_card",
                    "content": pdf_content,
                    "is_private": 0
                })
                _file.save(ignore_permissions=True)
                file_url = _file.file_url
            
            self.db_set("eligibility_result_card", file_url)
        finally:
            self.flags.in_card_generation = False

    def get_card_html(self):
        def esc(v): return escape_html(str(v if v is not None else ""))
        def val(v): return esc(v) if (v and str(v).strip() != "") else "—"

        app_doc = frappe.get_doc("Applicant", self.applicant_id)
        dob = formatdate(app_doc.date_of_birth) if app_doc.date_of_birth else "—"
        issue_date = formatdate(nowdate())

        def get_base64_img(file_url):
            if not file_url: return None
            try:
                if "?" in file_url: file_url = file_url.split("?")[0]
                if file_url.startswith(("http://", "https://")):
                    from urllib.parse import urlparse
                    file_url = urlparse(file_url).path
                if not file_url.startswith("/"): file_url = "/" + file_url
                if file_url.startswith("/private/files/"):
                    file_url = file_url.replace("/private/files/", "/files/")

                if not frappe.db.exists("File", {"file_url": file_url}): return None
                file_doc = frappe.get_doc("File", {"file_url": file_url})
                content = file_doc.get_content()
                if not content: return None
                mtype = mimetypes.guess_type(file_url)[0] or "image/png"
                b64 = base64.b64encode(content).decode()
                return f"data:{mtype};base64,{b64}"
            except Exception: return None

        profile_image_url = get_base64_img(app_doc.candidate_photo)
        campus_display_name = self.campus or "Institution of Legal Education"
        campus_logo_url = None
        try:
            campus = frappe.get_doc("Campus", self.campus)
            if campus.campus_name: campus_display_name = campus.campus_name
            if campus.logo: campus_logo_url = get_base64_img(campus.logo)
        except: pass

        header_html = f"""
            <div class="header">
              <div class="logo-box">
                {f'<img src="{campus_logo_url}" alt="Campus Logo" style="max-width:100%;max-height:100%;object-fit:contain;">' if campus_logo_url else '<div class="logo-inner"><span class="logo-icon">⚖</span><span class="logo-text">LAW<br>SCHOOL</span></div>'}
              </div>
              <div class="hdr-center">
                <div class="univ-name">{esc(campus_display_name)}</div>
                <div class="univ-sub">OFFICE OF ADMISSIONS &nbsp;&middot;&nbsp; ELIGIBILITY CELL</div>
              </div>
            </div>"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Eligibility Result - {esc(self.applicant_id)}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: "Times New Roman", Times, serif;
  font-size: 13px;
  background: #fff;
  color: #000;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}}
img {{ max-width: none !important; }}
.card-page {{
  width: 710px;
  margin: 0 auto;
  background: #fff;
  border: 1.5px solid #555;
  page-break-after: always;
}}
.header {{
  background: #7b1c1c;
  display: flex;
  align-items: center;
  padding: 10px 18px;
  gap: 16px;
  border-bottom: 3px solid #5a0e0e;
}}
.logo-box {{
  width: 74px;
  height: 74px;
  background: #fff;
  border: 2px solid rgba(255,255,255,0.6);
  border-radius: 3px;
  display: flex;
  align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden;
}}
.logo-box img {{ width: 70px; height: 70px; object-fit: contain; }}
.logo-inner {{
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
}}
.logo-icon {{ font-size: 28px; line-height: 1; color: #7b1c1c; }}
.logo-text {{
  font-size: 7.5px; font-weight: bold; font-family: Arial, sans-serif; color: #7b1c1c;
  text-align: center; letter-spacing: 0.5px; line-height: 1.2;
}}
.hdr-center {{ flex: 1; text-align: center; }}
.univ-name {{
  font-size: 21px; font-weight: bold; font-family: Arial, sans-serif; color: #fff;
  text-transform: uppercase; letter-spacing: 1.5px; line-height: 1.2;
}}
.univ-sub {{
  font-size: 11px; font-family: Arial, sans-serif; color: rgba(255,255,255,0.80);
  letter-spacing: 2.5px; text-transform: uppercase; margin-top: 3px;
}}
.title-row {{ text-align: center; padding: 9px 18px 7px; border-bottom: 1.5px solid #bbb; }}
.title-row .t1 {{ font-size: 14px; font-weight: bold; font-family: Arial, sans-serif; color: #000; }}
.title-row .t2 {{ font-size: 12.5px; font-family: Arial, sans-serif; color: #111; margin-top: 2px; }}
.info-wrap {{ border: 1.5px solid #888; margin: 12px 14px; display: flex; }}
.info-tbl {{ flex: 1; border-collapse: collapse; }}
.info-tbl tr {{ border-bottom: 1px solid #ccc; }}
.info-tbl tr:last-child {{ border-bottom: none; }}
.info-tbl td {{ padding: 5.5px 8px; font-size: 12.5px; vertical-align: middle; line-height: 1.5; }}
.info-tbl td.lb {{ font-weight: bold; font-family: Arial, sans-serif; width: 36%; white-space: nowrap; color: #000; }}
.info-tbl td.sp {{ width: 14px; font-weight: bold; font-family: Arial, sans-serif; color: #000; text-align: center; padding: 0; }}
.info-tbl td.vl {{ font-family: "Times New Roman", Times, serif; font-size: 13px; color: #000; }}
.score-pill {{
  display: inline-block; background: #e8f0fe; color: #1a73e8; font-weight: bold;
  font-family: Arial, sans-serif; font-size: 13px; padding: 2px 10px; border-radius: 4px; border: 1px solid #1a73e8;
}}
.photo-col {{ 
  width: 140px; 
  flex-shrink: 0; 
  border-left: 1.5px solid #888; 
  display: flex; 
  flex-direction: column; 
  align-items: center; 
  justify-content: flex-start; 
  padding: 10px 8px; 
  min-height: 200px; 
}}
.photo-frame {{ 
  width: 120px; 
  height: 150px; 
  border: 1.5px solid #555; 
  overflow: hidden; 
  background: #eee; 
  display: flex; 
  align-items: center; 
  justify-content: center; 
}}
.photo-frame img {{ 
  width: 100%; 
  height: 100%; 
  object-fit: cover; 
}}
.photo-ph {{ font-size: 36px; color: #aaa; text-align: center; line-height: 150px; }}
.photo-cap {{
  font-size: 9.5px; font-family: Arial, sans-serif; color: #555; text-align: center; font-style: italic; line-height: 1.3; margin-top: 8px;
}}
.pg-footer {{ padding: 6px 14px 10px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #ddd; margin-top: 20px; }}
.pg-footer span {{ font-size: 8.5px; font-family: Arial, sans-serif; color: #888; }}
@media print {{ body {{ background: #fff; margin: 0; }} .card-page {{ width: 100%; margin: 0; border: 1.5px solid #555; }} }}
</style>
</head>
<body>
<div class="card-page">
  {header_html}
  <div class="title-row">
    <div class="t1">Eligibility Result Mark Sheet</div>
    <div class="t2">{val(self.academic_year)} &nbsp;|&nbsp; {val(self.admission_cycle)}</div>
  </div>
  <div class="info-wrap">
    <table class="info-tbl">
      <tbody>
        <tr><td class="lb">Candidate's Name</td><td class="sp">:</td><td class="vl">{val(self.candidate_name)}</td></tr>
        <tr><td class="lb">Date of Birth</td><td class="sp">:</td><td class="vl">{val(dob)}</td></tr>
        <tr><td class="lb">Father's Name</td><td class="sp">:</td><td class="vl">{val(app_doc.father_name)}</td></tr>
        <tr><td class="lb">Mother's Name</td><td class="sp">:</td><td class="vl">{val(app_doc.mother_name)}</td></tr>
        <tr><td class="lb">Gender</td><td class="sp">:</td><td class="vl">{val(self.gender)}</td></tr>
        <tr><td class="lb">Programme Applied</td><td class="sp">:</td><td class="vl">{val(self.program)}</td></tr>
        <tr><td class="lb">Application Number</td><td class="sp">:</td><td class="vl">{val(self.applicant_id)}</td></tr>
        <tr><td class="lb">Entrance score</td><td class="sp">:</td><td class="vl"><span class="score-pill">{val(self.entrance_test_score)}</span></td></tr>
        <tr><td class="lb">Interview score</td><td class="sp">:</td><td class="vl"><span class="score-pill">{val(self.interview_score)}</span></td></tr>
        <tr><td class="lb">Result Status</td><td class="sp">:</td><td class="vl"><strong>{val(self.result_status)}</strong></td></tr>
      </tbody>
    </table>
    <div class="photo-col">
        <div class="photo-frame">
          {f'<img src="{profile_image_url}" alt="Candidate Photo">' if profile_image_url else '<div class="photo-ph">👤</div>'}
        </div>
        <div class="photo-cap">Candidate's Photograph</div>
    </div>
  </div>
  <div style="padding: 20px 14px; font-size: 12px; line-height: 1.6;">
    <p>This is a system-generated Eligibility Result Mark Sheet. It indicates the scores obtained by the candidate in the Entrance Test and Interview (if applicable) for the specified admission cycle.</p>
  </div>
  <div class="pg-footer">
    <span>Doc: <strong>{val(self.name)}</strong> &nbsp;·&nbsp; Generated: <strong>{val(issue_date)}</strong> &nbsp;·&nbsp; System-generated.</span>
    <span>{val(self.applicant_id)}</span>
  </div>
</div>
</body>
</html>"""
        return html

@frappe.whitelist()
def get_applicant_data():
    """
    Fetches merit scores and admission statuses for the currently logged-in applicant.
    Security: Only returns data matching the session user's email.
    """
    user_email = frappe.session.user
    if user_email == "Guest":
        return {"error": "Unauthorized"}

    # 1. Fetch the primary Eligibility Result names first to get full docs
    result_names = frappe.get_all("Eligibility Result", 
        filters={"email": user_email},
        pluck="name"
    )
    
    if not result_names:
        result_names = frappe.get_all("Eligibility Result", 
            filters={"owner": user_email},
            pluck="name"
        )

    results = []
    for name in result_names:
        doc = frappe.get_doc("Eligibility Result", name)
        
        # Calculate averaged UG CGPA
        ug_avg = 0
        if doc.ug_degree_details:
            scores = [float(r.ug_cgpa or r.percentage_cgpa_obtained or 0) for r in doc.ug_degree_details]
            if scores: ug_avg = sum(scores) / len(scores)
            
        # Calculate averaged PG CGPA
        pg_avg = 0
        if doc.pg_degree_details:
            scores = [float(r.pg_cgpa or r.percentagecgpa_obtained or 0) for r in doc.pg_degree_details]
            if scores: pg_avg = sum(scores) / len(scores)

        results.append({
            "name": doc.name,
            "applicant_id": doc.applicant_id,
            "candidate_name": doc.candidate_name,
            "campus": doc.campus,
            "program": doc.program,
            "program_level": doc.program_level,
            "admission_cycle": doc.admission_cycle,
            "reservation_category": ", ".join([c.category for c in doc.category if c.category]) if doc.category else "General",
            "hsc_percentage": doc.hsc_percentage,
            "entrance_test_score": doc.entrance_test_score,
            "interview_score": doc.interview_score,
            "source_type": doc.source_type,
            "result_status": doc.result_status,
            "ug_cgpa": round(ug_avg, 2),
            "pg_cgpa": round(pg_avg, 2),
            "eligibility_result_card": doc.eligibility_result_card
        })

    if not results:
        # Check if any data is published even without Eligibility Result
        app_id = frappe.db.get_value("Applicant", {"email": user_email}, "name")
        if not app_id:
             app_id = frappe.db.get_value("Applicant", {"owner": user_email}, "name")

        if not app_id:
            return {"error": "No admission application record found for this account."}

        # Check for published Merit List or Seat Allocation
        merit_exists = frappe.db.exists("Merit List Applicant", {"applicant_id": app_id})
        allocation_exists = frappe.db.exists("Seat Selection Applicant", {"applicant_id": app_id})
        
        # If neither exists, then it's truly in progress
        if not merit_exists and not allocation_exists:
            # Check if any scholarship is published to allow early application
            scholarship_available = frappe.db.get_single_value("Admission Settings", "is_scholarship_available")
            if not scholarship_available:
                return {"error": "Your application is under review. Merit lists and scholarships will be visible here once published."}


    # 2. For each result, get the specific selection statuses from Seat Allocation child tables
    settings = frappe.get_single("Admission Settings")
    
    combined_data = []

    # If results is empty but we have an app_id, we might want to synthesize a result
    if not results and app_id:
        app = frappe.get_doc("Applicant", app_id)
        results.append({
            "applicant_id": app_id,
            "candidate_name": app.candidate_name,
            "campus": app.campus,
            "program": app.program,
            "admission_cycle": app.admission_cycle,
            "program_level": app.program_level,
            "reservation_category": app.whether_scstobc_ncl if app.whether_scstobc_ncl and app.whether_scstobc_ncl != "NA" else ("Karnataka" if app.karnataka_category == "Yes" else "General"),
            "hsc_percentage": getattr(app, "hsc_percentage", 0),
            "entrance_test_score": getattr(app, "entrance_test_score", None),
            "interview_score": getattr(app, "interview_score", None),
            "source_type": getattr(app, "source_type", None),
            "result_status": getattr(app, "result_status", None),
            "ug_cgpa": 0,
            "pg_cgpa": 0,
            "eligibility_result_card": None
        })

    for res in results:  
        # Fetch Merit List Entries
        merit_entries = []
        if settings.is_merit_list:
            merit_entries = frappe.get_all("Merit List Applicant",
                filters={"applicant_id": res['applicant_id']},
                fields=["total_score", "overall_rank", "program_rank", "status", "parent"]
            )
            for m in merit_entries:
                if m.get("parent"):
                    m["published"] = frappe.db.get_value("Merit List", m.get("parent"), "status") == "Published"
        
        # Fetch Seat Allocation Statuses
        statuses = frappe.get_all("Seat Selection Applicant",
            filters={"applicant_id": res['applicant_id']},
            fields=["selection_status", "overall_rank", "allocation_type", "parent", "total_score", "allocated_category"]
        )
        
        # Inject Seat Allocation details
        for s in statuses:
            if s.get("parent"):
                s["published"] = frappe.db.get_value("Seat Allocation", s.get("parent"), "status") == "Published"
        
        published_statuses = [s.get("selection_status") for s in statuses if s.get("published")]
        
        available_scholarships = []
        applied_scholarships = []
        if res['applicant_id'] and settings.is_scholarship_available:
            from slcm.admission.utils.scholarship_availability import get_available_scholarships_for_dashboard, get_applied_scholarships_for_dashboard
            available_scholarships = get_available_scholarships_for_dashboard(
                res['applicant_id'], res['admission_cycle'], res['campus'], res['program'], published_statuses
            )
            applied_scholarships = get_applied_scholarships_for_dashboard(res['applicant_id'])

        combined_data.append({
            "profile": res,
            "merit": [m for m in merit_entries if m.get("published")],
            "results": [s for s in statuses if s.get("published")],
            "available_scholarships": available_scholarships,
            "applied_scholarships": applied_scholarships
        })

    return combined_data
