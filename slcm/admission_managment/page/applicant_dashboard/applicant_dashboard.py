import frappe
from frappe import _

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to view your dashboard"), frappe.PermissionError)
    context.no_cache = 1
    applicant = get_applicant_data()
    if not applicant:
        context.no_application = True
        return
    context.applicant = applicant
    context.campus_status = get_campus_status(applicant.name)
    context.pending_actions = get_pending_actions(applicant)
    context.documents = get_document_status(applicant.name)
    context.deadlines = get_active_deadlines(applicant.admission_cycle)
    context.completion = get_completion_percentage(applicant)

def get_applicant_data():
    applicant = frappe.db.get_value(
        "Applicant",
        {"email": frappe.session.user},
        ["name", "application_id", "candidate_name", "application_status",
         "application_type", "program", "campus", "admission_cycle",
         "first_preference", "second_preference", "third_preference",
         "reservation_category", "docstatus"],
        as_dict=True
    )
    return applicant

def get_campus_status(applicant_name):
    return frappe.get_all(
        "Applicant Campus Preference",
        filters={"applicant": applicant_name},
        fields=["campus", "preference_order", "status",
               "offer_date", "acceptance_deadline", "program"],
        order_by="preference_order asc"
    )

def get_pending_actions(applicant):
    actions = []
    if applicant.docstatus == 0:
        actions.append({
            "action": "Complete Application",
            "description": "Your application is not yet submitted",
            "url": f"/app/applicant/{applicant.name}",
            "type": "warning",
            "icon": "edit"
        })
    unverified_docs = frappe.db.count(
        "Applicant Document",
        {"applicant": applicant.name, "is_verified": 0, "docstatus": 1}
    )
    if unverified_docs:
        actions.append({
            "action": "Documents Pending Verification",
            "description": f"{unverified_docs} document(s) awaiting verification",
            "url": f"/app/applicant-document?applicant={applicant.name}",
            "type": "info",
            "icon": "file"
        })
    offered = frappe.db.exists(
        "Applicant Campus Preference",
        {"applicant": applicant.name, "status": "Offered"}
    )
    if offered:
        actions.append({
            "action": "Accept Offer",
            "description": "You have a pending offer. Accept before deadline.",
            "url": f"/app/applicant-campus-preference?applicant={applicant.name}",
            "type": "success",
            "icon": "check-circle"
        })
    interview = frappe.db.exists(
        "Applicant Campus Preference",
        {"applicant": applicant.name, "status": "Interview Scheduled"}
    )
    if interview:
        actions.append({
            "action": "Interview Scheduled",
            "description": "You have an interview scheduled. Check details.",
            "url": f"/app/applicant-campus-preference?applicant={applicant.name}",
            "type": "primary",
            "icon": "calendar"
        })
    return actions

def get_document_status(applicant_name):
    applicant = frappe.get_doc("Applicant", applicant_name)
    from slcm.admission_managment.utils.documents import get_required_documents
    required = get_required_documents(
        applicant.program,
        applicant.reservation_category
    )
    uploaded = frappe.get_all(
        "Applicant Document",
        filters={"applicant": applicant_name},
        fields=["document_type", "is_verified", "is_locked", "file"]
    )
    uploaded_map = {d.document_type: d for d in uploaded}
    result = []
    for doc_type in required:
        uploaded_doc = uploaded_map.get(doc_type)
        result.append({
            "document_type": doc_type,
            "uploaded": bool(uploaded_doc),
            "verified": uploaded_doc.is_verified if uploaded_doc else False,
            "locked": uploaded_doc.is_locked if uploaded_doc else False
        })
    return result

def get_active_deadlines(admission_cycle):
    if not admission_cycle:
        return []
    return frappe.get_all(
        "Admission Round",
        filters={
            "admission_cycle": admission_cycle,
            "status": ["in", ["Active", "Upcoming"]]
        },
        fields=["round_name", "round_type",
               "application_end", "status"],
        order_by="application_end asc"
    )

def get_completion_percentage(applicant):
    fields = [
        "candidate_name", "email", "mobile_number",
        "date_of_birth", "gender", "correspondence_address",
        "class_x_percentage", "class_xii_percentage",
        "first_preference", "declaration_undertaking",
        "id_proof", "candidate_photo"
    ]
    filled = sum(1 for f in fields if getattr(applicant, f, None))
    return round((filled / len(fields)) * 100)
