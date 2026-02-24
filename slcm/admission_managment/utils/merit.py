import frappe
from frappe.utils import now

def generate_merit_list(cycle, program, campus):
    preferences = frappe.get_all(
        "Applicant Campus Preference",
        filters={
            "admission_cycle": cycle,
            "campus": campus,
            "program": program
        },
        fields=["applicant", "clat_rank", "nlsat_score",
                "interview_score", "workflow_type"],
        order_by="clat_rank asc, nlsat_score desc"
    )
    entries = []
    for idx, pref in enumerate(preferences, 1):
        applicant = frappe.get_doc("Applicant", pref.applicant)
        entries.append({
            "rank": idx,
            "applicant": pref.applicant,
            "candidate_name": applicant.candidate_name,
            "category": applicant.reservation_category,
            "score": pref.nlsat_score or 0,
            "clat_rank": pref.clat_rank or 0,
            "status": "Listed"
        })
    return entries

def publish_merit_list(merit_list_name):
    doc = frappe.get_doc("Merit List", merit_list_name)
    if doc.is_published:
        frappe.throw("Merit List is already published.")
    doc.submit()
    return doc.name

def export_merit_list_pdf(merit_list_name):
    url = frappe.utils.get_url(
        f"/api/method/frappe.utils.print_format.download_pdf"
        f"?doctype=Merit List&name={merit_list_name}&format=Standard"
    )
    return url
