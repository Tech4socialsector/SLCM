import frappe
import math

@frappe.whitelist(allow_guest=True)
def get_pace_programmes():
    programmes = frappe.get_all('PACE Programme', fields=[
        'name', 'programme_name', 'programme_code', 'programme_prefix',
        'admission_status', 'show_overview_tab', 'overview as description',
        'duration', 'duration_type', 'banner_image as image_url', 'route'
    ], filters={'published': 1}, order_by='creation desc')
    
    for p in programmes:
        p['duration_label'] = f"{p.duration} {p.duration_type}" if p.duration and p.duration_type else ""
        
    return programmes

@frappe.whitelist(allow_guest=True)
def get_pace_faqs(faq_page=1):
    faq_page = int(faq_page)
    page_size = 10
    start = (faq_page - 1) * page_size
    
    faqs = frappe.get_all('PACE FAQs', fields=['question', 'answer'], order_by='creation desc', limit_start=start, limit_page_length=page_size)
    total_count = frappe.db.count('PACE FAQs')
    
    return {
        'success': True,
        'faqs': faqs,
        'faq_page': faq_page,
        'faq_total_pages': math.ceil(total_count / page_size) if total_count > 0 else 1
    }

@frappe.whitelist(allow_guest=True)
def get_pace_page_data():
    config = frappe.get_single('Applicant Portal Config')
    
    active_admission_data = frappe.db.get_value("PACE Admission", {"status": "Active", "docstatus": ["<", 2]}, ["name", "academic_year"], as_dict=True)
    academic_year = active_admission_data.academic_year if active_admission_data else ""
    if not academic_year:
        academic_year = frappe.db.get_value("Academic Year", {"status": "Active"}, "name") or ""
        
    hero_badge_text = f"Admission Open for {academic_year}" if academic_year else ""
    
    data = {
        'success': True,
        'show_ticker': config.show_ticker,
        'hero_background_image': config.hero_background_image,
        'hero_title': config.hero_title,
        'hero_subtitle': config.hero_subtitle,
        'hero_description': config.hero_description,
        'hero_cta_label': config.hero_cta_label,
        'hero_cta2_label': config.hero_cta2_label,
        'hero_badge_text': hero_badge_text,
        'ticker_items': [],
        'programmes': get_pace_programmes()
    }
    
    if config.show_ticker:
        data['ticker_items'] = frappe.get_all('PACE News Ticker', fields=['ticker_text', 'ticker_link', 'first_priority'], filters={'parent': 'Applicant Portal Config', 'parenttype': 'Applicant Portal Config'}, order_by='idx asc')
        
    faq_data = get_pace_faqs(1)
    data['faqs'] = faq_data.get('faqs', [])
    data['faq_total_pages'] = faq_data.get('faq_total_pages', 1)
    data['faq_page'] = 1
    
    return data

@frappe.whitelist(allow_guest=True)
def submit_pace_enquiry(full_name, email, phone, programme_of_interest):
    try:
        enquiry = frappe.get_doc({
            'doctype': 'PACE Enquiry',
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'programme_of_interest': programme_of_interest,
            'status': 'New'
        })
        enquiry.insert(ignore_permissions=True)
        return {"success": True, "message": "Enquiry submitted successfully"}
    except Exception as e:
        frappe.log_error("PACE Enquiry Submission Failed", str(e))
        return {"success": False, "message": "Failed to submit enquiry. Please try again later."}

@frappe.whitelist()
def get_user_pace_applications():
    if frappe.session.user == 'Guest':
        return []
    
    apps = frappe.get_all('PACE Application', fields=['name', 'programme', 'status'], filters={'owner': frappe.session.user}, order_by='creation desc')
    
    return apps
