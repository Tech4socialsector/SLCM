# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, cint, today


def _get_student():
    """Return the Student Master name for the currently logged-in user."""
    user = frappe.session.user
    name = frappe.db.get_value("Student Master", {"user": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"email": user}, "name")
    if not name:
        name = frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
    return name


# ─────────────────────────────────────────────────────────────────────────────
#  Lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_condonation_reasons():
    """Return a list of available Condonation Reason names."""
    try:
        reasons = frappe.get_all(
            "Condonation Reason",
            fields=["name"],
            order_by="name asc",
            ignore_permissions=True
        )
        return [r.name for r in reasons]
    except Exception as e:
        frappe.log_error(f"get_condonation_reasons error: {e}", "Student Portal API")
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  FA / MFA Application
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def submit_fa_mfa_application(
    course,
    examination_date,
    application_type,
    reason,
    description=None,
    proof_document=None,
    event_from_date=None,
    event_to_date=None,
):
    """
    Create and save a new FA/MFA Application on behalf of the logged-in student.
    Called via AJAX from the student portal attendance page.
    """
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to submit an application.", frappe.PermissionError)

    student = _get_student()
    if not student:
        frappe.throw(
            "No student record found for your account. "
            "Please contact the Registrar's Office."
        )

    # Validate required fields
    for label, val in [
        ("Course", course),
        ("Examination Date", examination_date),
        ("Application Type", application_type),
        ("Reason", reason),
        ("Proof Document", proof_document),
    ]:
        if not val:
            frappe.throw(f"{label} is required.")

    # Check global setting
    settings = frappe.get_single("Attendance Settings")
    if not settings.allow_fa_mfa:
        frappe.throw("FA/MFA Applications are currently disabled by the administration.")

    # Prevent duplicate
    existing = frappe.db.exists(
        "FA MFA Application",
        {
            "student": student,
            "course": course,
            "examination_date": examination_date,
            "docstatus": ["<", 2],
        },
    )
    if existing:
        frappe.throw(
            f"An application for this course and examination date already exists "
            f"(ID: {existing}). Please check your existing applications."
        )

    doc = frappe.new_doc("FA MFA Application")
    doc.student = student
    doc.course = course
    doc.examination_date = examination_date
    doc.application_type = application_type
    doc.reason = reason
    doc.description = description or ""
    doc.proof_document = proof_document
    doc.status = "Pending"

    if reason == "University Representation":
        if event_from_date:
            doc.event_from_date = event_from_date
        if event_to_date:
            doc.event_to_date = event_to_date

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"FA MFA Application insert error: {e}", "Student Portal API")
        frappe.throw(str(e))

    return {
        "name": doc.name,
        "status": "success",
        "message": f"Application submitted successfully. Application ID: {doc.name}",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Condonation Application
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def submit_condonation_application(
    course_offering,
    number_of_sessions,
    number_of_hours,
    condonation_reason,
    proof_document=None,
):
    """
    Create and save a new Student Attendance Condonation on behalf of the
    logged-in student. Called via AJAX from the student portal attendance page.
    """
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to submit an application.", frappe.PermissionError)

    student = _get_student()
    if not student:
        frappe.throw(
            "No student record found for your account. "
            "Please contact the Registrar's Office."
        )

    # Validate required fields
    for label, val in [
        ("Course", course_offering),
        ("Number of Sessions", number_of_sessions),
        ("Number of Hours", number_of_hours),
        ("Reason", condonation_reason),
    ]:
        if not val:
            frappe.throw(f"{label} is required.")

    # Check global setting
    settings = frappe.get_single("Attendance Settings")
    if not settings.allow_condonation:
        frappe.throw("Condonation Applications are currently disabled by the administration.")

    # Prevent duplicate pending application for same course
    existing = frappe.db.exists(
        "Student Attendance Condonation",
        {
            "student": student,
            "course_offering": course_offering,
            "final_status": "Pending",
            "docstatus": ["<", 2],
        },
    )
    if existing:
        frappe.throw(
            f"A pending condonation application for this course already exists "
            f"(ID: {existing})."
        )

    # Attendance eligibility check
    summary = frappe.db.get_value(
        "Attendance Summary",
        {"student": student, "course_offering": course_offering},
        ["attendance_percentage", "minimum_required_percentage"],
        as_dict=True,
    )
    if summary:
        min_cond_pct = flt(getattr(settings, "condonation_min_percentage", 66) or 66)
        att_pct = flt(summary.attendance_percentage)
        if att_pct < min_cond_pct:
            frappe.throw(
                f"Your attendance ({att_pct:.1f}%) is below the minimum required "
                f"({min_cond_pct:.0f}%) to apply for condonation. "
                "Please contact your Faculty Advisor."
            )

    doc = frappe.new_doc("Student Attendance Condonation")
    doc.student = student
    doc.course_offering = course_offering
    doc.number_of_sessions = cint(number_of_sessions)
    doc.number_of_hours = flt(number_of_hours)
    doc.condonation_reason = condonation_reason
    if proof_document:
        doc.proof_document = proof_document
    doc.final_status = "Pending"

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Condonation insert error: {e}", "Student Portal API")
        frappe.throw(str(e))

    return {
        "name": doc.name,
        "status": "success",
        "message": f"Condonation application submitted successfully. Application ID: {doc.name}",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Support Ticket
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_support_ticket(category, subject, description, attachment=None):
    """
    Create a support ticket (Communication record) on behalf of the logged-in student.
    Sends an email notification to the system admin.
    """
    if frappe.session.user == "Guest":
        frappe.throw("Please log in to raise a support ticket.", frappe.PermissionError)

    for label, val in [("Category", category), ("Subject", subject), ("Description", description)]:
        if not val or not str(val).strip():
            frappe.throw(f"{label} is required.")

    student = _get_student()
    student_name_display = frappe.session.user
    student_id = ""
    if student:
        s = frappe.db.get_value(
            "Student Master",
            student,
            ["first_name", "last_name", "registration_id"],
            as_dict=True,
        )
        if s:
            student_name_display = " ".join(filter(None, [s.first_name, s.last_name])) or student
            student_id = s.registration_id or student

    full_subject = f"[{category}] {str(subject).strip()}"
    full_content = (
        f"<p><strong>Category:</strong> {category}</p>"
        f"<p><strong>Student:</strong> {student_name_display}"
        + (f" ({student_id})" if student_id else "") +
        f"</p>"
        f"<p><strong>Email:</strong> {frappe.session.user}</p>"
        f"<hr>"
        f"<p>{str(description).strip().replace(chr(10), '<br>')}</p>"
        + (f"<p><strong>Attachment:</strong> <a href='{attachment}'>{attachment}</a></p>" if attachment else "")
    )

    # Create Communication record for tracking
    comm = frappe.new_doc("Communication")
    comm.communication_type = "Communication"
    comm.communication_medium = "Email"
    comm.subject = full_subject
    comm.content = full_content
    comm.sent_or_received = "Received"
    comm.status = "Open"
    comm.sender = frappe.session.user
    comm.sender_full_name = student_name_display
    if student:
        comm.reference_doctype = "Student Master"
        comm.reference_name = student
    comm.communication_date = frappe.utils.now()

    try:
        comm.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Support ticket Communication insert error: {e}", "Student Portal API")
        frappe.throw("Failed to create support ticket. Please try again.")

    # Email notification to admin
    try:
        admin_email = frappe.db.get_single_value("System Settings", "support_email") or ""
        if not admin_email:
            # Fallback to first outgoing email account
            acc = frappe.db.get_value(
                "Email Account",
                {"enable_outgoing": 1},
                "email_id",
            )
            admin_email = acc or ""

        if admin_email:
            frappe.sendmail(
                recipients=[admin_email],
                subject=f"[Student Portal] {full_subject}",
                message=full_content,
                now=True,
            )
    except Exception as e:
        # Email failure should not block the user
        frappe.log_error(f"Support ticket email error: {e}", "Student Portal API")

    return {
        "name": comm.name,
        "status": "success",
        "message": f"Support ticket raised successfully! Ticket ID: {comm.name}",
    }


@frappe.whitelist()
def get_my_support_tickets():
    """Return support tickets (Communications) raised by the logged-in student."""
    if frappe.session.user == "Guest":
        frappe.throw("Please log in.", frappe.PermissionError)

    student = _get_student()
    filters = [["sender", "=", frappe.session.user]]
    if student:
        filters = [
            ["reference_doctype", "=", "Student Master"],
            ["reference_name", "=", student],
        ]

    try:
        tickets = frappe.get_all(
            "Communication",
            filters=filters,
            fields=["name", "subject", "content", "status", "communication_date", "creation"],
            order_by="creation desc",
            limit=20,
            ignore_permissions=True,
        )
        return tickets
    except Exception as e:
        frappe.log_error(f"get_my_support_tickets error: {e}", "Student Portal API")
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  Office Hours Registration
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def register_office_hours_attendance(session_name):
    """
    Register the logged-in student's attendance for a scheduled Office Hours Session.
    Creates a Student Attendance record with based_on = Office Hours.
    """
    if frappe.session.user == "Guest":
        frappe.throw("Please log in.", frappe.PermissionError)

    student = _get_student()
    if not student:
        frappe.throw("No student record found for your account.")

    try:
        session = frappe.get_doc("Office Hours Session", session_name, ignore_permissions=True)
    except frappe.DoesNotExistError:
        frappe.throw("Office Hours Session not found.")

    if session.session_status != "Scheduled":
        frappe.throw("This session is no longer available for registration.")

    # Prevent duplicate registration
    existing = frappe.db.exists(
        "Student Attendance",
        {
            "student": student,
            "attendance_date": session.session_date,
            "based_on": "Office Hours",
            "course_offer": session.course_offering,
        },
    )
    if existing:
        frappe.throw("You have already registered attendance for this office hours session.")

    doc = frappe.new_doc("Student Attendance")
    doc.based_on = "Office Hours"
    doc.student = student
    doc.course_offer = session.course_offering
    doc.attendance_date = session.session_date
    doc.date = session.session_date
    doc.status = "Present"
    doc.in_time = session.start_time
    doc.out_time = session.end_time
    doc.session_type = "Office Hours"
    doc.source = "Manual"

    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Office Hours registration error: {e}", "Student Portal API")
        frappe.throw(str(e))

    return {
        "name": doc.name,
        "status": "success",
        "message": "You have been successfully registered for the office hours session.",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Secure Document Downloads
# ─────────────────────────────────────────────────────────────────────────────

# Maps doc_type keys the student can request to (Frappe doctype, print format name)
_ALLOWED_DOWNLOADS = {
    "application_form": {
        "doctype": "Applicant",
        "format":  "Applicant Application Form",
        "filename": "Application_Form",
        "source":   "application_number",   # SM field that holds the doc name
    },
    "registration_slip": {
        "doctype": "Student Master",
        "format":  "Student Registration Slip",
        "filename": "Registration_Slip",
        "source":   "self",                 # use the student's own SM name
    },
}


@frappe.whitelist()
def download_student_document(doc_type):
    """Generate and stream a PDF for the requesting student's own document.

    Security:
    * Caller must be authenticated and have a Student Master record.
    * Only document types listed in _ALLOWED_DOWNLOADS are permitted.
    * For Applicant documents, the Applicant name is read from the student's
      own `application_number` field — the student cannot request another
      applicant's form.

    Usage (called via a direct browser link):
        /api/method/slcm.api.student_portal.download_student_document
            ?doc_type=application_form
    """
    from frappe.utils.pdf import get_pdf

    # ── Auth guard ────────────────────────────────────────────
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Please log in to download documents."),
                     frappe.AuthenticationError)

    student_name = _get_student()
    if not student_name:
        frappe.throw(frappe._("No student record found for your account."),
                     frappe.PermissionError)

    # ── Allowed-list check ────────────────────────────────────
    config = _ALLOWED_DOWNLOADS.get(doc_type)
    if not config:
        frappe.throw(
            frappe._("Invalid document type '{0}'.").format(doc_type),
            frappe.ValidationError,
        )

    # ── Resolve the document name ─────────────────────────────
    if config["source"] == "self":
        doc_name = student_name
    else:
        # e.g. application_number from Student Master
        doc_name = frappe.db.get_value(
            "Student Master", student_name, config["source"]
        )
        if not doc_name:
            frappe.throw(
                frappe._("No {0} record found on your student profile.").format(
                    config["doctype"]
                ),
                frappe.ValidationError,
            )

    # ── Verify the document exists before attempting PDF generation ──
    # Prevents a cryptic 500 error if the record was deleted or never created.
    if not frappe.db.exists(config["doctype"], doc_name):
        frappe.throw(
            frappe._(
                "Your {0} record could not be found. "
                "Please contact the Registrar's Office."
            ).format(config["doctype"]),
            frappe.DoesNotExistError,
        )

    # ── Generate PDF (escalate to Administrator so the print
    #    format can read the document regardless of role perms) ─
    pdf_bytes = _generate_pdf(config["doctype"], doc_name, config["format"])

    # ── Stream response ───────────────────────────────────────
    safe_name = doc_name.replace("/", "-").replace(" ", "_")
    frappe.local.response.filename    = f"{config['filename']}_{safe_name}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type        = "pdf"


@frappe.whitelist()
def download_fee_invoice(invoice_name):
    """Stream a PDF of the student's own Fee Invoice.

    Security:
    * Caller must be authenticated and have a Student Master record.
    * Invoice ownership validated before any PDF is generated (IDOR guard).
    """
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Please log in."), frappe.AuthenticationError)

    student_name = _get_student()
    if not student_name:
        frappe.throw(frappe._("No student record found for your account."),
                     frappe.PermissionError)

    # Ownership check — the invoice must belong to this student
    owner = frappe.db.get_value("Fee Invoice", invoice_name, "student")
    if not owner or owner != student_name:
        frappe.throw(frappe._("Invoice not found or access denied."),
                     frappe.PermissionError)

    pdf_bytes = _generate_pdf("Fee Invoice", invoice_name, None)

    safe = invoice_name.replace("/", "-").replace(" ", "_")
    frappe.local.response.filename    = f"Fee_Invoice_{safe}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type        = "pdf"


@frappe.whitelist()
def download_student_record_pdf(doctype, name):
    """Stream a PDF for portal documents owned by the logged-in student."""
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Please log in."), frappe.AuthenticationError)

    student_name = _get_student()
    if not student_name:
        frappe.throw(frappe._("No student record found for your account."),
                     frappe.PermissionError)

    allowed = {
        "Student Transcript": {"student_field": "student", "filename": "Transcript"},
        "Student ID Card": {"student_field": "student", "filename": "ID_Card"},
        "Student Enrollment": {"student_field": "student", "filename": "Enrollment"},
    }
    config = allowed.get(doctype)
    if not config:
        frappe.throw(frappe._("Document type not allowed."), frappe.PermissionError)

    owner = frappe.db.get_value(doctype, name, config["student_field"])
    if not owner or owner != student_name:
        frappe.throw(frappe._("Document not found or access denied."),
                     frappe.PermissionError)

    pdf_bytes = _generate_pdf(doctype, name, None)
    safe = name.replace("/", "-").replace(" ", "_")
    frappe.local.response.filename = f"{config['filename']}_{safe}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "pdf"


def _generate_pdf(doctype, name, print_format):
    """Generate a PDF for *name* by temporarily running as Administrator.

    frappe.get_print() does not accept an ignore_permissions kwarg; the only
    safe way to bypass role-based read checks for server-side PDF generation
    is to escalate the session user to Administrator for the duration of the
    call, then restore the original user.
    """
    from frappe.utils.pdf import get_pdf

    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        html = frappe.get_print(
            doctype=doctype,
            name=name,
            print_format=print_format,
            as_pdf=False,
            no_letterhead=0,
        )
        return get_pdf(html)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "_generate_pdf")
        frappe.throw(
            frappe._("Could not generate the document. Please try again or contact support."),
            frappe.ValidationError,
        )
    finally:
        frappe.set_user(original_user)
