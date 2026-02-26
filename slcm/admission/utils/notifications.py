import frappe
from frappe.utils import today, date_diff

def send_status_notification(applicant_name, new_status):
    applicant = frappe.get_doc("Applicant", applicant_name)
    subject_map = {
        "Submitted": "Application Submitted Successfully",
        "Under Evaluation": "Your Application is Under Evaluation",
        "Shortlisted": "Congratulations! You are Shortlisted",
        "Interview Scheduled": "Interview Scheduled - Action Required",
        "Offered": "Offer of Admission - Action Required",
        "Accepted": "Admission Confirmed",
        "Rejected": "Application Status Update",
        "Waitlisted": "You are on the Waitlist"
    }
    message_map = {
        "Submitted": f"""
            Your application <b>{applicant.application_id}</b>
            has been submitted successfully.<br>
            You will be notified of further updates.
        """,
        "Shortlisted": f"""
            Congratulations! Your application for <b>{applicant.program}</b>
            has been shortlisted.<br>
            Please login to your dashboard for next steps.
        """,
        "Interview Scheduled": f"""
            Your interview has been scheduled.<br>
            Please login to your dashboard to view interview details
            and confirm your attendance.
        """,
        "Offered": f"""
            You have received an offer of admission for
            <b>{applicant.program}</b>.<br>
            Please login to your dashboard to accept the offer
            before the deadline.
        """,
        "Accepted": f"""
            Your admission to <b>{applicant.program}</b>
            has been confirmed.<br>
            Please complete the fee payment and document
            verification process.
        """,
        "Rejected": f"""
            We regret to inform you that your application for
            <b>{applicant.program}</b> was not successful this time.<br>
            Thank you for applying to NLSIU.
        """,
        "Waitlisted": f"""
            You have been placed on the waitlist for
            <b>{applicant.program}</b>.<br>
            You will be notified if a seat becomes available.
        """
    }
    subject = subject_map.get(new_status, "Application Status Update")
    message = message_map.get(
        new_status, "Your application status has been updated."
    )
    try:
        frappe.sendmail(
            recipients=[applicant.email],
            subject=f"NLSIU Admissions | {subject}",
            message=f"""
            Dear {applicant.candidate_name},<br><br>
            {message}<br><br>
            <b>Application ID:</b> {applicant.application_id}<br>
            <b>Program:</b> {applicant.program}<br>
            <b>Status:</b> {new_status}<br><br>
            Login to your dashboard:
            <a href="/applicant-dashboard">Click Here</a><br><br>
            NLSIU Admissions Team<br>
            National Law School of India University
            """
        )
    except Exception as e:
        frappe.log_error(str(e), "Notification Error")

def send_offer_deadline_reminder(applicant_name, campus, days_left):
    applicant = frappe.get_doc("Applicant", applicant_name)
    try:
        frappe.sendmail(
            recipients=[applicant.email],
            subject=f"NLSIU | Offer Deadline Reminder - {days_left} day(s) left",
            message=f"""
            Dear {applicant.candidate_name},<br><br>
            This is a reminder that your admission offer for
            <b>{applicant.program}</b> at <b>{campus}</b>
            expires in <b>{days_left} day(s)</b>.<br><br>
            Please login immediately to accept your offer:
            <a href="/applicant-dashboard">Accept Offer</a><br><br>
            If you do not respond before the deadline, your offer
            will be automatically cancelled.<br><br>
            NLSIU Admissions Team
            """
        )
    except Exception as e:
        frappe.log_error(str(e), "Offer Reminder Error")

def send_document_reminder(applicant_name, missing_docs):
    applicant = frappe.get_doc("Applicant", applicant_name)
    doc_list = "".join([f"<li>{d}</li>" for d in missing_docs])
    try:
        frappe.sendmail(
            recipients=[applicant.email],
            subject="NLSIU | Documents Pending Upload",
            message=f"""
            Dear {applicant.candidate_name},<br><br>
            The following documents are still pending for your
            application <b>{applicant.application_id}</b>:<br>
            <ul>{doc_list}</ul>
            Please upload them immediately:
            <a href="/applicant-dashboard">Go to Dashboard</a><br><br>
            NLSIU Admissions Team
            """
        )
    except Exception as e:
        frappe.log_error(str(e), "Document Reminder Error")

def check_and_send_offer_reminders():
    offered_prefs = frappe.get_all(
        "Applicant Campus Preference",
        filters={"status": "Offered"},
        fields=["applicant", "campus", "acceptance_deadline"]
    )
    for pref in offered_prefs:
        if pref.acceptance_deadline:
            days_left = date_diff(pref.acceptance_deadline, today())
            if days_left in [3, 1]:
                send_offer_deadline_reminder(
                    pref.applicant, pref.campus, days_left
                )