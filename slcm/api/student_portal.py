# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, cint, today, nowdate, getdate


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
    absence_from_date=None,
    absence_to_date=None,
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
    if absence_from_date:
        doc.absence_from_date = absence_from_date
    if absence_to_date:
        doc.absence_to_date = absence_to_date
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

    # Resolve print format: prefer the one configured on the student's Fee Structure
    print_format = _resolve_invoice_print_format(student_name)

    pdf_bytes = _generate_pdf("Fee Invoice", invoice_name, print_format)

    safe = invoice_name.replace("/", "-").replace(" ", "_")
    frappe.local.response.filename    = f"Fee_Invoice_{safe}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type        = "pdf"


@frappe.whitelist()
def download_fee_invoice_admin(invoice_name):
    """Stream a PDF of any Fee Invoice for admin / REGO office users.

    Security:
    * Caller must be authenticated (not Guest).
    * Caller must have at least one of the allowed admin roles.
      (System Manager, REGO Officer, FINO Officer, Registration Officer,
       Registration User, Documentation Officer, IT Admin, or Accounts Manager)
    * No student-ownership check — admins can download any student's invoice.
    """
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Please log in."), frappe.AuthenticationError)

    ADMIN_ROLES = {
        "System Manager", "Administrator",
        "REGO Officer", "FINO Officer",
        "Registration Officer", "Registration User",
        "Documentation Officer", "IT Admin",
        "Accounts Manager", "Accounts User",
    }
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not user_roles.intersection(ADMIN_ROLES):
        frappe.throw(
            frappe._("You do not have permission to download fee invoices."),
            frappe.PermissionError,
        )

    if not frappe.db.exists("Fee Invoice", invoice_name):
        frappe.throw(frappe._("Invoice not found."), frappe.DoesNotExistError)

    # Resolve print format via the invoice's linked student
    student_name = frappe.db.get_value("Fee Invoice", invoice_name, "student")
    print_format  = _resolve_invoice_print_format(student_name) if student_name else "Fee Invoice Receipt"

    pdf_bytes = _generate_pdf("Fee Invoice", invoice_name, print_format)

    safe = invoice_name.replace("/", "-").replace(" ", "_")
    frappe.local.response.filename    = f"Fee_Invoice_{safe}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type        = "pdf"


def _resolve_invoice_print_format(student_name):
    """Return the receipt_print_format from the student's active Fee Structure, or the default."""
    default_fmt = "Fee Invoice Receipt"
    try:
        fs_name = frappe.db.get_value("Student Master", student_name, "fee_structure")
        if not fs_name:
            # Fallback: find active Student fee structure via programme
            programme = frappe.db.get_value("Student Master", student_name, "programme")
            if programme:
                program = frappe.db.get_value("Cohort", programme, "program")
                if not program and frappe.db.exists("Program", programme):
                    program = programme
                if program:
                    fs_name = frappe.db.get_value(
                        "Fee Structure",
                        {"program": program, "status": "Active", "applicable": "Student"},
                        "name",
                        order_by="valid_from desc, creation desc",
                    )
        if fs_name:
            pf = frappe.db.get_value("Fee Structure", fs_name, "receipt_print_format")
            if pf and frappe.db.exists("Print Format", pf):
                return pf
    except Exception:
        pass
    return default_fmt


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
        "Student Transcript":  {"student_field": "student", "filename": "Transcript"},
        "ID Card Generation":  {"student_field": "student", "filename": "ID_Card"},
        "Student Enrollment":  {"student_field": "student", "filename": "Enrollment"},
    }
    config = allowed.get(doctype)
    if not config:
        frappe.throw(frappe._("Document type not allowed."), frappe.PermissionError)

    owner = frappe.db.get_value(doctype, name, config["student_field"])
    if not owner or owner != student_name:
        frappe.throw(frappe._("Document not found or access denied."),
                     frappe.PermissionError)

    if doctype == "ID Card Generation":
        pdf_bytes = _generate_id_card_pdf(name)
    else:
        pdf_bytes = _generate_pdf(doctype, name, None)

    safe = name.replace("/", "-").replace(" ", "_")
    frappe.local.response.filename = f"{config['filename']}_{safe}.pdf"
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "pdf"


# Allowed Student Master fields that a student may download
_STUDENT_MASTER_DOWNLOADABLE_FIELDS = {
    "aadhaar_card",
    "pan_card",
    "passport",
    "pwd_certificate",
    "std_x_marksheet",
    "class_xii_marksheet",
    "ug_certificate",
    "ug_transcripts",
    "transfer_certificate",
    "entrance_exam_score_marksheet",
    "offer_letter",
    "phd_proposal",
    "posh_anti_ragging_declaration",
    "student_declaration",
    "parent_declaration",
}


@frappe.whitelist()
def download_student_master_document(fieldname):
    """Stream a file attached to the logged-in student's Student Master record."""
    if frappe.session.user == "Guest":
        frappe.throw(frappe._("Please log in."), frappe.AuthenticationError)

    if fieldname not in _STUDENT_MASTER_DOWNLOADABLE_FIELDS:
        frappe.throw(frappe._("Document type not allowed."), frappe.PermissionError)

    student_name = _get_student()
    if not student_name:
        frappe.throw(frappe._("No student record found for your account."), frappe.PermissionError)

    file_url = frappe.db.get_value("Student Master", student_name, fieldname)
    if not file_url:
        frappe.throw(frappe._("Document not found."), frappe.DoesNotExistError)

    # Resolve the actual file doc to get the real path / content
    file_doc = frappe.db.get_value(
        "File",
        {"file_url": file_url, "attached_to_doctype": "Student Master", "attached_to_name": student_name},
        ["name", "file_url", "file_name", "is_private"],
        as_dict=True,
    )
    if not file_doc:
        # Fallback: try matching only by URL (covers public files not linked strictly)
        file_doc = frappe.db.get_value(
            "File",
            {"file_url": file_url},
            ["name", "file_url", "file_name", "is_private"],
            as_dict=True,
        )

    if not file_doc:
        # If no File doc, serve as redirect to the stored URL directly
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = file_url
        return

    # Stream the file via Frappe's file manager
    from frappe.utils.file_manager import get_file
    fname, content = get_file(file_doc.name)
    frappe.local.response.filename = fname
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"


@frappe.whitelist()
def get_portal_notifications():
	"""Return notification data for the bell icon and announcement ticker in the student portal."""
	if frappe.session.user == "Guest":
		return {"notifications": [], "count": 0, "urgent_count": 0}

	student_name = _get_student()
	if not student_name:
		return {"notifications": [], "count": 0, "urgent_count": 0}

	notifications = []

	try:
		student = frappe.get_doc("Student Master", student_name, ignore_permissions=True)
		today_str = nowdate()
		today_date = getdate(today_str)

		# ── 1. Student Announcements ───────────────────────────────
		priority_order = {"Urgent": 0, "Important": 1, "Normal": 2}
		priority_icon = {"Urgent": "warning", "Important": "priority_high", "Normal": "campaign"}

		all_records = frappe.get_all(
			"Student Announcement",
			filters=[["is_active", "=", 1], ["publish_date", "<=", today_str]],
			fields=["name", "title", "announcement_type", "priority", "publish_date", "expiry_date", "target_audience"],
			order_by="priority desc, publish_date desc",
			limit=30,
			ignore_permissions=True,
		)

		for r in all_records:
			if r.expiry_date and getdate(r.expiry_date) < today_date:
				continue

			if r.target_audience != "All Students":
				if r.target_audience == "Specific Programme(s)":
					targets = frappe.get_all(
						"Announcement Programme Target",
						filters={"parent": r.name},
						fields=["programme"],
						ignore_permissions=True,
					)
					if not any(t.programme == student.programme for t in targets):
						continue
				elif r.target_audience == "Specific Batch Year(s)":
					targets = frappe.get_all(
						"Announcement Batch Target",
						filters={"parent": r.name},
						fields=["batch_year"],
						ignore_permissions=True,
					)
					s_batch = str(student.batch_year or "")
					s_acyr  = str(student.academic_year or "")
					if not any(
						str(t.batch_year) == s_batch or (s_acyr and str(t.batch_year) == s_acyr)
						for t in targets
					):
						continue
				elif r.target_audience == "Specific Student(s)":
					targets = frappe.get_all(
						"Announcement Student Target",
						filters={"parent": r.name},
						fields=["student"],
						ignore_permissions=True,
					)
					if not any(t.student == student_name for t in targets):
						continue

			pub_date = ""
			if r.publish_date:
				try:
					pub_date = getdate(r.publish_date).strftime("%d %b %Y")
				except Exception:
					pub_date = str(r.publish_date)

			notifications.append({
				"type": "announcement",
				"category": r.announcement_type or "General",
				"priority": r.priority or "Normal",
				"title": r.title or "",
				"subtitle": pub_date,
				"icon": priority_icon.get(r.priority, "campaign"),
				"link": "/student-portal/announcements",
				"sort_key": priority_order.get(r.priority, 2),
			})

		# ── 2. Upcoming Exam Schedule ──────────────────────────────
		try:
			att_summaries = frappe.get_all(
				"Attendance Summary",
				filters={"student": student_name},
				fields=["course_offering", "course"],
				ignore_permissions=True,
			)
			enrolled_courses = list({s.course for s in att_summaries if s.course})

			if enrolled_courses:
				exam_schedules = frappe.get_all(
					"Exam Course Schedule",
					filters=[
						["course", "in", enrolled_courses],
						["exam_date", ">=", today_str],
					],
					fields=["course", "exam_date", "start_time", "venue"],
					order_by="exam_date asc",
					limit=5,
					ignore_permissions=True,
				)
				for es in exam_schedules:
					date_str = ""
					try:
						date_str = getdate(es.exam_date).strftime("%d %b %Y")
					except Exception:
						date_str = str(es.exam_date or "")
					notifications.append({
						"type": "exam_schedule",
						"category": "Exam Schedule",
						"priority": "Important",
						"title": f"Exam: {es.course}",
						"subtitle": f"{date_str}" + (f" | {es.venue}" if es.venue else ""),
						"icon": "event_note",
						"link": "/student-portal/exam-schedule",
						"sort_key": 1,
					})
		except Exception:
			pass

		# ── 3. Published Results ───────────────────────────────────
		try:
			published_results = frappe.get_all(
				"Student Result Publish",
				filters={"student": student_name, "is_published": 1},
				fields=["exam_plan", "term_gpa", "published_on"],
				order_by="published_on desc",
				limit=3,
				ignore_permissions=True,
			)
			for res in published_results:
				pub_on = ""
				try:
					if res.published_on:
						pub_on = getdate(res.published_on).strftime("%d %b %Y")
				except Exception:
					pass
				notifications.append({
					"type": "result",
					"category": "Exam Result",
					"priority": "Important",
					"title": f"Results Published: {res.exam_plan or 'Exam'}",
					"subtitle": (f"GPA: {res.term_gpa:.2f}" if res.term_gpa else "") + (f" | {pub_on}" if pub_on else ""),
					"icon": "assignment_turned_in",
					"link": "/student-portal/results",
					"sort_key": 1,
				})
		except Exception:
			pass

		# ── 4. FA / MFA Application Status ────────────────────────
		try:
			fa_apps = frappe.get_all(
				"FA MFA Application",
				filters={"student": student_name, "status": ["in", ["Approved", "Rejected"]]},
				fields=["name", "status", "application_type", "course"],
				order_by="modified desc",
				limit=5,
				ignore_permissions=True,
			)
			for app in fa_apps:
				notifications.append({
					"type": "fa_mfa",
					"category": "FA / MFA",
					"priority": "Important",
					"title": f"{app.application_type or 'Application'} {app.status}",
					"subtitle": app.course or "",
					"icon": "check_circle" if app.status == "Approved" else "cancel",
					"link": "/student-portal/attendance",
					"sort_key": 1,
				})
		except Exception:
			pass

		# ── 5. Condonation Status ──────────────────────────────────
		try:
			cond_apps = frappe.get_all(
				"Student Attendance Condonation",
				filters={"student": student_name, "final_status": ["in", ["Approved", "Rejected"]]},
				fields=["name", "final_status", "course_offering"],
				order_by="modified desc",
				limit=5,
				ignore_permissions=True,
			)
			for app in cond_apps:
				notifications.append({
					"type": "condonation",
					"category": "Condonation",
					"priority": "Important",
					"title": f"Condonation {app.final_status}",
					"subtitle": app.course_offering or "",
					"icon": "check_circle" if app.final_status == "Approved" else "cancel",
					"link": "/student-portal/attendance",
					"sort_key": 1,
				})
		except Exception:
			pass

		# ── 6. Leave Application Status ───────────────────────────────
		try:
			leave_apps = frappe.get_all(
				"Student Leave Applications",
				filters={"student": student_name, "status": ["in", ["Approved", "Rejected"]]},
				fields=["name", "status", "from_date", "to_date", "total_leave_days"],
				order_by="modified desc",
				limit=5,
				ignore_permissions=True,
			)
			for app in leave_apps:
				from_str = ""
				try:
					if app.from_date:
						from_str = getdate(app.from_date).strftime("%d %b")
				except Exception:
					pass
				notifications.append({
					"type": "leave",
					"category": "Leave Request",
					"priority": "Important",
					"title": f"Leave {app.status}: {app.name}",
					"subtitle": from_str + (f" · {int(app.total_leave_days or 0)} day(s)" if app.total_leave_days else ""),
					"icon": "check_circle" if app.status == "Approved" else "cancel",
					"link": "/student-portal/leave-request",
					"sort_key": 1,
				})
		except Exception:
			pass

		# ── 7. Upcoming Office Hours ───────────────────────────────
		try:
			att_sums = frappe.get_all(
				"Attendance Summary",
				filters={"student": student_name},
				fields=["course_offering"],
				ignore_permissions=True,
			)
			enrolled_co = list({s.course_offering for s in att_sums if s.course_offering})

			if enrolled_co:
				oh_sessions = frappe.get_all(
					"Office Hours Session",
					filters=[
						["session_date", ">=", today_str],
						["session_status", "=", "Scheduled"],
						["course_offering", "in", enrolled_co],
					],
					fields=["name", "session_date", "start_time", "course_offering"],
					order_by="session_date asc",
					limit=3,
					ignore_permissions=True,
				)
				for sess in oh_sessions:
					date_str = ""
					try:
						date_str = getdate(sess.session_date).strftime("%d %b %Y")
					except Exception:
						date_str = str(sess.session_date or "")
					notifications.append({
						"type": "office_hours",
						"category": "Office Hours",
						"priority": "Normal",
						"title": "Office Hours Available",
						"subtitle": f"{sess.course_offering} — {date_str}",
						"icon": "school",
						"link": "/student-portal/attendance",
						"sort_key": 2,
					})
		except Exception:
			pass

	except Exception as e:
		frappe.log_error(f"get_portal_notifications error: {e}", "Student Portal API")

	notifications.sort(key=lambda x: x.get("sort_key", 2))

	count = len(notifications)
	urgent_count = sum(1 for n in notifications if n.get("priority") == "Urgent")

	return {
		"notifications": notifications[:20],
		"count": count,
		"urgent_count": urgent_count,
	}


def _generate_id_card_pdf(card_name):
    """Build a landscape PDF with front + back ID card images, base64-embedded for Frappe Cloud."""
    import base64
    import mimetypes
    from frappe.utils.pdf import get_pdf
    from frappe.utils.file_manager import get_file
    from frappe.utils import get_url, nowdate, escape_html, formatdate

    card = frappe.db.get_value(
        "ID Card Generation",
        card_name,
        [
            "front_id_image", "back_id_image", "student_name",
            "card_status", "issue_date", "expiry_date", "academic_year",
            "cancellation_reason",
        ],
        as_dict=True,
    )
    if not card:
        frappe.throw(frappe._("ID Card record not found."))

    if card.card_status in ("Cancelled", "Expired"):
        frappe.throw(
            frappe._(f"This ID card is {card.card_status.lower()} and cannot be downloaded."),
            frappe.PermissionError,
        )

    def _embed_image(file_url):
        """Return (data-URI, is_ok). Falls back to absolute URL on failure."""
        if not file_url:
            return None
        try:
            file_doc_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
            if file_doc_name:
                fname, content = get_file(file_doc_name)
                mime = mimetypes.guess_type(fname)[0] or "image/png"
                b64 = base64.b64encode(content).decode()
                return f"data:{mime};base64,{b64}"
        except Exception:
            pass
        return get_url(file_url)

    front_src = _embed_image(card.front_id_image)
    back_src  = _embed_image(card.back_id_image)

    if not front_src and not back_src:
        frappe.throw(
            frappe._("ID card images have not been generated yet."),
            frappe.ValidationError,
        )

    def _card_col(src, label):
        if not src:
            return ""
        return (
            f'<td class="card-col">'
            f'  <div class="card-label">{label}</div>'
            f'  <div class="card-img-wrap">'
            f'    <img src="{src}" alt="{label}">'
            f'  </div>'
            f'</td>'
        )

    issue_str  = formatdate(card.issue_date,  "dd MMM yyyy") if card.issue_date  else "—"
    expiry_str = formatdate(card.expiry_date, "dd MMM yyyy") if card.expiry_date else "—"
    name_safe  = escape_html(card.student_name or card_name)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{ size: A4 landscape; margin: 18mm 16mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background: #fff;
  color: #222;
  font-size: 12px;
}}

/* ── Header ── */
.hdr {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 3px solid #1a3c6e;
  margin-bottom: 18px;
}}
.hdr-left {{ }}
.hdr-title {{
  font-size: 20px;
  font-weight: 800;
  color: #1a3c6e;
  letter-spacing: -0.3px;
}}
.hdr-sub {{
  font-size: 12px;
  color: #666;
  margin-top: 2px;
}}
.hdr-meta {{
  text-align: right;
  font-size: 11px;
  color: #888;
  line-height: 1.8;
}}
.hdr-meta strong {{ color: #333; }}

/* ── Info strip ── */
.info-strip {{
  display: flex;
  gap: 32px;
  background: #f4f7fb;
  border: 1px solid #dce5f0;
  border-radius: 8px;
  padding: 10px 18px;
  margin-bottom: 22px;
}}
.info-item {{ }}
.info-label {{
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: #999;
  font-weight: 700;
}}
.info-val {{
  font-size: 13px;
  font-weight: 700;
  color: #1a3c6e;
  margin-top: 1px;
}}

/* ── Cards ── */
.cards-table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}}
.card-col {{
  width: 50%;
  vertical-align: top;
  padding: 0 12px;
}}
.card-col:first-child {{ padding-left: 0; border-right: 1px dashed #ddd; }}
.card-col:last-child  {{ padding-right: 0; }}
.card-label {{
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: #888;
  margin-bottom: 10px;
  text-align: center;
}}
.card-img-wrap {{
  text-align: center;
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px;
  border: 1px solid #e8eef5;
}}
.card-img-wrap img {{
  max-width: 100%;
  max-height: 200px;
  border-radius: 10px;
  box-shadow: 0 3px 14px rgba(0,0,0,.14);
  display: inline-block;
}}

/* ── Footer ── */
.footer {{
  margin-top: 22px;
  padding-top: 8px;
  border-top: 1px solid #e5e5e5;
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: #bbb;
}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-left">
    <div class="hdr-title">Student ID Card</div>
    <div class="hdr-sub">{name_safe}</div>
  </div>
  <div class="hdr-meta">
    <div><strong>Card ID</strong> {escape_html(card_name)}</div>
    <div><strong>Status</strong> {escape_html(card.card_status or 'Generated')}</div>
  </div>
</div>

<div class="info-strip">
  <div class="info-item">
    <div class="info-label">Card Holder</div>
    <div class="info-val">{name_safe}</div>
  </div>
  <div class="info-item">
    <div class="info-label">Issue Date</div>
    <div class="info-val">{issue_str}</div>
  </div>
  <div class="info-item">
    <div class="info-label">Valid Until</div>
    <div class="info-val">{expiry_str}</div>
  </div>
  {f'<div class="info-item"><div class="info-label">Academic Year</div><div class="info-val">{escape_html(card.academic_year)}</div></div>' if card.academic_year else ''}
</div>

<table class="cards-table">
  <tr>
    {_card_col(front_src, "Front")}
    {_card_col(back_src,  "Back")}
  </tr>
</table>

<div class="footer">
  <span>Downloaded from Student Portal &mdash; {nowdate()}</span>
  <span>Card ID: {escape_html(card_name)}</span>
</div>

</body>
</html>"""

    return get_pdf(html, {"orientation": "Landscape"})


def _generate_pdf(doctype, name, print_format):
    """Generate a PDF by temporarily running as Administrator.

    frappe.set_user() corrupts three session fields that must all be restored:
      - session.sid  → overwritten with username string (breaks cookie lookup)
      - session.data → cleared to empty _dict() (loses all session payload)
      - session.user → restored by set_user(original_user), but data/sid are not
    We snapshot all three before escalating and restore them in the finally block.
    """
    from frappe.utils.pdf import get_pdf
    import copy as _copy

    sess            = frappe.local.session
    original_user   = sess.user
    original_sid    = getattr(sess, "sid",  None)
    original_data   = _copy.deepcopy(getattr(sess, "data", frappe._dict()))

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
        # set_user(original_user) restores .user but clears .sid and .data again.
        frappe.set_user(original_user)
        if original_sid:
            sess.sid  = original_sid
        sess.data = original_data
 