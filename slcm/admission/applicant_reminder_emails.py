"""
slcm/admission/applicant_reminder_emails.py
-------------------------------------------
Scheduled reminder email logic for the Admission module.

Scheduler entry (hooks.py  "0 10 * * *"):
    slcm.admission.applicant_reminder_emails.send_not_started_reminders
    slcm.admission.applicant_reminder_emails.send_draft_applicant_reminders
    slcm.admission.applicant_reminder_emails.send_unpaid_fee_reminders
"""

import traceback
import frappe
from frappe.utils import get_url, getdate, today, now_datetime, formatdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_active_cycle():
    """
    Returns (cycle_name, application_end_date) for the currently Active
    Admission Cycle, or (None, None) if none found.
    """
    cycle = frappe.db.get_value(
        "Admission Cycle",
        {"status": "Active"},
        ["name", "application_end_date"],
        as_dict=True,
    )
    if cycle:
        return cycle.name, cycle.application_end_date

    # Fallback: look for the most recently closed cycle
    cycle = frappe.db.get_value(
        "Admission Cycle",
        {"status": "Closed"},
        ["name", "application_end_date"],
        as_dict=True,
        order_by="application_end_date desc",
    )
    if cycle:
        return cycle.name, cycle.application_end_date

    return None, None


def _get_template_sender(template_name):
    """Resolves the sender email address from an Email Template's email_account."""
    if not template_name:
        return None
    email_account = frappe.db.get_value("Email Template", template_name, "email_account")
    if email_account:
        return frappe.db.get_value("Email Account", email_account, "email_id") or None
    return None


def _get_institution_name():
    try:
        return frappe.get_single("Institution Settings").institution_name or "NLSIU"
    except Exception:
        return "NLSIU"


def _send_email_from_template(template_name, recipient, args, reference_doctype=None, reference_name=None, now=False):
    """
    Renders and sends an email from a named Email Template.
    Returns (subject, success_bool).
    """
    if not frappe.db.exists("Email Template", template_name):
        frappe.log_error(f"Email Template '{template_name}' not found.", "Applicant Reminder Email Missing Template")
        return None, False

    tmpl = frappe.get_doc("Email Template", template_name)

    if "doc" not in args:
        args["doc"] = frappe._dict()

    try:
        subject = frappe.render_template(tmpl.subject or template_name, args)

        body = ""
        if tmpl.get("use_html") and tmpl.get("response_html"):
            body = frappe.render_template(tmpl.response_html, args)
        elif tmpl.get("response"):
            body = frappe.render_template(tmpl.response, args)

        if not body:
            body = frappe.render_template(tmpl.get("message") or "", args)

        if not body:
            return subject, False

        cc_list = []
        cc_val = tmpl.get("cc")
        if cc_val:
            cc_list = [c.strip() for c in cc_val.replace(";", ",").split(",") if c.strip()]

        frappe.sendmail(
            recipients=[recipient],
            sender=_get_template_sender(template_name),
            cc=cc_list,
            subject=subject,
            message=body,
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            now=now,
        )
        return subject, True

    except Exception:
        frappe.log_error(traceback.format_exc(), f"Applicant Reminder Send Error: {template_name} → {recipient}")
        return None, False


# ---------------------------------------------------------------------------
# 1. Not-Started Application Reminder
# ---------------------------------------------------------------------------

def send_not_started_reminders(current_item=0, total_items=0, is_rejection_only=False):
    """
    Sends reminders to users with role 'Applicant' who have NO Applicant record
    in the current active admission cycle.
    After application_end_date: disables the user's Applicant role (no application → no rejection record).
    """
    from slcm.admission.doctype.applicant_reminder_email_configuration.applicant_reminder_email_configuration import (
        should_send_reminder, get_rejection_reason,
    )
    from slcm.admission.doctype.applicant_reminder_email_log.applicant_reminder_email_log import (
        log_applicant_reminder_email,
    )

    cycle_name, cycle_end_date = _get_active_cycle()
    if not cycle_name or not cycle_end_date:
        return 0

    today_date = getdate(today())
    close_date = getdate(cycle_end_date)
    
    if is_rejection_only and today_date <= close_date:
        return 0

    # All users with Applicant role
    users = frappe.get_all("Has Role", filters={"role": "Applicant"}, fields=["parent"])
    user_emails = list(set([u.parent for u in users]))

    # Emails that already have at least one Applicant record
    existing = frappe.get_all(
        "Applicant",
        filters={"admission_cycle": cycle_name},
        fields=["user_id"],
        pluck="user_id",
    )
    existing_set = set(existing)

    already_rejected = frappe.get_all(
        "Applicant Reminder Email Log",
        filters={"reminder_type": "Not Started Application Rejected"},
        pluck="recipient"
    )
    already_rejected_set = set(already_rejected)

    template_name = "Applicant Not Started Application Reminder"
    institution_name = _get_institution_name()
    sent_count = 0

    for i, email in enumerate(user_emails):
        if total_items > 0:
            frappe.publish_realtime("applicant_reminder_progress", {
                "progress": [current_item + i, total_items],
                "title": "Applicant Reminders",
                "description": f"Not Started Reminders: {email}"
            }, user=frappe.session.user)

        if email in existing_set or email in already_rejected_set:
            continue

        try:
            if not email or not frappe.db.exists("User", email):
                continue

            user_doc = frappe.get_doc("User", email)
            if not user_doc.enabled:
                continue

            last_sent = user_doc.get("last_applicant_reminder_sent")

            if not should_send_reminder("not_started", last_sent, cycle_end_date):
                continue

            if today_date > close_date:
                # Past deadline — just log; no application to reject
                rejection_reason = get_rejection_reason("not_started_rejection_reason")
                subject, ok = _send_email_from_template(
                    "Applicant Application Rejected",
                    email,
                    {
                        "candidate_name": user_doc.full_name or email,
                        "rejection_reason": rejection_reason,
                        "cycle_end_date": formatdate(cycle_end_date),
                        "institution_name": institution_name,
                        "admission_portal_url": get_url("/admission-dashboard"),
                    },
                    reference_doctype="User",
                    reference_name=email,
                )
                if ok:
                    log_applicant_reminder_email(
                        recipient=email,
                        subject=subject or "Application Rejected",
                        reminder_type="Not Started Application Rejected",
                        sender=_get_template_sender("Applicant Application Rejected"),
                        reference_doctype="User",
                        reference_name=email,
                        email_template="Applicant Application Rejected",
                    )
                    sent_count += 1
                continue

            # Before deadline — send reminder
            subject, ok = _send_email_from_template(
                template_name,
                email,
                {
                    "candidate_name": user_doc.first_name or user_doc.full_name or email,
                    "cycle_end_date": formatdate(cycle_end_date),
                    "institution_name": institution_name,
                    "admission_portal_url": get_url("/admission-dashboard"),
                },
                reference_doctype="User",
                reference_name=email,
            )
            if ok:
                user_doc.db_set("last_applicant_reminder_sent", now_datetime(), update_modified=False)
                log_applicant_reminder_email(
                    recipient=email,
                    subject=subject,
                    reminder_type="Not Started Application Reminder",
                    sender=_get_template_sender(template_name),
                    reference_doctype="User",
                    reference_name=email,
                    email_template=template_name,
                )
                sent_count += 1

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Not Started Reminder Failed: {email}")

    return sent_count


# ---------------------------------------------------------------------------
# 2. Draft Application Reminder
# ---------------------------------------------------------------------------

def send_draft_applicant_reminders(current_item=0, total_items=0, is_rejection_only=False):
    """
    Sends reminders to applicants whose Applicant doc is still in Draft (docstatus=0).
    After application_end_date: rejects the application.
    """
    from slcm.admission.doctype.applicant_reminder_email_configuration.applicant_reminder_email_configuration import (
        should_send_reminder, get_rejection_reason,
    )
    from slcm.admission.doctype.applicant_reminder_email_log.applicant_reminder_email_log import (
        log_applicant_reminder_email,
    )

    cycle_name, cycle_end_date = _get_active_cycle()
    if not cycle_name or not cycle_end_date:
        return 0

    today_date = getdate(today())
    close_date = getdate(cycle_end_date)
    
    if is_rejection_only and today_date <= close_date:
        return 0

    applications = frappe.get_all(
        "Applicant",
        filters={"status": "Draft", "admission_cycle": cycle_name},
        fields=["name", "email", "candidate_name", "program", "last_draft_reminder_sent"],
    )

    template_name = "Applicant Draft Application Reminder"
    institution_name = _get_institution_name()
    sent_count = 0

    for i, app in enumerate(applications):
        if total_items > 0:
            frappe.publish_realtime("applicant_reminder_progress", {
                "progress": [current_item + i, total_items],
                "title": "Applicant Reminders",
                "description": f"Draft Reminders: {app.name}",
            }, user=frappe.session.user)

        try:
            recipient = app.email
            if not recipient:
                continue

            if not should_send_reminder("draft", app.last_draft_reminder_sent, cycle_end_date):
                continue

            if today_date > close_date:
                rejection_reason = get_rejection_reason("draft_rejection_reason")
                subject, ok = _send_email_from_template(
                    "Applicant Application Rejected",
                    recipient,
                    {
                        "candidate_name": app.candidate_name or recipient,
                        "applicant_id": app.name,
                        "program": app.program or "",
                        "rejection_reason": rejection_reason,
                        "cycle_end_date": formatdate(cycle_end_date),
                        "institution_name": institution_name,
                        "admission_portal_url": get_url("/admission-dashboard"),
                    },
                    reference_doctype="Applicant",
                    reference_name=app.name,
                )
                if ok:
                    # Mark application as Rejected via db_set to skip submit validation
                    rejected_status = frappe.db.get_value("Applicant Status", {"name": "Rejected"}, "name") or "Rejected"
                    frappe.db.set_value("Applicant", app.name, "status", rejected_status, update_modified=False)
                    frappe.db.set_value("Applicant", app.name, "rejected_reason", rejection_reason, update_modified=False)
                    frappe.db.commit()
                    log_applicant_reminder_email(
                        recipient=recipient,
                        subject=subject or "Application Rejected",
                        reminder_type="Draft Application Rejected",
                        sender=_get_template_sender("Applicant Application Rejected"),
                        reference_doctype="Applicant",
                        reference_name=app.name,
                        email_template="Applicant Application Rejected",
                    )
                    sent_count += 1
                continue

            # Before deadline — send reminder
            subject, ok = _send_email_from_template(
                template_name,
                recipient,
                {
                    "candidate_name": app.candidate_name or recipient,
                    "applicant_id": app.name,
                    "program": app.program or "",
                    "cycle_end_date": formatdate(cycle_end_date),
                    "institution_name": institution_name,
                    "admission_portal_url": get_url("/admission-dashboard"),
                },
                reference_doctype="Applicant",
                reference_name=app.name,
            )
            if ok:
                frappe.db.set_value("Applicant", app.name, "last_draft_reminder_sent", now_datetime(), update_modified=False)
                log_applicant_reminder_email(
                    recipient=recipient,
                    subject=subject,
                    reminder_type="Draft Application Reminder",
                    sender=_get_template_sender(template_name),
                    reference_doctype="Applicant",
                    reference_name=app.name,
                    email_template=template_name,
                )
                sent_count += 1

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Draft Reminder Failed: {app.name}")

    return sent_count


# ---------------------------------------------------------------------------
# 3. Submitted But Unpaid Application Fee Reminder
# ---------------------------------------------------------------------------

def send_unpaid_fee_reminders(current_item=0, total_items=0, is_rejection_only=False):
    """
    Sends reminders to submitted applicants (docstatus=1) whose application_fee_status
    is still Pending or Requested.
    After application_end_date: rejects the application.
    """
    from slcm.admission.doctype.applicant_reminder_email_configuration.applicant_reminder_email_configuration import (
        should_send_reminder, get_rejection_reason,
    )
    from slcm.admission.doctype.applicant_reminder_email_log.applicant_reminder_email_log import (
        log_applicant_reminder_email,
    )

    cycle_name, cycle_end_date = _get_active_cycle()
    if not cycle_name or not cycle_end_date:
        return 0

    today_date = getdate(today())
    close_date = getdate(cycle_end_date)
    
    if is_rejection_only and today_date <= close_date:
        return 0

    applications = frappe.get_all(
        "Applicant",
        filters={
            "status": "Submitted",
            "admission_cycle": cycle_name,
            "application_fee_status": ["in", ["Pending", "Requested"]],
        },
        fields=["name", "email", "candidate_name", "program", "application_fee_amount", "last_fee_reminder_sent"],
    )

    template_name = "Applicant Fee Payment Pending Reminder"
    institution_name = _get_institution_name()
    sent_count = 0

    for i, app in enumerate(applications):
        if total_items > 0:
            frappe.publish_realtime("applicant_reminder_progress", {
                "progress": [current_item + i, total_items],
                "title": "Applicant Reminders",
                "description": f"Unpaid Fee Reminders: {app.name}",
            }, user=frappe.session.user)

        try:
            recipient = app.email
            if not recipient:
                continue

            if not should_send_reminder("unpaid_fee", app.last_fee_reminder_sent, cycle_end_date):
                continue

            if today_date > close_date:
                rejection_reason = get_rejection_reason("unpaid_fee_rejection_reason")
                subject, ok = _send_email_from_template(
                    "Applicant Application Rejected",
                    recipient,
                    {
                        "candidate_name": app.candidate_name or recipient,
                        "applicant_id": app.name,
                        "program": app.program or "",
                        "rejection_reason": rejection_reason,
                        "cycle_end_date": formatdate(cycle_end_date),
                        "institution_name": institution_name,
                        "admission_portal_url": get_url("/admission-dashboard"),
                    },
                    reference_doctype="Applicant",
                    reference_name=app.name,
                )
                if ok:
                    rejected_status = frappe.db.get_value("Applicant Status", {"name": "Rejected"}, "name") or "Rejected"
                    frappe.db.set_value("Applicant", app.name, "status", rejected_status, update_modified=False)
                    frappe.db.set_value("Applicant", app.name, "rejected_reason", rejection_reason, update_modified=False)
                    frappe.db.commit()
                    log_applicant_reminder_email(
                        recipient=recipient,
                        subject=subject or "Application Rejected",
                        reminder_type="Unpaid Application Fee Rejected",
                        sender=_get_template_sender("Applicant Application Rejected"),
                        reference_doctype="Applicant",
                        reference_name=app.name,
                        email_template="Applicant Application Rejected",
                    )
                    sent_count += 1
                continue

            # Before deadline — send reminder
            subject, ok = _send_email_from_template(
                template_name,
                recipient,
                {
                    "candidate_name": app.candidate_name or recipient,
                    "applicant_id": app.name,
                    "program": app.program or "",
                    "application_fee_amount": app.application_fee_amount or 0,
                    "cycle_end_date": formatdate(cycle_end_date),
                    "institution_name": institution_name,
                    "admission_portal_url": get_url("/admission-dashboard"),
                },
                reference_doctype="Applicant",
                reference_name=app.name,
            )
            if ok:
                frappe.db.set_value("Applicant", app.name, "last_fee_reminder_sent", now_datetime(), update_modified=False)
                log_applicant_reminder_email(
                    recipient=recipient,
                    subject=subject,
                    reminder_type="Application Fee Reminder",
                    sender=_get_template_sender(template_name),
                    reference_doctype="Applicant",
                    reference_name=app.name,
                    email_template=template_name,
                )
                sent_count += 1

        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Unpaid Fee Reminder Failed: {app.name}")

    return sent_count
