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
    # Branding & JSON for client-side generation
    campus_branding = {"campus_name": doc.campus or "Institution of Legal Education", "logo": None}
    try:
        if doc.campus:
            campus = frappe.get_doc("Campus", doc.campus)
            campus_branding["campus_name"] = campus.campus_name or doc.campus
            campus_branding["logo"] = campus.logo
    except: pass
    context.campus_branding = campus_branding
    context.doc_json = frappe.as_json(doc.as_dict())
    
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

    field_to_check = "re_admit_card_download" if is_rescheduled else "admit_card_download"

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
    Optimized Admit Card template for A4 single-page rendering.
    Restores original P2 content while perfecting P1.
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

    # Resolve fields
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

    alloc_date = formatdate(f_date) if f_date else "—"
    dob = formatdate(doc.date_of_birth) if doc.date_of_birth else "—"
    issue_date = formatdate(nowdate())

    profile_image_url = get_base64_img(doc.profile)
    campus_display_name = doc.campus or "Institution of Legal Education"
    campus_logo_url = None
    try:
        campus = frappe.get_doc("Campus", doc.campus)
        if campus.campus_name: campus_display_name = campus.campus_name
        if campus.logo: campus_logo_url = get_base64_img(campus.logo)
    except: pass

    # Reporting time calculation (1 hour before exam)
    from datetime import timedelta
    rep_time_str = "09:30 AM"
    if f_date:
        try:
            rep_dt = f_date - timedelta(hours=1)
            rep_time_str = format_datetime(rep_dt, "hh:mm a")
        except: pass

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
    @page {{
        size: A4;
        margin: 0;
    }}
    body {{
        font-family: Arial, sans-serif;
        font-size: 11px;
        color: #000;
        margin: 0;
        padding: 0;
        background: #fff;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }}
    .p1-container {{
        width: 210mm;
        height: 297mm;
        padding: 8mm;
        box-sizing: border-box;
        position: relative;
        background: #fff;
    }}
    .outer-page-border {{
        border: 2px solid #333;
        width: 100%;
        height: 100%;
        box-sizing: border-box;
        position: relative;
    }}
    .header-table {{
        width: 100%;
        background: #7b1c1c;
        color: #fff;
        border-collapse: collapse;
    }}
    .header-table td {{
        padding: 12px 15px;
        vertical-align: middle;
    }}
    .logo-container {{
        width: 65px;
        height: 65px;
        background: #fff;
        border-radius: 4px;
        text-align: center;
        overflow: hidden;
    }}
    .logo-container img {{
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }}
    .univ-info {{
        text-align: center;
    }}
    .univ-name {{
        font-size: 20px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 2px;
    }}
    .univ-sub {{
        font-size: 11px;
        opacity: 0.9;
        letter-spacing: 1.5px;
    }}
    .title-banner {{
        background: #f1f1f1;
        text-align: center;
        padding: 8px;
        border-bottom: 1.5px solid #333;
        font-weight: bold;
        font-size: 13.5px;
        text-transform: uppercase;
    }}
    .section-title {{
        background: #f5f5f5;
        padding: 5px 12px;
        font-weight: bold;
        font-size: 11.5px;
        border-top: 1px solid #333;
        border-bottom: 1px solid #333;
        color: #000;
    }}
    .data-table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .data-table td {{
        padding: 6px 12px;
        border-bottom: 1px solid #eee;
        vertical-align: top;
        font-size: 11px;
    }}
    .label {{
        font-weight: bold;
        color: #333;
        width: 38%;
    }}
    .value {{
        color: #000;
    }}
    .photo-cell {{
        width: 140px;
        text-align: center;
        padding: 12px;
        border-left: 1.5px solid #333;
        vertical-align: top;
    }}
    .photo-frame {{
        width: 115px;
        height: 140px;
        border: 1px solid #333;
        margin: 0 auto 5px;
        background: #fdfdfd;
        overflow: hidden;
    }}
    .photo-frame img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
    }}
    .photo-cap {{
        font-size: 9.5px;
        font-style: italic;
        color: #555;
    }}
    .pill {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 2px;
        font-weight: bold;
        font-size: 11px;
    }}
    .pill-seat {{ background: #002e5b; color: #fff; }}
    .pill-status {{ border: 1px solid #28a745; color: #155724; background: #d4edda; }}

    .signature-area {{
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        border-top: 2px solid #333;
        background: #fff;
    }}
    .sig-table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .sig-table td {{
        width: 50%;
        height: 75px;
        border-right: 1.5px solid #333;
        padding: 8px;
        text-align: center;
        vertical-align: bottom;
        font-size: 11px;
        font-weight: bold;
    }}
    .sig-table td:last-child {{
        border-right: none;
    }}
    .sig-note {{
        text-align: center;
        font-style: italic;
        font-size: 11px;
        padding: 6px;
        border-top: 1px solid #eee;
    }}
    .footer-note {{
        font-size: 9px;
        color: #666;
        padding: 6px 12px;
        border-top: 1px solid #eee;
    }}

    /* ── ORIGINAL P2 STYLES ────────────────────────────────────── */
    .p2-container {{
        width: 210mm;
        height: 297mm;
        background: #fff;
        page-break-before: always;
        padding: 10mm;
        box-sizing: border-box;
    }}
    .card-page.p2 {{
        width: 100%;
        height: 100%;
        border: 1.5px solid #555;
        box-sizing: border-box;
        display: block;
        position: relative;
    }}
    .inst-outer {{ border: 1.5px solid #888; margin: 12px 14px 16px; padding: 14px 18px 18px; }}
    .inst-main-title {{ font-size: 13.5px; font-weight: bold; font-family: Arial, sans-serif; text-align: center; color: #000; margin-bottom: 10px; }}
    .p2-sec-title {{ font-size: 12.5px; font-weight: bold; font-family: Arial, sans-serif; color: #000; margin: 10px 0 3px; }}
    .il {{ list-style: none; margin: 0; padding: 0; }}
    .il > li {{ display: flex; gap: 6px; font-size: 11.5px; font-family: Arial, sans-serif; color: #000; line-height: 1.65; padding-left: 18px; }}
    .il > li .mk {{ flex-shrink: 0; min-width: 16px; font-weight: bold; }}
    .sl {{ list-style: none; margin: 2px 0 2px 52px; padding: 0; }}
    .sl li {{ display: flex; gap: 6px; font-size: 11.5px; font-family: Arial, sans-serif; color: #000; line-height: 1.65; }}
    .sl li .mk {{ flex-shrink: 0; min-width: 22px; font-style: italic; font-weight: bold; }}
    .pg-footer {{ padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #ddd; position: absolute; bottom: 0; width: 100%; box-sizing: border-box; }}
    .pg-footer span {{ font-size: 8.5px; font-family: Arial, sans-serif; color: #888; }}
</style>
</head>
<body>
    <!-- Page 1: Admit Card -->
    <div class="p1-container">
        <div class="outer-page-border">
            <table class="header-table">
                <tr>
                    <td style="width: 80px;">
                        <div class="logo-container">
                            {f'<img src="{campus_logo_url}" />' if campus_logo_url else '<div style="font-size:32px;line-height:65px;color:#7b1c1c;">⚖</div>'}
                        </div>
                    </td>
                    <td>
                        <div class="univ-info">
                            <div class="univ-name">{esc(campus_display_name)}</div>
                            <div class="univ-sub">OFFICE OF ADMISSIONS & EXAMINATION CELL</div>
                        </div>
                    </td>
                </tr>
            </table>

            <div class="title-banner">ADMIT CARD - {esc(admit_no)}</div>

            <table style="width:100%; border-collapse: collapse;">
                <tr>
                    <td style="vertical-align: top;">
                        <!-- Candidate Information -->
                        <div class="section-title">Candidate Information</div>
                        <table class="data-table">
                            <tr><td class="label">Candidate Name</td><td class="value"><strong>{val(doc.candidate_name)}</strong></td></tr>
                            <tr><td class="label">Date of Birth</td><td class="value">{val(dob)}</td></tr>
                            <tr><td class="label">Father's Name</td><td class="value">{val(doc.father_name)}</td></tr>
                            <tr><td class="label">Mother's Name</td><td class="value">{val(doc.mother_name)}</td></tr>
                            <tr><td class="label">Gender</td><td class="value">{val(doc.gender)}</td></tr>
                        </table>

                        <!-- Application Details -->
                        <div class="section-title">Application Details</div>
                        <table class="data-table">
                            <tr><td class="label">Programme Applied</td><td class="value"><strong>{val(doc.program)}</strong></td></tr>
                            <tr><td class="label">Application Number</td><td class="value">{val(doc.applicant)}</td></tr>
                            <tr><td class="label">Academic Year</td><td class="value">{val(doc.academic_year)}</td></tr>
                            <tr><td class="label">Admission Cycle</td><td class="value">{val(doc.admission_cycle)}</td></tr>
                        </table>
                    </td>
                    <td class="photo-cell">
                        <div class="photo-frame">
                            {f'<img src="{profile_image_url}" />' if profile_image_url else '<div style="font-size:60px; color:#ccc; margin-top:35px;">👤</div>'}
                        </div>
                        <div class="photo-cap">Candidate's Photograph</div>
                    </td>
                </tr>
            </table>

            <!-- Examination Details -->
            <div class="section-title">Examination Details</div>
            <table class="data-table">
                <tr><td class="label">Entrance Test</td><td class="value"><strong>{val(f_test)}</strong></td></tr>
                <tr><td class="label">Examination Date</td><td class="value"><strong>{alloc_date}</strong></td></tr>
                <tr><td class="label">Examination Time</td><td class="value">As per center schedule</td></tr>
                <tr><td class="label">Reporting Time</td><td class="value">{rep_time_str} (30 mins before start)</td></tr>
            </table>

            <!-- Seat & Venue Details -->
            <div class="section-title">Seat & Venue Details</div>
            <table class="data-table">
                <tr><td class="label">Seat Number</td><td class="value"><span class="pill pill-seat">{val(f_seat)}</span></td></tr>
                <tr><td class="label">Room / Hall</td><td class="value">{val(f_room)}{f' (Code: {esc(f_code)})' if f_code and f_code.strip() else ""}</td></tr>
                <tr><td class="label">Building / Floor</td><td class="value">{val(f_building)}{f' - Floor: {esc(f_floor)}' if f_floor and f_floor.strip() else ""}</td></tr>
                <tr><td class="label">Examination Venue</td><td class="value"><strong>{val(f_center)}</strong><br/><span style="font-size:10px; color: #444;">{val(f_address)}</span></td></tr>
                <tr><td class="label">Allocation Status</td><td class="value"><span class="pill pill-status">{val(f_status)}</span></td></tr>
            </table>

            <div style="padding: 15px; font-size: 11px; color: #444; line-height: 1.4;">
                <strong>Note:</strong> Please bring a printed copy of this admit card along with a valid Government-issued Photo ID proof (Aadhar, PAN, Passport, etc.) to the examination center. No candidate will be allowed entry without these documents.
            </div>

            <div class="signature-area">
                <div class="sig-note">To be signed in the presence of the Invigilator at the Examination Hall</div>
                <table class="sig-table">
                    <tr>
                        <td>Candidate's Signature</td>
                        <td>Invigilator's Signature</td>
                    </tr>
                </table>
                <div class="footer-note">
                    Ref ID: {esc(doc.name)} &nbsp;|&nbsp; Generated: {esc(issue_date)} &nbsp;|&nbsp; System Generated. No physical signature required.
                </div>
            </div>
        </div>
    </div>

    <!-- Page 2: Instructions (ORIGINAL RESTORED) -->
    <div class="p2-container">
        <div class="card-page p2">
            <div class="inst-outer">
                <div class="inst-main-title">Instructions to Candidates</div>
                <div class="p2-sec-title">1.&nbsp;&nbsp; General Instructions</div>
                <ul class="il">
                <li><span class="mk">a.</span><span>Candidates should check and review their admit cards carefully and make sure that their Name, Date of Birth, and other personal details mentioned in the admit card are as per the details filled by them in the application form. In case of any discrepancy, please contact the Examination Cell immediately.</span></li>
                <li><span class="mk">b.</span><span>Please carry a printed copy of this admit card to the test centre.</span></li>
                </ul>
                <div class="p2-sec-title">2.&nbsp;&nbsp; Reporting to the Test Centre &amp; Test Timings</div>
                <ul class="il">
                <li><span class="mk">a.</span><span>Candidates will be allowed to enter the premises of the test centre 30 minutes before the examination start time and should be seated in the examination hall at least 15 minutes before commencement.</span></li>
                <li><span class="mk">b.</span><span>Candidates should carry a Government-issued photo ID card, preferably the one uploaded with the application form. The ID card will be checked at the time of entry into the centre.</span></li>
                <li><span class="mk">c.</span><span>Candidates who arrive at the test centre beyond the scheduled entry cut-off time will not be permitted entry.</span></li>
                <li><span class="mk">d.</span><span>Once the test commences, Candidates will not be permitted to leave the examination hall until the test is completed, and all the Question Booklets and OMR response sheets have been collected by the invigilator/s.</span></li>
                </ul>
                <div class="p2-sec-title">3.&nbsp;&nbsp; Pre-Test Instructions</div>
                <ul class="il">
                <li><span class="mk">a.</span><span>Candidates shall be required to follow all directions issued by the Centre Coordinators and the Institution representatives at their respective test centres.</span></li>
                <li><span class="mk">b.</span><span>Candidates must maintain all protocols in place at their respective test centres.</span></li>
                </ul>
                <div class="p2-sec-title">4.&nbsp;&nbsp; Permitted Items</div>
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
                <div class="p2-sec-title">5.&nbsp;&nbsp; Admissions Test Related Instructions</div>
                <ul class="il">
                <li><span class="mk">a.</span><span>An attendance sheet will be circulated during the admissions test. The requisite details should be filled in the attendance sheet.</span></li>
                <li><span class="mk">b.</span><span>Candidates will be provided with a Question Booklet and/or answer sheets. Candidates should use black/blue ball point pen <strong>only</strong> to enter the admit card number and other required details.</span></li>
                <li><span class="mk">c.</span><span>Candidates must read the instructions provided with the Question Booklet before commencing the test.</span></li>
                <li><span class="mk">d.</span><span>Candidates should write the details required on the cover page of the Question Booklet.</span></li>
                <li><span class="mk">e.</span><span>No clarifications can be sought about the Question Booklet from anyone.</span></li>
                <li><span class="mk">f.</span><span>Candidates shall not carry the Question Booklet out of the examination hall under any circumstances.</span></li>
                </ul>
                <div class="p2-sec-title">6.&nbsp;&nbsp; Documents to be retained by the Candidate after the test</div>
                <ul class="il">
                <li><span class="mk">a.</span><span>The admit card, with the invigilator's signature, should be retained by the candidate and produced at the Institution at the time of admission.</span></li>
                </ul>
                <div class="p2-sec-title">7.&nbsp;&nbsp; Malpractice</div>
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
    </div>
</body>
</html>"""
    return html
