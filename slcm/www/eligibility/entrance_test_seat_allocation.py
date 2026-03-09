import frappe
from frappe import _
from frappe.utils import escape_html, format_datetime, formatdate, nowdate, get_url
import base64
import mimetypes

def get_context(context):
    from slcm.admission.utils.portal import get_portal_config
    context.portal_config = get_portal_config()
    
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to view this page"), frappe.PermissionError)

    # Get applicant name for the current user
    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    if not applicant_name:
        context.no_record = True
        return context

    # Get Seat Allocation record
    allocation = frappe.get_all("Entrance Test Seat Allocation", 
        filters={"applicant": applicant_name},
        fields=["*"],
        order_by="creation desc",
        limit=1
    )

    if not allocation:
        context.no_record = True
        return context

    doc = frappe.get_doc("Entrance Test Seat Allocation", allocation[0].name)
    context.doc = doc
    
    # Check if rescheduled
    is_rescheduled = (doc.is_rescheduled == 1 or doc.entrance_test_status == "Rescheduled")
    context.is_rescheduled = is_rescheduled
    
    # Track previous schedule if rescheduled
    if is_rescheduled:
        context.previous_schedule = {
            "center": doc.center_name,
            "address": doc.center_address,
            "date": doc.allocation_date,
            "status": doc.allocation_status or "Rescheduled",
            "reason": doc.reschedule_reason or "System Rescheduled"
        }
    else:
        context.previous_schedule = None
    
    # Get preferences
    raw_prefs = doc.re_assigned_preferences if is_rescheduled else doc.assigned_preferences
    context.preferences = []
    for p in raw_prefs:
        context.preferences.append({
            "provider": p.provider,
            "center_name": p.center_name,
            "center_address": p.center_address
        })
    
    # Check if result is published
    context.show_result = (doc.entrance_test_status in ["Attended", "Absent"] and doc.result_published == 1)

    # Reporting time calculation (1 hour before exam)
    from datetime import timedelta
    f_date = doc.re_allocation_date if is_rescheduled else doc.allocation_date
    if f_date:
        try:
            rep_dt = f_date - timedelta(hours=1)
            context.reporting_time = format_datetime(rep_dt, "hh:mm a")
        except:
            context.reporting_time = "09:30 AM" # Fallback
    else:
        context.reporting_time = "—"
    
    return context

@frappe.whitelist()
def save_provider(allocation_name, selected_provider, is_rescheduled=False):
    """
    Saves the provider choice for the applicant.
    """
    from slcm.admission.doctype.entrance_test_list.entrance_test_list import (
        confirm_applicant_preference, 
        confirm_rescheduled_preference
    )
    
    # Security check: verify ownership
    user = frappe.session.user
    applicant_name = frappe.db.get_value("Applicant", {"email": user}, "name")
    doc_applicant = frappe.db.get_value("Entrance Test Seat Allocation", allocation_name, "applicant")
    
    if not applicant_name or doc_applicant != applicant_name:
        frappe.throw(_("You are not authorized to modify this record."), frappe.PermissionError)
    
    # Validation
    doc = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    # Cast is_rescheduled to safe boolean if stringified
    if isinstance(is_rescheduled, str):
        is_rescheduled = is_rescheduled.lower() == "true"

    prefs = doc.re_assigned_preferences if is_rescheduled else doc.assigned_preferences
    if not any(p.provider == selected_provider for p in prefs):
        frappe.throw(_("Please choose from your assigned preference centers."))

    if is_rescheduled:
        return confirm_rescheduled_preference(allocation_name, selected_provider)
    else:
        return confirm_applicant_preference(allocation_name, selected_provider)

@frappe.whitelist(allow_guest=True)
def download_admit_card(allocation_name):
    """
    Downloads the Admit Card. Prioritizes the stored file (BASE or RE).
    Accessible without login if the file is already generated.
    Always regenerates for logged-in users to ensure accuracy.
    """
    doc = frappe.get_doc("Entrance Test Seat Allocation", allocation_name)
    
    is_rescheduled = (doc.is_rescheduled == 1 or doc.entrance_test_status == "Rescheduled")
    status = doc.re_allocation_status if is_rescheduled else doc.allocation_status
    
    if status not in ["Allocated", "Reallocated"]:
        frappe.throw(_("Admit Card is only available after seat allocation is confirmed."))

    field_to_check = "reschedule_admit_card" if is_rescheduled else "admit_card"
    
    # Always regenerate the Admit Card PDF to reflect potential changes in data/layout
    if frappe.session.user == "Guest":
        stored_file_url = getattr(doc, field_to_check)
        if not stored_file_url:
            frappe.throw(_("Admit Card not yet generated. Please login to generate it."), frappe.PermissionError)
    else:
        from slcm.admission.doctype.entrance_test_list.entrance_test_list import generate_and_store_admit_card
        stored_file_url = generate_and_store_admit_card(doc.name, is_rescheduled=is_rescheduled)
        if stored_file_url:
            doc.reload()

    if stored_file_url:
        # Redirect to the public file URL for direct download
        frappe.local.response.type = "redirect"
        frappe.local.response.location = stored_file_url
    else:
        frappe.throw(_("Admit Card generation failed. Please contact the admission office."))

def get_admit_card_html(doc, is_rescheduled):
    """
    EXACT port of generate_admit_card_pdf template from Desk JS.
    """
    def esc(v): return escape_html(str(v if v is not None else ""))
    def val(v): return esc(v) if (v and str(v).strip() != "") else "—"

    admit_no = doc.admit_card_number or ("AC-" + doc.name)

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

    # Pick fields based on is_rescheduled
    f_date = doc.re_allocation_date if is_rescheduled else doc.allocation_date
    f_test = (doc.re_entrance_test_name or doc.re_entrance_test_list) if is_rescheduled else (doc.entrance_test_name or doc.entrance_test_list)
    f_seat = doc.re_seat_number if is_rescheduled else doc.seat_number
    f_room = doc.re_room_name if is_rescheduled else doc.room_name
    f_code = doc.re_room_code if is_rescheduled else doc.room_code
    f_building = doc.re_building if is_rescheduled else doc.building
    f_floor = doc.re_floor if is_rescheduled else doc.floor
    f_center = doc.re_center_name if is_rescheduled else doc.center_name
    f_address = doc.re_center_address if is_rescheduled else doc.center_address
    f_status = doc.re_allocation_status if is_rescheduled else doc.allocation_status

    alloc_date = "—"
    if f_date:
        try: alloc_date = formatdate(f_date)
        except: alloc_date = str(f_date)

    dob = formatdate(doc.date_of_birth) if doc.date_of_birth else "—"
    issue_date = formatdate(nowdate())

    exam_date_time = f"{alloc_date} &nbsp;|&nbsp; As per schedule" if alloc_date != "—" else "As per schedule"

    profile_image_url = get_base64_img(doc.profile)

    campus_display_name = doc.campus or "Institution of Legal Education"
    campus_logo_url = None
    try:
        campus = frappe.get_doc("Campus", doc.campus)
        if campus.campus_name: campus_display_name = campus.campus_name
        if campus.logo: campus_logo_url = get_base64_img(campus.logo)
    except: pass

    centre_parts = [f_center, f_address]
    centre_full = ", ".join([esc(p) for p in centre_parts if p and p.strip()]) or "—"

    header_html = f"""
        <div class="header">
          <div class="logo-box">
            {f'<img src="{campus_logo_url}" alt="Campus Logo" style="max-width:100%;max-height:100%;object-fit:contain;">' if campus_logo_url else '<div class="logo-inner"><span class="logo-icon">⚖</span><span class="logo-text">LAW<br>SCHOOL</span></div>'}
          </div>
          <div class="hdr-center">
            <div class="univ-name">{esc(campus_display_name)}</div>
            <div class="univ-sub">OFFICE OF ADMISSIONS &nbsp;&middot;&nbsp; EXAMINATION CELL</div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Admit Card - {esc(admit_no)}</title>
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
.seat-pill {{
  display: inline-block; background: #1a237e; color: #fff; font-weight: bold;
  font-family: Arial, sans-serif; font-size: 13px; padding: 2px 14px; border-radius: 2px; letter-spacing: 1px;
}}
.status-pill {{
  display: inline-block; border: 1px solid #4caf50; color: #1b5e20; background: #f0fdf0;
  font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; padding: 1px 10px; border-radius: 30px;
}}
.photo-col {{ width: 140px; flex-shrink: 0; border-left: 1.5px solid #888; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding: 10px 8px; gap: 8px; }}
.photo-frame {{ width: 120px; height: 150px; border: 2px solid #555; overflow: hidden; background: #eee; display: block; }}
.photo-frame img {{ width: 120px; height: 150px; display: block; max-width: none !important; }}
.photo-ph {{ font-size: 36px; color: #aaa; text-align: center; line-height: 150px; }}
.photo-cap {{
  font-size: 9.5px; font-family: Arial, sans-serif; color: #555; text-align: center; font-style: italic; line-height: 1.3;
}}
.sig-note {{ text-align: center; font-style: italic; font-size: 11.5px; font-family: "Times New Roman", Times, serif; padding: 6px 14px 3px; color: #000; }}
.sig-tbl {{ border-collapse: collapse; width: calc(100% - 28px); margin: 0 14px 16px; border: 1.5px solid #888; }}
.sig-tbl td {{ border: 1.5px solid #888; padding: 0; width: 50%; }}
.sig-cell-inner {{ display: flex; flex-direction: column; }}
.sig-hdr {{ font-weight: bold; font-family: Arial, sans-serif; font-size: 12px; color: #000; text-align: center; padding: 5px 8px 4px; border-bottom: 1.5px solid #888; display: block; }}
.sig-body {{ height: 54px; display: block; }}
.inst-outer {{ border: 1.5px solid #888; margin: 12px 14px 16px; padding: 14px 18px 18px; }}
.inst-main-title {{ font-size: 13.5px; font-weight: bold; font-family: Arial, sans-serif; text-align: center; color: #000; margin-bottom: 10px; }}
.sec-title {{ font-size: 12.5px; font-weight: bold; font-family: Arial, sans-serif; color: #000; margin: 10px 0 3px; }}
.il {{ list-style: none; margin: 0; padding: 0; }}
.il > li {{ display: flex; gap: 6px; font-size: 11.5px; font-family: Arial, sans-serif; color: #000; line-height: 1.65; padding-left: 18px; }}
.il > li .mk {{ flex-shrink: 0; min-width: 16px; }}
.sl {{ list-style: none; margin: 2px 0 2px 52px; padding: 0; }}
.sl li {{
  display: flex; gap: 6px; font-size: 11.5px; font-family: Arial, sans-serif; color: #000; line-height: 1.65;
}}
.sl li .mk {{ flex-shrink: 0; min-width: 22px; font-style: italic; }}
.pg-footer {{ padding: 6px 14px 10px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #ddd; }}
.pg-footer span {{ font-size: 8.5px; font-family: Arial, sans-serif; color: #888; }}
@media print {{ body {{ background: #fff; margin: 0; }} .card-page {{ width: 100%; margin: 0; border: 1.5px solid #555; }} }}
</style>
</head>
<body>
<div class="card-page p1">
  {header_html}
  <div class="title-row">
    <div class="t1">Admit Card ({val(f_test)})</div>
    <div class="t2">Admission to {val(doc.program_level) if doc.program_level else "the Programme"} &nbsp;|&nbsp; {val(doc.academic_year)} &nbsp;|&nbsp; {val(doc.admission_cycle)}</div>
  </div>
  <div class="info-wrap">
    <table class="info-tbl">
      <tbody>
        <tr><td class="lb">Admit Card Number</td><td class="sp">:</td><td class="vl"><strong>{val(admit_no)}</strong></td></tr>
        <tr><td class="lb">Candidate's Name</td><td class="sp">:</td><td class="vl">{val(doc.candidate_name)}</td></tr>
        <tr><td class="lb">Date of Birth</td><td class="sp">:</td><td class="vl">{val(dob)}</td></tr>
        <tr><td class="lb">Father's Name</td><td class="sp">:</td><td class="vl">{val(doc.father_name)}</td></tr>
        <tr><td class="lb">Mother's Name</td><td class="sp">:</td><td class="vl">{val(doc.mother_name)}</td></tr>
        <tr><td class="lb">Gender</td><td class="sp">:</td><td class="vl">{val(doc.gender)}</td></tr>
        <tr><td class="lb">Programme Applied</td><td class="sp">:</td><td class="vl">{val(doc.program)}</td></tr>
        <tr><td class="lb">Application Number</td><td class="sp">:</td><td class="vl">{val(doc.applicant)}</td></tr>
        <tr><td class="lb">Examination Date &amp; Time</td><td class="sp">:</td><td class="vl">{exam_date_time}</td></tr>
        <tr><td class="lb">Reporting Time</td><td class="sp">:</td><td class="vl">30 minutes before scheduled time</td></tr>
        <tr><td class="lb">Seat Number</td><td class="sp">:</td><td class="vl"><span class="seat-pill">{val(f_seat)}</span></td></tr>
        <tr><td class="lb">Room / Hall</td><td class="sp">:</td><td class="vl">{val(f_room)}{f'&nbsp; (Code:&nbsp;{esc(f_code)})' if f_code and f_code.strip() else ""}</td></tr>
        <tr><td class="lb">Building / Floor</td><td class="sp">:</td><td class="vl">{val(f_building)}{f'&nbsp; &middot;&nbsp; Floor:&nbsp;{esc(f_floor)}' if f_floor and f_floor.strip() else ""}</td></tr>
        <tr><td class="lb">Allocation Status</td><td class="sp">:</td><td class="vl"><span class="status-pill">{val(f_status)}</span></td></tr>
        <tr><td class="lb">Test Centre Name &amp;&nbsp;Address</td><td class="sp">:</td><td class="vl" style="font-size:11.5px;">{centre_full}</td></tr>
      </tbody>
    </table>
    <div class="photo-col">
      <div class="photo-frame">
        {f'<img src="{profile_image_url}" alt="Candidate Photo">' if profile_image_url else '<div class="photo-ph">👤</div>'}
      </div>
      <div class="photo-cap">Candidate's Photograph</div>
      <div class="photo-gap"></div>
    </div>
  </div>
  <div class="sig-note">To be signed in the presence of the Invigilator in the Examination Hall</div>
  <table class="sig-tbl">
    <tr>
      <td><div class="sig-cell-inner"><span class="sig-hdr">Candidate's Signature</span><span class="sig-body"></span></div></td>
      <td><div class="sig-cell-inner"><span class="sig-hdr">Invigilator's Signature</span><span class="sig-body"></span></div></td>
    </tr>
  </table>
</div>
<div class="card-page p2">
  <div class="inst-outer">
    <div class="inst-main-title">Instructions to Candidates</div>
    <div class="sec-title">1.&nbsp;&nbsp; General Instructions</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>Candidates should check and review their admit cards carefully and make sure that their Name, Date of Birth, and other personal details mentioned in the admit card are as per the details filled by them in the application form. In case of any discrepancy, please contact the Examination Cell immediately.</span></li>
      <li><span class="mk">b.</span><span>Please carry a printed copy of this admit card to the test centre.</span></li>
    </ul>
    <div class="sec-title">2.&nbsp;&nbsp; Reporting to the Test Centre &amp; Test Timings</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>Candidates will be allowed to enter the premises of the test centre 30 minutes before the examination start time and should be seated in the examination hall at least 15 minutes before commencement.</span></li>
      <li><span class="mk">b.</span><span>Candidates should carry a Government-issued photo ID card, preferably the one uploaded with the application form. The ID card will be checked at the time of entry into the centre.</span></li>
      <li><span class="mk">c.</span><span>Candidates who arrive at the test centre beyond the scheduled entry cut-off time will not be permitted entry.</span></li>
      <li><span class="mk">d.</span><span>Once the test commences, Candidates will not be permitted to leave the examination hall until the test is completed, and all the Question Booklets and OMR response sheets have been collected by the invigilator/s.</span></li>
    </ul>
    <div class="sec-title">3.&nbsp;&nbsp; Pre-Test Instructions</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>Candidates shall be required to follow all directions issued by the Centre Coordinators and the Institution representatives at their respective test centres.</span></li>
      <li><span class="mk">b.</span><span>Candidates must maintain all protocols in place at their respective test centres.</span></li>
    </ul>
    <div class="sec-title">4.&nbsp;&nbsp; Permitted Items</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>Candidates will only be permitted to carry the following inside the Test Centre:</span></li>
    </ul>
    <ul class="sl">
      <li><span class="mk">i.</span><span>Admit Card (In case the photograph on the Admit Card is not clear, candidates should carry a self-attested passport size photograph).</span></li>
      <li><span class="mk">ii.</span><span>Government Issued Photo ID (preferably the one uploaded with the application form).</span></li>
      <li><span class="mk">iii.</span><span>Black or Blue Ballpoint pen.</span></li>
      <li><span class="mk">iv.</span><span>A transparent water bottle.</span></li>
      <li><span class="mk">v.</span><span>A face mask (the Candidate may be asked to remove the face mask for ascertainment of identity).</span></li>
      <li><span class="mk">vi.</span><span>An analogue watch. <strong>Note:</strong> Smart Watches are not permitted.</span></li>
    </ul>
    <div class="sec-title">5.&nbsp;&nbsp; Admissions Test Related Instructions</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>An attendance sheet will be circulated during the admissions test. The requisite details should be filled in the attendance sheet.</span></li>
      <li><span class="mk">b.</span><span>Candidates will be provided with a Question Booklet and/or answer sheets. Candidates should use black/blue ball point pen <strong>only</strong> to enter the admit card number and other required details.</span></li>
      <li><span class="mk">c.</span><span>Candidates must read the instructions provided with the Question Booklet before commencing the test.</span></li>
      <li><span class="mk">d.</span><span>Candidates should write the details required on the cover page of the Question Booklet.</span></li>
      <li><span class="mk">e.</span><span>No clarifications can be sought about the Question Booklet from anyone.</span></li>
      <li><span class="mk">f.</span><span>Candidates shall not carry the Question Booklet out of the examination hall under any circumstances.</span></li>
    </ul>
    <div class="sec-title">6.&nbsp;&nbsp; Documents to be retained by the Candidate after the test</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>The admit card, with the invigilator's signature, should be retained by the candidate and produced at the Institution at the time of admission.</span></li>
    </ul>
    <div class="sec-title">7.&nbsp;&nbsp; Malpractice</div>
    <ul class="il">
      <li><span class="mk">a.</span><span>The use of any unfair means by a Candidate shall result in their disqualification and cancellation of their test.</span></li>
      <li><span class="mk">b.</span><span>Impersonation is an offence, and the Candidate, apart from being disqualified, shall be liable to penal action under the law.</span></li>
      <li><span class="mk">c.</span><span>Possession of electronic devices, including mobile phones, headphones, earphones, smart watches, calculators etc., is strictly prohibited in the examination hall.</span></li>
    </ul>
  </div>
  <div class="pg-footer">
    <span>Doc: <strong>{val(doc.name)}</strong> &nbsp;·&nbsp; Generated: <strong>{val(issue_date)}</strong> &nbsp;·&nbsp; System-generated. No physical signature required.</span>
    <span>{val(admit_no)}</span>
  </div>
</div>
</body>
</html>"""
    return html
