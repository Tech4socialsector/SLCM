import frappe
from frappe.utils import now, getdate, today, add_days
from slcm.admission.utils.regulatory import log_audit_trail

def on_applicant_submit(doc, method):
    log_audit_trail(
        doc.doctype, doc.name,
        "Submitted", "application_status",
        "Draft", "Submitted", "General"
    )
    frappe.sendmail(
        recipients=[doc.email],
        subject=f"Application Submitted - {doc.application_id}",
        message=f"""
        Dear {doc.candidate_name},<br><br>
        Your NLSIU application <b>{doc.application_id}</b> has been submitted.<br>
        Program: {doc.program}<br>
        Application Type: {doc.application_type}<br><br>
        You will be notified of further updates through this
        email and your portal.<br><br>
        NLSIU Admissions Team
        """
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
    applicants = frappe.get_all(
        "Merit List Entry",
        {"parent": doc.name, "status": "Listed"},
        ["applicant"]
    )
    for entry in applicants:
        applicant = frappe.get_doc("Applicant", entry.applicant)
        frappe.sendmail(
            recipients=[applicant.email],
            subject=f"Merit List Published - {doc.program}",
            message=f"""
            Dear {applicant.candidate_name},<br><br>
            The merit list for <b>{doc.program}</b> at <b>{doc.campus}</b>
            has been published.<br>
            Please login to your portal to check your status.<br><br>
            NLSIU Admissions Team
            """
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
            frappe.sendmail(
                recipients=[applicant.email],
                subject=f"Deadline Reminder - {round_doc.round_name}",
                message=f"""
                Dear {applicant.candidate_name},<br><br>
                This is a reminder that the deadline for
                <b>{round_doc.round_name}</b> is tomorrow.<br>
                Please complete and submit your application
                before the deadline.<br><br>
                NLSIU Admissions Team
                """
            )