import frappe
from frappe.utils import now, getdate, today, add_days
from slcm.admission.utils.regulatory import log_audit_trail
from slcm.admission.doctype.email_template_config.email_template_config import EmailTemplateConfig

def on_applicant_submit(doc, method):
    log_audit_trail(
        doc.doctype, doc.name,
        "Submitted", "application_status",
        "Draft", "Submitted", "General"
    )
    EmailTemplateConfig.send(
        trigger_event="Application Submitted",
        recipient_email=doc.email,
        context={
            "candidate_name": doc.candidate_name,
            "program": doc.program,
            "applicant_id": doc.applicant_id,
            "submission_date": now()
        }
    )

def on_applicant_cancel(doc, method):
    log_audit_trail(
        doc.doctype, doc.name,
        "Cancelled", "application_status",
        "Submitted", "Draft", "General"
    )

def on_document_submit(doc, method):
    log_audit_trail(
        doc.doctype, doc.name,
        "Submitted", "is_locked", 0, 1, "Document"
    )

def on_merit_list_publish(doc, method):
    log_audit_trail(
        doc.doctype, doc.name,
        "Submitted", "is_published", 0, 1, "Rank"
    )
    # Status changed trigger usually happens when merit list is published and status updated
    # But here we send a general update if applicants are listed
    applicants = frappe.get_all(
        "Merit List Applicant",
        {"parent": doc.name, "status": "Selected"},
        ["applicant_id"]
    )
    for entry in applicants:
        if not entry.applicant_id:
            continue
        applicant = frappe.get_doc("Applicant", entry.applicant_id)
        EmailTemplateConfig.send(
            trigger_event="Status Changed",
            recipient_email=applicant.email,
            context={
                "candidate_name": applicant.candidate_name,
                "program": applicant.program,
                "applicant_id": applicant.applicant_id,
                "status": "Listed in Merit List",
                "old_status": applicant.application_status,
                "campus": doc.campus
            }
        )

def on_seat_matrix_lock(doc, method):
    log_audit_trail(
        doc.doctype, doc.name,
        "Submitted", "is_locked", 0, 1, "Reservation"
    )

def auto_update_cycle_status():
    cycles = frappe.get_all(
        "Admission Cycle",
        filters={"status": ["!=", "Closed"]},
        fields=["name", "start_date", "end_date", "status"]
    )
    today_date = getdate(today())
    for cycle in cycles:
        new_status = "Draft"
        if getdate(cycle.start_date) <= today_date <= getdate(cycle.end_date):
            new_status = "Active"
        elif today_date > getdate(cycle.end_date):
            new_status = "Closed"
        if new_status != cycle.status:
            frappe.db.set_value(
                "Admission Cycle", cycle.name, "status", new_status
            )
            log_audit_trail(
                "Admission Cycle", cycle.name,
                "Modified", "status",
                cycle.status, new_status, "General"
            )
    frappe.db.commit()

def send_deadline_reminders():
    tomorrow = add_days(today(), 1)
    rounds = frappe.get_all(
        "Admission Round",
        {
            "status": "Active",
            "application_end": ["between", [today(), tomorrow]]
        },
        ["name", "round_name", "admission_cycle", "application_end"]
    )
    for round_doc in rounds:
        applicants = frappe.get_all(
            "Applicant",
            {
                "admission_cycle": round_doc.admission_cycle,
                "application_status": "Draft"
            },
            ["email", "candidate_name"]
        )
        for applicant in applicants:
            EmailTemplateConfig.send(
                trigger_event="Deadline Reminder",
                recipient_email=applicant.email,
                context={
                    "candidate_name": applicant.candidate_name,
                    "program": "your selected program",
                    "deadline": round_doc.application_end,
                    "action_required": "Application Submission"
                }
            )
