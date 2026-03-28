import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address, getdate, date_diff, today, now, flt, nowdate
from slcm.admission.utils.regulatory import log_audit_trail

class Applicant(Document):

    # ──────────────────────────────────────────────
    # VALIDATE
    # ──────────────────────────────────────────────

    def before_validate(self):
        # Save Draft: skip mandatory check so user can save incomplete form.
        if self.application_status == "Draft":
            self.flags.ignore_mandatory = True

    def validate(self):
        """
        Runs on every save.
        Eligibility and mandatory are checked only when the user clicks "Submit Application":
        the portal sets application_status = "Submitted" before save(), so this block runs
        during that submit request. Save Draft does not set Submitted, so no eligibility/mandatory here.
        create_or_update_evaluation() is called inside validate_eligibility().
        """
        set_intake_type(self)

        if self.application_status == "Submitted" and self.has_value_changed("application_status"):
            self._validate_application_fee_before_submit()

        if self.application_status == "Submitted":
            self._validate_national_test_percentage()
            self.validate_eligibility()
            if self.evaluation_status == "Ineligible":
                frappe.throw(
                    _("Submission Not Allowed: Applicant is not eligible."),
                    title=_("Submission Not Allowed")
                )
            # Set application_status from national test exemption (only when student submits)
            self.application_status = _get_submission_application_status(self)

    def validate_email(self):
        if not validate_email_address(self.email):
            frappe.throw(
                f"Invalid email address: {self.email}",
                title="Invalid Email"
            )

    def validate_age(self):
        if self.date_of_birth:
            age = date_diff(today(), self.date_of_birth) / 365
            if age < 17:
                frappe.throw(
                    "Applicant must be at least 17 years old.",
                    title="Age Restriction"
                )

    # def validate_percentages(self):
    #     if self.class_x_percentage:
    #         if not 0 <= self.class_x_percentage <= 100:
    #             frappe.throw(
    #                 "Class X Percentage must be between 0 and 100.",
    #                 title="Invalid Percentage"
    #             )
    #     if self.class_xii_percentage:
    #         if not 0 <= self.class_xii_percentage <= 100:
    #             frappe.throw(
    #                 "Class XII Percentage must be between 0 and 100.",
    #                 title="Invalid Percentage"
    #             )

    def validate_reservation_documents(self):
        if self.ews == "Yes" and not self.ews_certificate:
            frappe.throw(
                "EWS Certificate is mandatory for EWS category.",
                title="Missing Document"
            )

        # Derive caste categories from the whether_scstobc_ncl field
        caste_categories = {"SC", "ST", "OBC-NCL"}
        applicant_cats = self._get_applicant_categories()
        matched_caste = applicant_cats & caste_categories

        if matched_caste and not self.caste_certificate:
            frappe.throw(
                f"Caste Certificate is mandatory for {', '.join(sorted(matched_caste))} category.",
                title="Missing Document"
            )

        if self.pwd == "Yes" and not self.pwd_certificate:
            frappe.throw(
                "PwD Certificate is mandatory for PwD category.",
                title="Missing Document"
            )

    def _validate_national_test_percentage(self):
        """When National test is selected, score/percentage is mandatory."""
        if self.get("national_test_name") and not self.flags.ignore_mandatory:
            pct = self.get("percentage")
            if pct is None or pct == "" or (isinstance(pct, (int, float)) and flt(pct) < 0):
                frappe.throw(
                    _("Score or percentage is required when National test is selected."),
                    title=_("National Test Score Required"),
                )

    def validate_preferences(self):
        if not self.first_preference:
            frappe.throw(
                "First Campus Preference is mandatory.",
                title="Missing Preference"
            )
        preferences = [
            self.first_preference,
            self.second_preference,
            self.third_preference
        ]
        filled = [p for p in preferences if p]
        if len(filled) != len(set(filled)):
            frappe.throw(
                "Duplicate campus preferences are not allowed.",
                title="Duplicate Preference"
            )

    def _validate_application_fee_before_submit(self):
        """Block submission if application fee is required and not paid/waived.
        When category has no fee or fee is 0, allow submit and set application_fee_status to 'Paid'."""
        from slcm.api.service.application_fee_service import get_application_fee_for_category
        from slcm.api.service.application_fee_service import _get_applicant_category

        category = _get_applicant_category(self.name)
        fee_amount = get_application_fee_for_category(self.program, self.admission_cycle, category)

        if flt(fee_amount, 2) <= 0:
            # No fee or zero fee: allow submit without payment; set status to Paid so UI/reports treat as complete
            self.application_fee_status = "Paid"
            if flt(self.application_fee_amount or 0, 2) != flt(fee_amount, 2):
                self.application_fee_amount = flt(fee_amount, 2)
            return

        # Fee > 0: require Paid or Waived
        db_status = frappe.db.get_value("Applicant", self.name, "application_fee_status")
        status = (db_status or self.application_fee_status or "Pending").strip()

        if status not in ("Paid", "Waived"):
            frappe.throw(
                _("Application fee must be paid or waived before you can submit. "
                  "Current status: {0}. Amount: {1}. "
                  "Go to View Application and click \"Pay Application Fee\" to open the payment gateway and pay; then return here to submit.").format(
                    status, fee_amount
                ),
                title=_("Pay Application Fee First")
            )

    def validate_declaration(self):
        if self.application_status == "Submitted" and not self.declaration_undertaking:
            frappe.throw(
                "Declaration Undertaking must be accepted before submission.",
                title="Declaration Required"
            )

    def before_save(self):
        if not self.applicant_id:
            self.applicant_id = frappe.generate_hash(length=8).upper()
        doc_before = self.get_doc_before_save()
        self.flags.old_application_status = doc_before.application_status if doc_before else None

    def on_update(self):
        # Statuses that mean "student has submitted" (including exemption statuses)
        _SUBMITTED_STATUSES = frozenset({
            "Submitted",
            "Interview Excempted",
            "Entrance Test Exempted",
            "Excempted Entrance Test And Interview",
        })

        old_status = self.flags.get("old_application_status")
        just_submitted = (
            old_status == "Draft"
            and self.application_status in _SUBMITTED_STATUSES
            and self.has_value_changed("application_status")
        )

        if just_submitted:
            log_audit_trail(
                self.doctype, self.name,
                self.application_status, "application_status",
                "Draft", self.application_status, "General"
            )

            # ── Rich confirmation email with PDF attachment ──────────────
            try:
                self.send_submission_confirmation()
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Submission confirmation email failed — {self.applicant_id}"
                )
            # ─────────────────────────────────────────────────────────────

            from slcm.admission.utils.notifications import log_communication
            log_communication(
                applicant=self.name,
                communication_type="Email",
                category="Admission",
                subject=f"Application Submitted — {self.applicant_id} | {self.program or 'Admissions'}",
                content=(
                    f"Submission confirmation email sent for {self.applicant_id}. "
                    f"Program: {self.program or '—'}, "
                    f"Cycle: {self.admission_cycle or '—'}, "
                    f"Campus: {self.campus or '—'}"
                ),
                reference_doctype="Applicant",
                reference_name=self.name
            )

        # If current_stage changed, notify applicant
        if self.is_new() or self.has_value_changed("current_stage"):
            if self.current_stage and self.admission_cycle:
                try:
                    from slcm.admission.utils.stage_control import get_cycle_stages
                    stages = get_cycle_stages(
                        self.admission_cycle,
                        self.intake_type or "All"
                    )
                    for s in stages:
                        if s.stage_name == self.current_stage:
                            notify_stage_entry(self, s)
                            break
                except Exception:
                    pass

        # Withdrawn application: Student Master (Current Status) + enrollments
        if self.application_status == "Withdrawn" and self.has_value_changed("application_status"):
            try:
                from slcm.admission.utils.withdrawal_sync import (
                    sync_student_records_for_withdrawn_application,
                )

                sync_student_records_for_withdrawn_application(
                    self.name,
                    status_remark=_("Application withdrawn"),
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Withdrawal sync failed for Applicant {self.name}",
                )

    def send_submission_confirmation(self):
        """
        Sends a formatted confirmation email on application submission.
        - Email template fetched from active Admission Cycle's `email_template` field
        - Print format fetched from active Admission Cycle's `application_form_template` field
        - System notification created via Notification Log (no new DocType)
        - Falls back to hardcoded HTML if no template is configured on the cycle
        """

        # ── Fetch active Admission Cycle config ──────────────────────────────
        cycle_name = self.admission_cycle  # already linked on the applicant

        email_template_name = None
        print_format_name = "Applicant Application Form"  # default fallback

        if cycle_name:
            cycle = frappe.db.get_value(
                "Admission Cycle",
                {"name": cycle_name, "status": "Active"},
                ["email_template", "application_form_template"],
                as_dict=True
            )
            if cycle:
                email_template_name = cycle.get("email_template")
                print_format_name = cycle.get("application_form_template") or print_format_name

        # ── Reservation summary ──────────────────────────────────────────────
        reservation_parts = []
        if self.whether_scstobc_ncl:
            reservation_parts.append(self.whether_scstobc_ncl)
        if self.ews == "Yes":
            reservation_parts.append("EWS")
        if self.pwd == "Yes":
            reservation_parts.append("PwD")
        if self.karnataka_category:
            reservation_parts.append(f"Karnataka: {self.karnataka_category}")
        reservation_summary = (
            ", ".join(reservation_parts) if reservation_parts else "General (Unreserved)"
        )

        # ── Test center preference summary ───────────────────────────────────
        test_centers = []
        if self.first_preference:
            test_centers.append(f"1st: {self.first_preference}")
        if self.second_preference:
            test_centers.append(f"2nd: {self.second_preference}")
        if self.third_preference:
            test_centers.append(f"3rd: {self.third_preference}")
        test_center_summary = " | ".join(test_centers) if test_centers else "Not specified"

        # ── Program-level academic summary ───────────────────────────────────
        academic_line = ""
        if self.program_level == "UG":
            academic_line = (
                f"Class XII: {self.class_xii_school or '—'} "
                f"({self.class_xii_year_of_completion or '—'}) "
                f"— {self.hsc_percentage or '—'}%"
            )
        elif self.program_level in ["PG", "LLM"]:
            academic_line = f"UG Degree completion: {self.ug_degree_completion or '—'}"
        elif self.program_level == "PhD":
            academic_line = f"PhD Program Type: {self.phd_program_type or '—'}"

        # ── Institution name ─────────────────────────────────────────────────
        institution_name = (
            frappe.db.get_single_value("Institution Settings", "institution_name")
            or "Admissions Office"
        )

        admission_portal_url = frappe.utils.get_url("/admission")

        # ── Institution logo ──────────────────────────────────────────────────
        institution_logo = frappe.db.get_single_value("Institution Settings", "logo") or ""
        # Convert to full URL if it's a file path
        if institution_logo and not institution_logo.startswith("http"):
            institution_logo = frappe.utils.get_url(institution_logo)

        # ── Context dict for template rendering ──────────────────────────────
        template_context = {
            "doc": self,
            "applicant_id": self.name,
            "candidate_name": self.candidate_name,
            "program": self.program or "—",
            "program_level": self.program_level or "—",
            "application_type": self.application_type or "—",
            "admission_cycle": self.admission_cycle or "—",
            "campus": self.campus or "—",
            "application_status": self.application_status or "Submitted",
            "date_of_birth": frappe.utils.formatdate(self.date_of_birth) if self.date_of_birth else "—",
            "gender": self.gender or "—",
            "mobile_number": self.mobile_number or "—",
            "nationality": self.nationality or "—",
            "city": self.city or "—",
            "state": self.state or "—",
            "class_x_school": self.class_x_school or "—",
            "class_x_percentage": f"{self.class_x_percentage}%" if self.class_x_percentage else "—",
            "class_xii_school": self.class_xii_school or "—",
            "hsc_percentage": f"{self.hsc_percentage}%" if self.hsc_percentage else "—",
            "reservation_summary": reservation_summary,
            "annual_house_hold_income": self.annual_house_hold_income or "—",
            "test_center_summary": test_center_summary,
            "application_fee_status": self.application_fee_status or "—",
            "application_fee_amount": (
                frappe.utils.fmt_money(self.application_fee_amount, currency="INR")
                if self.application_fee_amount else "—"
            ),
            "institution_name": institution_name,
            "institution_logo": institution_logo,
            "admission_portal_url": admission_portal_url,
            "generated_on": frappe.utils.now_datetime().strftime("%d %b %Y, %I:%M %p"),
        }

        # ── Resolve email subject and body ────────────────────────────────────
        email_subject = f"Application Submitted — {self.name} | {self.program or 'Admissions'}"
        html_body = None

        if email_template_name:
            try:
                email_template = frappe.get_doc("Email Template", email_template_name)
                # Render subject and response using Jinja
                email_subject = frappe.render_template(email_template.subject, template_context)
                html_body = frappe.render_template(email_template.response, template_context)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Email template render failed for {self.applicant_id}, falling back to default"
                )
                html_body = None  # will fall through to hardcoded below

        # ── Fallback to hardcoded HTML if no template or render failed ────────
        if not html_body:
            html_body = self._build_default_email_html(template_context)

        # ── PDF attachment using dynamic print format ─────────────────────────
        try:
            pdf_content = frappe.get_print(
                doctype="Applicant",
                name=self.name,
                print_format=print_format_name,
                as_pdf=True
            )
            attachments = [{
                "fname": f"Application_Form_{self.applicant_id or self.name}.pdf",
                "fcontent": pdf_content
            }]
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"PDF generation failed for {self.applicant_id} using format '{print_format_name}'"
            )
            attachments = []

        # ── Send email ────────────────────────────────────────────────────────
        frappe.sendmail(
            recipients=[self.email],
            subject=email_subject,
            message=html_body,
            attachments=attachments,
            now=True
        )

        # ── System notification (Notification Log — no new DocType) ──────────
        self._create_system_notification(institution_name)


    def _create_system_notification(self, institution_name):
        """
        Creates a Frappe Notification Log entry so the bell icon in the desk
        shows a notification to the Admission Admin role.
        No new DocType required — uses the built-in Notification Log.
        """
        try:
            # Notify all users who have the Admission Admin role
            admin_users = frappe.get_all(
                "Has Role",
                filters={"role": "Admission Admin", "parenttype": "User"},
                pluck="parent"
            )

            # Also notify the applicant if they have a user account
            applicant_user = frappe.db.get_value("User", {"email": self.email}, "name")
            
            notify_users = set(admin_users)
            if applicant_user:
                notify_users.add(applicant_user)

            for user in notify_users:
                # Skip system/guest users
                if user in ("Administrator", "Guest"):
                    continue

                if user == applicant_user:
                    subject = f"Application Submitted Successfully — {self.name}"
                    msg = (
                        f"Dear <b>{self.candidate_name}</b>,<br><br>"
                        f"Your application for <b>{self.program or 'N/A'}</b> has been successfully submitted (ID: {self.name}).<br>"
                        f"Track your status in the admission portal."
                    )
                else:
                    subject = f"New Application Submitted — {self.name}"
                    msg = (
                        f"<b>{self.candidate_name}</b> has submitted their application "
                        f"for <b>{self.program or 'N/A'}</b> "
                        f"(Cycle: {self.admission_cycle or 'N/A'}, "
                        f"Campus: {self.campus or 'N/A'}).<br><br>"
                        f"Application ID: <b>{self.name}</b><br>"
                        f"Status: <b>{self.application_status or 'Submitted'}</b>"
                    )

                notification = frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": subject,
                    "email_content": msg,
                    "for_user": user,
                    "from_user": frappe.session.user if user != applicant_user else "Administrator",
                    "document_type": "Applicant",
                    "document_name": self.name,
                    "type": "Alert",
                    "read": 0,
                })
                notification.insert(ignore_permissions=True)

            frappe.db.commit()

        except Exception:
            # Non-fatal — log but don't break the submission flow
            frappe.log_error(
                frappe.get_traceback(),
                f"System notification failed for {self.name}"
            )


    def _build_default_email_html(self, ctx):
        """
        Returns the hardcoded HTML email body as a fallback when no
        Email Template is configured on the Admission Cycle.
        """
        html_template = """
<html>
<head>
<meta charset="UTF-8">
<style>
    body {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 14px;
        color: #1a1a1a;
        line-height: 1.7;
        margin: 0;
        padding: 0;
        background: #f0f0f0;
    }
    .wrapper {
        max-width: 600px;
        margin: 32px auto;
        background: #ffffff;
        border: 1px solid #cccccc;
    }
    .header {
        background: #920c24;
        padding: 24px 32px;
        text-align: center;
    }
    .header img {
        max-height: 56px;
        margin-bottom: 10px;
        display: block;
        margin-left: auto;
        margin-right: auto;
    }
    .header h1 {
        color: #ffffff;
        font-size: 16px;
        font-weight: normal;
        letter-spacing: 0.04em;
        margin: 0;
        font-family: Georgia, serif;
    }
    .header .sub {
        color: rgba(255,255,255,0.80);
        font-size: 12px;
        margin-top: 4px;
        font-family: Arial, sans-serif;
    }
    .content {
        padding: 32px 40px;
        font-family: Arial, sans-serif;
    }
    .content p {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: #1a1a1a;
    }
    .ref-box {
        background: #f7f7f7;
        border: 1px solid #dddddd;
        border-left: 4px solid #920c24;
        padding: 14px 18px;
        margin: 20px 0;
        font-family: Arial, sans-serif;
        font-size: 13px;
        color: #1a1a1a;
    }
    .ref-box strong {
        display: block;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #666666;
        margin-bottom: 6px;
    }
    .ref-box .ref-id {
        font-size: 17px;
        font-weight: bold;
        color: #920c24;
        letter-spacing: 0.04em;
    }
    .steps-title {
        font-size: 13px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #555555;
        border-bottom: 1px solid #dddddd;
        padding-bottom: 6px;
        margin: 28px 0 14px 0;
    }
    .step-list {
        margin: 0;
        padding: 0;
        list-style: none;
    }
    .step-list li {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 12px;
        font-size: 13px;
        color: #1a1a1a;
    }
    .step-num {
        background: #920c24;
        color: #ffffff;
        font-size: 11px;
        font-weight: bold;
        min-width: 22px;
        height: 22px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 1px;
        flex-shrink: 0;
    }
    .cta-wrap {
        text-align: center;
        margin: 28px 0 8px 0;
    }
    .cta-link {
        display: inline-block;
        background: #920c24;
        color: #ffffff !important;
        font-size: 13px;
        font-weight: bold;
        padding: 11px 28px;
        text-decoration: none;
        letter-spacing: 0.03em;
        font-family: Arial, sans-serif;
    }
    .cta-fallback {
        text-align: center;
        font-size: 11px;
        color: #888888;
        margin-top: 8px;
        word-break: break-all;
    }
    .cta-fallback a {
        color: #920c24;
    }
    .attachment-note {
        background: #fffbf0;
        border: 1px solid #e8ddb5;
        padding: 11px 16px;
        font-size: 13px;
        color: #4a3c00;
        margin: 24px 0 0 0;
    }
    .footer {
        background: #f7f7f7;
        border-top: 1px solid #dddddd;
        padding: 18px 40px;
        text-align: center;
    }
    .footer .inst-name {
        font-size: 13px;
        font-weight: bold;
        color: #1a1a1a;
        margin-bottom: 4px;
        font-family: Georgia, serif;
    }
    .footer p {
        font-size: 11px;
        color: #888888;
        margin: 3px 0;
        font-family: Arial, sans-serif;
    }
</style>
</head>
<body>
<div class="wrapper">

    <div class="header">
        {% if institution_logo %}
        <img src="{{ institution_logo }}" alt="{{ institution_name }}">
        {% endif %}
        <h1>{{ institution_name }}</h1>
        <div class="sub">Office of Admissions</div>
    </div>

    <div class="content">

        <p>Dear {{ candidate_name }},</p>

        <p>
            We acknowledge receipt of your application to
            <strong>{{ institution_name }}</strong> for the
            <strong>{{ program }}</strong> programme
            for the admission cycle <strong>{{ admission_cycle }}</strong>.
        </p>

        <div class="ref-box">
            <strong>Your Application Reference</strong>
            <span class="ref-id">{{ applicant_id }}</span>
            <span style="font-size:12px;color:#555555;margin-top:4px;display:block;">
                Please quote this reference in all correspondence with the Admissions Office.
            </span>
        </div>

        <p>
            Your completed application form is attached to this email as a PDF.
            Please retain it for your records.
        </p>

        <div class="steps-title">What happens next</div>
        <ul class="step-list">
            <li>
                <span class="step-num">1</span>
                <span>Your application will be reviewed for eligibility. You will be notified by email if any documents or information are required.</span>
            </li>
            <li>
                <span class="step-num">2</span>
                <span>Shortlisted candidates will receive details regarding the entrance test or interview, as applicable to your programme.</span>
            </li>
            <li>
                <span class="step-num">3</span>
                <span>Admit card and examination schedule details will be communicated to eligible candidates in due course.</span>
            </li>
            <li>
                <span class="step-num">4</span>
                <span>You may track the status of your application and complete any pending actions by logging into the admission portal.</span>
            </li>
        </ul>

        <div class="cta-wrap">
            <a class="cta-link" href="{{ admission_portal_url }}" target="_blank" rel="noopener noreferrer">
                Track Your Application
            </a>
        </div>
        <p class="cta-fallback">
            If the button does not open, copy this link into your browser:<br>
            <a href="{{ admission_portal_url }}">{{ admission_portal_url }}</a>
        </p>

        <div class="attachment-note">
            <strong>Note:</strong> Please check your spam or promotions folder if you do not receive further communications. Keep your original documents ready for verification when requested.
        </div>

    </div>

    <div class="footer">
        <p class="inst-name">{{ institution_name }}</p>
        <p>This is a system-generated email. Please do not reply to this message.</p>
        <p>For assistance, contact the Admissions Helpdesk.</p>
        <p style="margin-top:8px;">
            Ref: {{ applicant_id }} &nbsp;|&nbsp; Generated: {{ generated_on }}
        </p>
    </div>

</div>
</body>
</html>
"""
        return frappe.render_template(html_template, ctx)
    # ──────────────────────────────────────────────
    # APPLICANT CATEGORY HELPER
    # ──────────────────────────────────────────────

    def _get_applicant_categories(self):
        """
        Derive the applicant's Admission Category set from the existing
        reservation fields in the eligibility_for_reservation_tab.

        Field → Admission Category mapping (static, matches DB records):
          whether_scstobc_ncl  (not "NA")  →  OBC-NCL / ST / SC
          pwd == "Yes"                     →  PWD
          karnataka_category == "Yes"      →  Karnataka category

        Returns a set of category name strings.
        """
        cats = set()

        if (getattr(self, "ews", None) or "").strip() == "Yes":
            cats.add("EWS")

        sc_st_obc = (getattr(self, "whether_scstobc_ncl", None) or "").strip()
        if sc_st_obc and sc_st_obc.lower() != "na":
            cats.add(sc_st_obc)  # Only include real categories like "OBC-NCL", "ST", or "SC"

        if (getattr(self, "pwd", None) or "").strip() == "Yes":
            cats.add("PWD")

        if (getattr(self, "karnataka_category", None) or "").strip() == "Yes":
            cats.add("Karnataka category")

        return cats

    # ──────────────────────────────────────────────
    # CHILD TABLE VALUE HELPERS
    # ──────────────────────────────────────────────

    def _get_ug_cgpa_values(self):
        """Return a list of all UG CGPA values from the ug_degree_details child table."""
        rows = getattr(self, "ug_degree_details", None) or []
        return [flt(row.ug_cgpa) for row in rows if row.ug_cgpa not in (None, "")]

    def _get_pg_cgpa_values(self):
        """Return a list of all PG CGPA values from the pg_degree_details child table."""
        rows = getattr(self, "pg_degree_details", None) or []
        return [flt(row.pg_cgpa) for row in rows if row.pg_cgpa not in (None, "")]

    @frappe.whitelist()
    def waive_fee(self):
        """Admin marks fee as waived — records who waived and when."""
        self.application_fee_status = "Waived"
        self.fee_waived_by = frappe.session.user
        self.fee_waived_on = frappe.utils.now()
        self.save(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Admission Audit Log",
            "action": "Fee Waived",
            "reference_doctype": "Applicant",
            "reference_name": self.name,
            "performed_by": frappe.session.user,
            "reason": "Application fee waived by admin"
        }).insert(ignore_permissions=True)

    def _get_ug_programs(self):
        """Return a list of all UG programs from the ug_degree_details child table."""
        rows = getattr(self, "ug_degree_details", None) or []
        return [row.ug_program for row in rows if row.ug_program]

    def _get_pg_programs(self):
        """Return a list of all PG programs from the pg_degree_details child table."""
        rows = getattr(self, "pg_degree_details", None) or []
        return [row.pg_program for row in rows if row.pg_program]

    def _get_applicant_hsc_groups(self):
        """
        Return the applicant's HSC group as a set (single value from hsc_group field).
        """
        hsc_group = getattr(self, "hsc_group", None)
        if hsc_group:
            return {hsc_group.strip()}
        return set()

    # ──────────────────────────────────────────────
    # PROGRAM LEVEL HELPER
    # ──────────────────────────────────────────────

    def _get_selected_program_level(self):
        """
        Returns the level_of_study ('Undergraduate', 'Postgraduate', 'Research Course') of the
        currently selected program by querying the Program doctype.

        NOTE: The correct DB column is `level_of_study`.
        `program_level` is a different (often-null) field on older data.

        Returns None if not found.
        """
        if not self.program:
            return None
        return frappe.db.get_value("Program", self.program, "level_of_study")

    def _get_all_programs_for_level(self, program_level):
        """
        Returns programs of the same level that are part of the ACTIVE admission cycle.
        Prioritizes the applicant's linked admission cycle if set.

        This ensures the eligibility table shows programs from the current admission cycle —
        not just EVERY program of the same level from the Program doctype.
        """
        if not program_level:
            return []

        # 1. Use the applicant's cycle if set
        cycle = self.admission_cycle

        # 2. If not set, look for any 'Active' cycle
        if not cycle:
            cycle = frappe.db.get_value("Admission Cycle", {"status": "Active"}, "name")

        if cycle:
            # Fetch programs from the selected cycle that match the level
            # We filter by acp.is_active = 1 (Show on Portal)
            programs = frappe.db.sql("""
                SELECT DISTINCT acp.program
                FROM `tabAdmission Cycle Program` acp
                JOIN `tabProgram` p ON p.name = acp.program
                WHERE acp.parent = %(cycle)s
                  AND acp.is_active = 1
                  AND p.level_of_study = %(program_level)s
                ORDER BY acp.program ASC
            """, {
                "cycle": cycle,
                "program_level": program_level
            }, as_dict=True)

            if programs:
                return [row.program for row in programs if row.program]

        # 3. Fallback: all programs of that level if no cycle or no programs found in cycle
        programs = frappe.db.sql("""
            SELECT name AS program
            FROM `tabProgram`
            WHERE level_of_study = %(program_level)s
            ORDER BY name ASC
        """, {"program_level": program_level}, as_dict=True)

        return [row.program for row in programs if row.program]

    # ──────────────────────────────────────────────
    # CORE ELIGIBILITY LOGIC
    # ──────────────────────────────────────────────

    def validate_eligibility(self):
        """
        Main eligibility entry point.

        Flow:
        ─────
        STEP 0 — National Test Exemption check.
        STEP 1 — Academic Eligibility Rule Mapping checks.

        KEY BEHAVIOUR:
        ─────────────
        On ineligibility:
          1. Sets self.evaluation_status = "Ineligible" and self.rejected_reason.
          2. Calls create_or_update_evaluation() IMMEDIATELY — so the Ineligible
             record is persisted to the Eligibility Evaluation doctype BEFORE the
             throw. Without this, frappe.throw() exits the call stack and the
             save in validate() never runs, meaning ineligible records are lost.
          3. Raises a single frappe.throw() containing:
               • Red reason box  (the specific failure message)
               • Full program table  (all same-level programs + full eligibility check)

        On eligibility:
          1. Sets self.evaluation_status = "Eligible".
          2. Calls create_or_update_evaluation() here (NOT in validate()).
             This prevents the double-save duplicate record bug.
        """

        if not all([self.program, self.campus, self.admission_cycle, self.academic_year]):
            self.evaluation_status = ""
            self.rejected_reason = ""
            self._clear_national_test_flags()
            return

        try:
            # ── STEP 0: National Test Exemption ─────────────────────────────
            national_test_result = self._evaluate_national_test_exemption()

            if national_test_result.get("passed") and national_test_result.get("overrides_academic_rule"):
                # Passed national test AND rule overrides academic checks → Eligible immediately
                self.evaluation_status = "Eligible"
                self.rejected_reason   = ""
                self._apply_national_test_flags(national_test_result)

                # Save the eligible record here (not in validate())
                program_table_html = self._build_program_eligibility_html()
                self.create_or_update_evaluation(program_details_html=program_table_html)

                frappe.msgprint(
                    _("Eligible via National Test ({0}). Academic rule check bypassed.").format(
                        self.national_test_name or ""
                    ),
                    title=_("National Test Exemption Applied"),
                    indicator="green"
                )
                return

            # National test passed but does NOT override → store flags, continue
            if national_test_result.get("passed"):
                self._apply_national_test_flags(national_test_result)
            else:
                self._clear_national_test_flags()

            # ── STEP 1: Academic Eligibility Rule Mapping checks ─────────────
            rule_mappings = self._get_rule_mappings_for_applicant()

            if not rule_mappings:
                # No mapping found → no restriction → eligible
                self.evaluation_status = "Eligible"
                self.rejected_reason   = ""
                # Save eligible record here (not in validate())
                program_table_html = self._build_program_eligibility_html()
                self.create_or_update_evaluation(program_details_html=program_table_html)
                return

            for mapping in rule_mappings:
                is_eligible, failure_message = self._evaluate_mapping_with_category_priority(mapping)

                if not is_eligible:
                    self.evaluation_status  = "Ineligible"
                    self.application_status = "Rejected"
                    self.rejected_reason    = failure_message

                    # ── Build combined HTML: reason box + program table ────────
                    program_table_html = self._build_program_eligibility_html()

                    # ── CRITICAL: Save the Ineligible record NOW, before throw ──
                    # frappe.throw() raises ValidationError which unwinds the stack,
                    # so create_or_update_evaluation() would never execute after throw.
                    # We must save here explicitly before throwing.
                    self.create_or_update_evaluation(program_details_html=program_table_html)

                    full_message = self._build_ineligibility_message(failure_message, program_table_html)

                    # ONE single frappe.throw() — contains reason box + program table
                    # NOTE: allow_dangerous_html=True is required for modern Frappe versions (v15+)
                    # to render styles correctly. We check dynamically to avoid TypeError on older versions.
                    throw_kwargs = {
                        "msg": full_message,
                        "title": _("Eligibility Evaluation Results"),
                        "wide": True,
                    }

                    import inspect
                    if "allow_dangerous_html" in inspect.signature(frappe.throw).parameters:
                        throw_kwargs["allow_dangerous_html"] = True

                    frappe.throw(**throw_kwargs)
                    return

            # Passed all mappings → Eligible
            self.evaluation_status = "Eligible"
            self.rejected_reason   = ""
            program_table_html = self._build_program_eligibility_html()
            self.create_or_update_evaluation(program_details_html=program_table_html)

        except frappe.ValidationError:
            # Standard validation failure — let it raise naturally for the frontend
            raise
        except Exception:
            # Unexpected system error — log it to Error Log then raise
            frappe.log_error(frappe.get_traceback(), "Applicant Eligibility Validation Error")
            raise

    # ──────────────────────────────────────────────
    # INELIGIBILITY MESSAGE BUILDER  (Frappe-native)
    # ──────────────────────────────────────────────

    def _build_ineligibility_message(self, failure_message, program_table_html):
        """
        Builds a high-end, premium ineligibility message with focused styling for 
        required vs secured scores and specific eligibility mismatches.
        """
        # Split combined message if it contains '|' (multi-reason support)
        reasons_list = []
        if "|" in failure_message:
            parts = failure_message.split("|")
            main_reason = parts[0].strip()
            sub_reasons = " ".join(parts[1:]).strip()
            reason_html = (
                f"{frappe.utils.escape_html(main_reason)}"
                f"<div style='font-weight: 400; font-size: 12px; color: #666; margin-top: 4px;'>"
                f"{frappe.utils.escape_html(sub_reasons)}</div>"
            )
        else:
            reason_html = frappe.utils.escape_html(failure_message)

        return (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
            '<!-- ── Ineligibility Alert ───────────────────────────────── -->'
            '<div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; padding: 12px 16px; '
            'background-color: #fff2f2; border: 1px solid #f5c6cb; border-left: 4px solid #e74c3c; border-radius: 6px;">'
            '<span style="display: inline-block; width: 10px; height: 10px; background-color: #e74c3c; border-radius: 50%; '
            'margin-top: 4px; flex-shrink: 0;"></span>'
            '<div>'
            '<div style="font-weight: 600; font-size: 14px; color: #c0392b;">{reason}</div>'
            '<div style="font-size: 12px; color: #666; margin-top: 3px;">{note}</div>'
            '</div>'
            '</div>'
            '<!-- ── Program Options ───────────────────────────────────── -->'
            '{table}'
            '</div>'
        ).format(
            reason=reason_html,
            note=_("The applicant does not meet the eligibility criteria for the selected program."),
            table=program_table_html,
        )

    # ──────────────────────────────────────────────
    # PROGRAM ELIGIBILITY TABLE (rendered inside throw)
    # ──────────────────────────────────────────────

    def _build_program_eligibility_data(self):
        """
        Returns a list of dicts for EVERY program of the SAME LEVEL as the
        applicant's selected program (UG / PG / Research Course).
        Used by the portal 'Switch Program' feature.
        """
        selected_program_level = self._get_selected_program_level()
        if not selected_program_level:
            return []

        all_programs = self._get_all_programs_for_level(selected_program_level)
        if not all_programs:
            return []

        data = []
        for prog_name in all_programs:
            is_eligible, reason = self._check_eligibility_for_program(prog_name)
            data.append({
                "program": prog_name,
                "eligible": is_eligible,
                "reason": reason
            })
        return data

    def _build_program_eligibility_html(self):
        """
        Returns styled HTML listing EVERY program of the SAME LEVEL as the
        applicant's selected program (UG / PG / Research Course).

        FIX — Previously only showed programs that had eligibility rules configured.
        Now shows ALL programs from the Program doctype with matching program_level:
          • Programs WITH eligibility rules → full eligibility check (pass/fail + reason)
          • Programs WITHOUT eligibility rules → shown as "Eligible" (no restriction)
          • Programs of a DIFFERENT level (e.g., PG when applicant applied for UG)
            are completely excluded — they are irrelevant to the applicant.

        The currently selected program is marked with a "Selected" badge.
        """

        # Get the level of the selected program (UG / PG / Research Course)
        selected_program_level = self._get_selected_program_level()

        if not selected_program_level:
            return (
                "<p style='color:#888;font-size:12px;'>{0}</p>".format(
                    _("Could not determine program level for the selected program.")
                )
            )

        # Get ALL programs of the same level from Program doctype
        all_programs = self._get_all_programs_for_level(selected_program_level)

        if not all_programs:
            return (
                "<p style='color:#888;font-size:12px;'>{0}</p>".format(
                    _("No programs found for program level: {0}").format(selected_program_level)
                )
            )

        rows_html        = ""
        eligible_count   = 0
        ineligible_count = 0

        for prog_name in all_programs:
            is_prog_eligible, reason = self._check_eligibility_for_program(prog_name)
            is_selected = (prog_name == self.program)

            if not is_prog_eligible:
                ineligible_count += 1
                continue

            eligible_count += 1
            dot_color    = "#27ae60"
            status_label = _("Eligible")
            status_color = "#27ae60"
            row_bg       = "#fff"

            # Program name cell — bold + "Selected" badge for the active program
            if is_selected:
                prog_display = """
                    <strong style="color:#2c3e50;">{name}</strong>
                    &nbsp;<span style="
                        font-size: 10px;
                        padding: 2px 8px;
                        background-color: #3498db;
                        color: #fff;
                        border-radius: 10px;
                        font-weight: 600;
                        vertical-align: middle;
                    ">{label}</span>
                """.format(
                    name  = frappe.utils.escape_html(prog_name),
                    label = _("Selected"),
                )
            else:
                prog_display = "<span style='color:#2c3e50;'>{0}</span>".format(
                    frappe.utils.escape_html(prog_name)
                )

            rows_html += """
                <tr style="background-color:{row_bg};">
                    <td style="padding:10px 12px;vertical-align:middle;border-bottom:1px solid #eee;">
                        {prog}
                    </td>
                    <td style="padding:10px 12px;vertical-align:middle;text-align:center;white-space:nowrap;border-bottom:1px solid #eee;">
                        <span style="
                            display: inline-block;
                            width: 8px;
                            height: 8px;
                            background-color: {dot};
                            border-radius: 50%;
                            vertical-align: middle;
                            margin-right: 4px;
                        "></span>
                        <span style="font-size:13px;font-weight:500;color:{status_color};">{status}</span>
                    </td>
                </tr>
            """.format(
                row_bg       = row_bg,
                prog         = prog_display,
                dot          = dot_color,
                status_color = status_color,
                status       = status_label,
            )

        # ── Summary counts ───────────────────────────────────────────────────
        summary_html = (
            '<div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;flex-wrap:wrap;">'
            '<span style="display:inline-flex;align-items:center;gap:6px;">'
            '<span style="display:inline-block;width:8px;height:8px;background:#27ae60;border-radius:50%;"></span>'
            '<strong style="color:#2c3e50;">{ec}</strong>'
            '<span style="font-size:12px;color:#888;">{el}</span>'
            '</span>'
            '<span style="font-size:12px;color:#aaa;">({total}&nbsp;{tl})</span>'
            '</div>'
        ).format(
            ec    = eligible_count,
            el    = _("eligible programs found"),
            total = eligible_count + ineligible_count,
            tl    = _("total same-level programs"),
        )

        # ── Section heading ──────────────────────────────────────────────────
        heading_html = (
            '<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px;">'
            '<span style="font-weight:700;font-size:14px;color:#2c3e50;">{heading}</span>'
            '<span style="font-size:12px;color:#888;">&mdash;&nbsp;{campus}&nbsp;&middot;&nbsp;{cycle}&nbsp;&middot;&nbsp;{level}</span>'
            '</div>'
        ).format(
            heading = _("Suggested Eligible Programs"),
            campus  = frappe.utils.escape_html(self.campus or ""),
            cycle   = frappe.utils.escape_html(self.admission_cycle or ""),
            level   = frappe.utils.escape_html(selected_program_level or ""),
        )

        # ── Full table ───────────────────────────────────────────────────────
        table_html = (
            '<div style="margin-top:8px;">'
            '{heading}'
            '<hr style="margin:6px 0 12px 0;border:none;border-top:1px solid #eee;">'
            '{summary}'
            '<div style="overflow-x:auto;">'
            '<table style="width: 100%; border-collapse: collapse; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; font-size: 13px;">'
            '<thead>'
            '<tr style="background-color:#f8f9fa;">'
            '<th style="padding:10px 12px;text-align:left;font-weight:600;color:#555;width:70%;border-bottom:2px solid #e0e0e0;">{col1}</th>'
            '<th style="padding:10px 12px;text-align:center;font-weight:600;color:#555;border-bottom:2px solid #e0e0e0;">{col2}</th>'
            '</tr>'
            '</thead>'
            '<tbody>'
            '{rows}'
            '</tbody>'
            '</table>'
            '</div>'
            '</div>'
        ).format(
            heading = heading_html,
            summary = summary_html,
            col1    = _("Program"),
            col2    = _("Status"),
            rows    = rows_html,
        )

        return table_html

    def _check_eligibility_for_program(self, program_name):
        """
        Runs the full eligibility engine for a given program using the current
        applicant's scores, categories, campus, admission_cycle, and academic_year —
        WITHOUT permanently modifying self.

        Temporarily swaps self.program → runs check → restores original in finally.

        KEY BEHAVIOUR for programs WITHOUT eligibility rules:
          If no rule mappings exist for a program, it is treated as Eligible
          (no restriction configured = open to all applicants of that level).

        Returns (is_eligible: bool, failure_message: str)
        """
        original_program = self.program
        try:
            self.program = program_name

            # National test exemption for this program
            national_test_result = self._evaluate_national_test_exemption()
            if (national_test_result.get("passed")
                    and national_test_result.get("overrides_academic_rule")):
                return True, ""

            # Rule mappings for this program (direct link now)
            rule_mappings = frappe.db.sql("""
                SELECT erm.name, erm.failure_message
                FROM `tabEligibility Rule Mapping` erm
                WHERE erm.is_active       = 1
                  AND erm.campus          = %(campus)s
                  AND erm.admission_cycle = %(admission_cycle)s
                  AND erm.program         = %(program)s
            """, {
                "campus":          self.campus,
                "admission_cycle": self.admission_cycle,
                "program":         program_name,
            }, as_dict=True)

            # No rule mapping → no restriction → eligible
            if not rule_mappings:
                return True, ""

            for mapping in rule_mappings:
                is_eligible, failure_message = self._evaluate_mapping_with_category_priority(mapping)
                if not is_eligible:
                    return False, failure_message

            return True, ""

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "Program Eligibility Check Error — {0}".format(program_name)
            )
            return False, _("Error during eligibility check")

        finally:
            # Always restore original — even if exception occurs
            self.program = original_program

    # ──────────────────────────────────────────────
    # NATIONAL TEST EXEMPTION
    # ──────────────────────────────────────────────

    def _evaluate_national_test_exemption(self):
        """
        Check if the applicant qualifies under a National Test Exemption Rule.

        Returns a dict:
        {
            "passed":                  bool,
            "overrides_academic_rule": bool,
            "exempts_entrance_test":   bool,
            "exempts_interview":       bool,
            "rule_name":               str,
        }
        """
        empty = {
            "passed":                  False,
            "overrides_academic_rule": False,
            "exempts_entrance_test":   False,
            "exempts_interview":       False,
            "rule_name":               "",
        }

        national_test = getattr(self, "national_test_name", None)
        applicant_pct = flt(getattr(self, "percentage", None) or 0)

        if not national_test:
            return empty

        exemption_rules = frappe.db.sql("""
            SELECT
                nter.name,
                nter.mark_percentage,
                nter.operator,
                nter.overrides_academic_rule,
                nter.exempts_entrance_test,
                nter.exempts_interview
            FROM `tabNational Test Exemption Rule` nter
            INNER JOIN `tabEligibility Allowed Degree` ead
                ON ead.parent      = nter.name
               AND ead.degree_name = %(program)s
            WHERE nter.is_active        = 1
              AND nter.campus           = %(campus)s
              AND nter.admission_cycle  = %(admission_cycle)s
              AND nter.academic_year    = %(academic_year)s
              AND nter.national_test    = %(national_test)s
              AND %(today)s BETWEEN nter.valid_from AND nter.valid_until
            ORDER BY nter.mark_percentage DESC
            LIMIT 1
        """, {
            "program":         self.program,
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "academic_year":   self.academic_year,
            "national_test":   national_test,
            "today":           nowdate(),
        }, as_dict=True)

        if not exemption_rules:
            return empty

        rule         = exemption_rules[0]
        required_pct = flt(rule.get("mark_percentage") or 0)
        operator     = rule.get("operator") or ">="
        passed       = self._compare(applicant_pct, required_pct, operator)

        return {
            "passed":                  passed,
            "overrides_academic_rule": bool(rule.get("overrides_academic_rule")),
            "exempts_entrance_test":   bool(rule.get("exempts_entrance_test")),
            "exempts_interview":       bool(rule.get("exempts_interview")),
            "rule_name":               rule.get("name", ""),
        }

    def _apply_national_test_flags(self, result):
        self.exempts_entrance_test   = 1 if result.get("exempts_entrance_test")   else 0
        self.exempts_interview       = 1 if result.get("exempts_interview")        else 0
        self.national_test_rule_used = result.get("rule_name", "")

    def _clear_national_test_flags(self):
        self.exempts_entrance_test   = 0
        self.exempts_interview       = 0
        self.national_test_rule_used = ""

    # ──────────────────────────────────────────────
    # STEP 1 — Fetch matching rule mappings
    # ──────────────────────────────────────────────

    def _get_rule_mappings_for_applicant(self):
        return frappe.db.sql("""
            SELECT erm.name, erm.failure_message
            FROM `tabEligibility Rule Mapping` erm
            WHERE erm.is_active         = 1
              AND erm.campus            = %(campus)s
              AND erm.admission_cycle   = %(admission_cycle)s
              AND erm.program           = %(program)s
        """, {
            "campus":          self.campus,
            "admission_cycle": self.admission_cycle,
            "program":         self.program,
        }, as_dict=True)

    # ──────────────────────────────────────────────
    # STEP 2 — Multi-category priority engine
    # ──────────────────────────────────────────────

    def _build_rule_failure_reason(self, base_rule, required_val):
        """
        Constructs a detailed failure reason for a specific rule failure.
        Captures: Required vs Secured scores/CGPA and Ineligible HSC Group details.
        """
        reasons = []
        qualification_level = base_rule.get("qualification_level") or "Academic"
        rule_type           = base_rule.get("rule_type")
        operator            = base_rule.get("operator") or ">="
        
        # Determine unit symbol
        unit = ""
        is_cgpa = (rule_type == "CGPA" or "cgpa" in (base_rule.get("unit_type") or "").lower())
        if is_cgpa:
            unit = " CGPA"
        else:
            unit = "%"

        # Special label for XII as HSE
        display_level = "HSE (Class XII)" if qualification_level == "XII" else qualification_level

        # 1. Academic Threshold Check (Score/Percentage/CGPA)
        applicant_val = self._get_applicant_value(base_rule)
        
        # If a required value exists, check if it failed due to low score.
        # Hide the score comparison if Secured is 0.0 (confusing placeholders for missing data)
        # unless it's a specific requirement for entry.
        if required_val and applicant_val > 0 and not self._compare(applicant_val, required_val, operator):
            # User specifically asked for "required percentage [val] and you have to mention what they are secured"
            reasons.append(_("{0} Score — Required: {1}{2}, Secured: {3}{2}").format(
                display_level, required_val, unit, applicant_val
            ))

        # 2. Non-percentage checks (HSC Group / Degree)
        if not self._evaluate_non_percentage_checks(base_rule):
            # HSC Group failure detail
            if rule_type == "HSC Group" and not self._check_hsc_group_eligibility(base_rule.name):
                # Get applicant's secured group
                applicant_group = (getattr(self, "hsc_group", None) or "").strip() or _("Not provided")
                # Mention the ineligible group as requested
                reasons.append(_("Ineligible {0} Group: '{1}' is not allowed for this program.").format(display_level, applicant_group))
            
            # Detailed mismatch for Allowed Degrees
            else:
                # 1. Fetch allowed degrees directly from DB
                rule_allowed = frappe.get_all("Eligibility Allowed Degree", 
                                            filters={"parent": base_rule.name}, 
                                            pluck="degree_name")
                
                # 2. Identify Applicant's studied degrees
                applicant_studied = []
                if qualification_level == "Undergraduate":
                    applicant_studied = [r.ug_program for r in (self.get("ug_degree_details") or []) if r.ug_program]
                elif qualification_level == "Postgraduate":
                    applicant_studied = [r.pg_program for r in (self.get("pg_degree_details") or []) if r.pg_program]
                
                # 3. Construct the message
                if rule_allowed:
                    # e.g. "Required Undergraduate Degree: BCA"
                    req_msg = _("Required {0} Degree: {1}").format(display_level, ", ".join(rule_allowed))
                    
                    # e.g. "But you have studied: B.A English"
                    studied_val = ", ".join(applicant_studied) if applicant_studied else _("Not provided")
                    usr_msg = _("But you have studied: {0}").format(studied_val)
                    
                    # Combine with pipe for the toast bullet renderer
                    reasons.append(f"{req_msg} | {usr_msg}")
                elif not reasons:
                    # Fallback generic mismatch message only if no other details exist
                    reasons.append(_("Program mismatch for {0} qualification.").format(display_level))

        # 3. Custom message from rule (e.g. "this is an ineligible message. ajay basker")
        custom_rule_msg = (base_rule.get("ineligible_message") or "").strip()
        if custom_rule_msg:
            # Avoid repeating the exact same message
            if custom_rule_msg not in reasons:
                reasons.append(custom_rule_msg)

        return " | ".join(reasons)

    def _evaluate_mapping_with_category_priority(self, mapping):
        """
        Comprehensive eligibility engine:
        Checks ALL categories the applicant belongs to (against the mapping table)
        AND the 'General' (default) path using 'OR' logic.

        Result: Eligible if ANY (Category, Rule) combination passes.
        """
        mapping_name = mapping.get("name")
        failure_msg  = (mapping.get("failure_message") or "").strip() or \
            "You do not meet the eligibility criteria for the selected program."

        # 1. Fetch ALL rules for this mapping
        rules_in_mapping = frappe.db.get_all("Rule Mapping",
            filters={"parent": mapping_name},
            fields=["rule"]
        )

        if not rules_in_mapping:
            return True, ""

        # 2. Get reservation overrides defined for this mapping
        reservation_rows = frappe.db.sql("""
            SELECT category, priority, minimum_percentage
            FROM `tabRule Mapping Category`
            WHERE parent = %(mapping_name)s
            ORDER BY priority ASC
        """, {"mapping_name": mapping_name}, as_dict=True)

        # 3. Identify all evaluation paths (Matched categories + General)
        applicant_categories = self._get_applicant_categories()
        
        # Path 1: Categories matching the mapping table
        matched_categories = [
            row for row in reservation_rows
            if (row.category or "").strip() in applicant_categories
        ]
        
        # evaluation_paths = [MatchedCategoryRow1, MatchedCategoryRow2, ..., None (for General)]
        evaluation_paths = matched_categories + [None]

        # Collect rule-specific ineligible messages to show if ALL paths fail
        ineligible_messages = []

        # 4. Nested OR Evaluation: Success if ANY (Path, Rule) combination passes
        for cat_row in evaluation_paths:
            for r_row in rules_in_mapping:
                base_rule = self._get_base_rule(r_row.rule)
                if not base_rule:
                    continue

                # Threshold: Category Override or Rule Default
                if cat_row:
                    required_val = flt(cat_row.minimum_percentage)
                else:
                    required_val = self._get_required_value(base_rule)

                operator = (base_rule.get("operator") or ">=")
                
                # Perform academic value comparison
                passes_threshold = self._compare_any_academic_value(base_rule, required_val, operator)
                # Perform non-percentage checks (Degrees/HSC Groups)
                passes_non_percentage = self._evaluate_non_percentage_checks(base_rule)

                if passes_threshold and passes_non_percentage:
                    # ELIGIBLE: Found a valid qualifying path
                    self._set_applied_category_info(
                        category=cat_row.category if cat_row else "General",
                        priority=cat_row.priority if cat_row else None,
                        minimum=required_val
                    )
                    return True, ""
                else:
                    # If this specific rule failed, collect its detailed failure reason
                    rule_msg = self._build_rule_failure_reason(base_rule, required_val)
                    if rule_msg:
                        # Append with Pipe separator
                        ineligible_messages.append(rule_msg)

        # If all paths and all rules failed, combine the mapping-level failure_message
        # with the specific ineligible_message(s) from the rules.
        final_message = failure_msg
        if ineligible_messages:
            # deduplicate and handle multi-part messages
            unique_parts = []
            for m in ineligible_messages:
                parts = [p.strip() for p in (m or "").split("|") if p.strip()]
                for p in parts:
                    if p and p not in unique_parts:
                        unique_parts.append(p)
            
            if unique_parts:
                final_message = f"{failure_msg} | {' | '.join(unique_parts)}"

        return False, final_message



    # ──────────────────────────────────────────────
    # STEP 3 — Base rule fetch
    # ──────────────────────────────────────────────

    def _get_base_rule(self, rule_name):
        if not rule_name:
            return None

        rules = frappe.db.sql("""
            SELECT *
            FROM `tabEligibility Rule`
            WHERE name            = %(rule_name)s
              AND is_active       = 1
              AND campus          = %(campus)s
              AND academic_year   = %(academic_year)s
              AND %(today)s BETWEEN effective_from AND effective_to
        """, {
            "rule_name":     rule_name,
            "campus":        self.campus,
            "academic_year": self.academic_year,
            "today":         nowdate(),
        }, as_dict=True)

        return rules[0] if rules else None

    # ──────────────────────────────────────────────
    # NON-PERCENTAGE CHECKS (used in CASE A)
    # ──────────────────────────────────────────────

    def _evaluate_non_percentage_checks(self, rule):
        """
        Run only the non-percentage checks from the base rule:
          - Allowed Degree check  (any matching UG or PG program qualifies)
          - HSC Group check       (multi-group: passes if applicant's group is in
                                   the rule's hsc_group child table)
        """
        rule_type           = rule.get("rule_type")
        qualification_level = rule.get("qualification_level")
        rule_name           = rule.get("name")

        allowed_degrees = frappe.db.sql("""
            SELECT degree_name
            FROM `tabEligibility Allowed Degree`
            WHERE parent = %(rule_name)s
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_degree_list = [r.degree_name for r in allowed_degrees if r.degree_name]

        if allowed_degree_list:
            if qualification_level == "Postgraduate":
                applicant_degrees = self._get_pg_programs()
            else:
                applicant_degrees = self._get_ug_programs()

            if not any(deg in allowed_degree_list for deg in applicant_degrees):
                return False

        if rule_type == "HSC Group":
            if not self._check_hsc_group_eligibility(rule_name):
                return False

        return True

    # ──────────────────────────────────────────────
    # HSC GROUP CHECK — multi-group support
    # ──────────────────────────────────────────────

    def _check_hsc_group_eligibility(self, rule_name):
        """
        Check if the applicant's HSC group is in the list of allowed HSC groups
        defined in the Eligibility Rule's hsc_group child table (HSC Groups Mapping).

        Returns True if applicant's group matches any allowed group in the rule,
        or if the rule has NO groups defined (no restriction).
        """
        allowed_groups_rows = frappe.db.sql("""
            SELECT hsc_groups
            FROM `tabHSC Groups Mapping`
            WHERE parent = %(rule_name)s
              AND parenttype = 'Eligibility Rule'
              AND hsc_groups IS NOT NULL
              AND hsc_groups != ''
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_hsc_groups = [
            row.hsc_groups.strip()
            for row in allowed_groups_rows
            if row.hsc_groups
        ]

        # If no groups are configured in the rule → no restriction → pass
        if not allowed_hsc_groups:
            return True

        # Get applicant's HSC group
        applicant_hsc_group = (getattr(self, "hsc_group", None) or "").strip()

        if not applicant_hsc_group:
            return False

        return applicant_hsc_group in allowed_hsc_groups

    # ──────────────────────────────────────────────
    # RULE EVALUATION (single base rule — full check)
    # ──────────────────────────────────────────────

    def evaluate_single_rule(self, rule):
        """
        Full evaluation of a base Eligibility Rule against the applicant.
        Checks: Allowed Degrees, HSC Group (multi-group), and numeric threshold
        (Percentage / CGPA).
        """
        rule_type           = rule.get("rule_type")
        qualification_level = rule.get("qualification_level")
        operator            = rule.get("operator") or ">="
        rule_name           = rule.get("name")

        allowed_degrees = frappe.db.sql("""
            SELECT degree_name
            FROM `tabEligibility Allowed Degree`
            WHERE parent = %(rule_name)s
        """, {"rule_name": rule_name}, as_dict=True)

        allowed_degree_list = [r.degree_name for r in allowed_degrees if r.degree_name]

        # ── HSC Group check (multi-group via child table) ────────────────────
        if rule_type == "HSC Group":
            if not self._check_hsc_group_eligibility(rule_name):
                return False

        if qualification_level in ("Undergraduate", "Postgraduate"):
            required_value = self.get_required_academic_value(rule)

            if qualification_level == "Undergraduate":
                child_rows = getattr(self, "ug_degree_details", None) or []
            else:
                child_rows = getattr(self, "pg_degree_details", None) or []

            if not child_rows:
                return False

            for row in child_rows:
                program_field = "ug_program" if qualification_level == "Undergraduate" else "pg_program"
                cgpa_field    = "ug_cgpa"    if qualification_level == "Undergraduate" else "pg_cgpa"

                row_program = getattr(row, program_field, None)
                row_cgpa    = flt(getattr(row, cgpa_field, None) or 0)

                if allowed_degree_list and row_program not in allowed_degree_list:
                    continue

                if rule_type in ("CGPA", "Percentage"):
                    if required_value is None:
                        continue
                    if not self._compare(row_cgpa, required_value, operator):
                        continue

                return True

            return False

        if rule_type in ("HSC Group", "Percentage"):
            applicant_value = flt(getattr(self, "hsc_percentage", None) or 0)
            required_value  = self.get_required_academic_value(rule)

            if required_value is None:
                return False

            return self._compare(applicant_value, required_value, operator)

        return True

    # ──────────────────────────────────────────────
    # MULTI-DEGREE ACADEMIC VALUE CHECK (CASE A)
    # ──────────────────────────────────────────────

    def _compare_any_academic_value(self, rule, required_min, operator):
        if not rule:
            return self._compare(flt(getattr(self, "hsc_percentage", 0) or 0), required_min, operator)

        qualification_level = rule.get("qualification_level")

        if qualification_level == "XII":
            value = flt(getattr(self, "hsc_percentage", None) or 0)
            return self._compare(value, required_min, operator)

        elif qualification_level == "Undergraduate":
            values = self._get_ug_cgpa_values()
            if not values:
                return False
            return any(self._compare(v, required_min, operator) for v in values)

        elif qualification_level == "Postgraduate":
            values = self._get_pg_cgpa_values()
            if not values:
                return False
            return any(self._compare(v, required_min, operator) for v in values)

        return False

    # ──────────────────────────────────────────────
    # VALUE HELPERS
    # ──────────────────────────────────────────────

    def _get_applicant_value(self, rule):
        if not rule:
            return flt(getattr(self, "hsc_percentage", 0) or 0)

        qualification_level = rule.get("qualification_level")

        if qualification_level == "XII":
            return flt(getattr(self, "hsc_percentage", None) or 0)
        elif qualification_level == "Undergraduate":
            values = self._get_ug_cgpa_values()
            return max(values) if values else 0.0
        elif qualification_level == "Postgraduate":
            values = self._get_pg_cgpa_values()
            return max(values) if values else 0.0

        return 0.0

    def _get_required_value(self, rule):
        if not rule:
            return None
        return self.get_required_academic_value(rule)

    def get_applicant_academic_value(self, qualification_level):
        if qualification_level == "XII":
            return flt(getattr(self, "hsc_percentage", None) or 0)
        if qualification_level == "Undergraduate":
            values = self._get_ug_cgpa_values()
            return max(values) if values else None
        if qualification_level == "Postgraduate":
            values = self._get_pg_cgpa_values()
            return max(values) if values else None
        return None

    def get_required_academic_value(self, rule):
        if rule.get("required_percentage"):
            return flt(rule["required_percentage"])
        if rule.get("required_cgpa"):
            return flt(rule["required_cgpa"])
        if rule.get("required_score"):
            return flt(rule["required_score"])
        return None

    def _compare(self, actual, required, operator):
        try:
            actual   = flt(actual)
            required = flt(required)
            if operator == ">=":
                return actual >= required
            elif operator == "<=":
                return actual <= required
            elif operator == "=":
                return actual == required
        except Exception:
            pass
        return False

    def compare_values(self, actual, required, operator):
        return self._compare(actual, required, operator)

    def _set_applied_category_info(self, category, priority, minimum):
        self.applied_category = category
        self.applied_priority = priority if priority is not None else ""
        self.applied_minimum  = minimum

    # ──────────────────────────────────────────────
    # CREATE / UPDATE ELIGIBILITY EVALUATION RECORD
    # ──────────────────────────────────────────────

    def create_or_update_evaluation(self, program_details_html=None):
        """
        Saves (insert or update) an Eligibility Evaluation record for this applicant.

        FIX — Duplicate Record Prevention:
        ────────────────────────────────────
        This method is now called ONLY from within validate_eligibility():
          • Ineligible path: called before frappe.throw() — required because throw
            exits the call stack before validate() can complete normally.
          • Eligible path: called at the end of validate_eligibility() directly.

        It is NO LONGER called separately from validate(). This eliminates the
        duplicate save that was occurring previously.

        The upsert logic (get existing → update OR insert new) prevents duplicate
        records even if called more than once for the same applicant.
        """
        if not all([self.program, self.campus, self.admission_cycle, self.academic_year]):
            return

        applicant_name = self.name or "New Applicant"

        existing = frappe.db.get_value(
            "Eligibility Evaluation",
            {"applicant_name": applicant_name},
            "name"
        )

        current_status = getattr(self, "evaluation_status", None) or "Eligible"
        current_reason = getattr(self, "rejected_reason", None) or ""

        exempts_entrance_test   = getattr(self, "exempts_entrance_test",   0)
        exempts_interview       = getattr(self, "exempts_interview",       0)
        national_test_rule_used = getattr(self, "national_test_rule_used", "")

        doc_data = {
            "doctype":                 "Eligibility Evaluation",
            "applicant_name":          applicant_name,
            "academic_year":           self.academic_year,
            "admission_cycle":         self.admission_cycle,
            "program":                 self.program,
            "campus":                  self.campus,
            "evaluation_status":       current_status,
            "failure_message":         current_reason,
            "exempts_entrance_test":   exempts_entrance_test,
            "exempts_interview":       exempts_interview,
            "national_test_rule_used": national_test_rule_used,
            "program_eligibility_details": program_details_html,
            "reservation_category": [
                {"category": cat}
                for cat in self._get_applicant_categories()
            ]
        }

        if existing:
            doc = frappe.get_doc("Eligibility Evaluation", existing)
            doc.update(doc_data)
        else:
            doc = frappe.get_doc(doc_data)

        try:
            doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.logger().warning(
                f"Failed to save Eligibility Evaluation for {applicant_name}: {str(e)}"
            )


# ──────────────────────────────────────────────
# SUBMISSION APPLICATION STATUS (from national test exemption)
# ──────────────────────────────────────────────


def _truthy(val):
    """Treat 1, True, '1' as True; 0, False, None as False."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    return str(val).strip().lower() in ("1", "true", "yes")


def _application_status_from_exemption_flags(exempts_entrance_test, exempts_interview):
    """
    Return Applicant Status name from exemption flags.
    - Both exempt → "Excempted Entrance Test And Interview"
    - Only interview exempt → "Interview Excempted"
    - Only entrance test exempt → "Entrance Test Exempted"
    - Neither → "Submitted"
    """
    if _truthy(exempts_entrance_test) and _truthy(exempts_interview):
        return "Excempted Entrance Test And Interview"
    if _truthy(exempts_interview):
        return "Interview Excempted"
    if _truthy(exempts_entrance_test):
        return "Entrance Test Exempted"
    return "Submitted"


def _get_eligibility_evaluation_for_applicant(applicant_name, applicant_id=None):
    """Get Eligibility Evaluation by applicant_name (doc name) or applicant_id. Returns dict or None."""
    for key in [applicant_name, applicant_id]:
        if not key:
            continue
        ev = frappe.db.get_value(
            "Eligibility Evaluation",
            {"applicant_name": key},
            ["evaluation_status", "exempts_entrance_test", "exempts_interview"],
            as_dict=True,
        )
        if ev:
            return ev
    return None


def _sync_application_status_from_eligibility_evaluation(applicant_doc):
    """
    If the applicant is "Submitted" but has an Eligibility Evaluation that is Eligible
    with exemption flags, set application_status from that Evaluation so it shows
    "Entrance Test Exempted" / "Interview Excempted" / "Excempted Entrance Test And Interview".
    """
    if not getattr(applicant_doc, "name", None):
        return
    ev = _get_eligibility_evaluation_for_applicant(
        applicant_doc.name,
        getattr(applicant_doc, "applicant_id", None),
    )
    if not ev or ev.get("evaluation_status") != "Eligible":
        return
    if not _truthy(ev.get("exempts_entrance_test")) and not _truthy(ev.get("exempts_interview")):
        return
    new_status = _application_status_from_exemption_flags(
        ev.get("exempts_entrance_test"), ev.get("exempts_interview")
    )
    if new_status and new_status != "Submitted" and frappe.db.exists("Applicant Status", new_status):
        applicant_doc.application_status = new_status


def _get_submission_application_status(applicant_doc):
    """
    When the student submits, return application_status from national test exemption flags.
    """
    exempt_et = getattr(applicant_doc, "exempts_entrance_test", 0)
    exempt_int = getattr(applicant_doc, "exempts_interview", 0)
    status = _application_status_from_exemption_flags(exempt_et, exempt_int)
    if status == "Submitted":
        return status
    if frappe.db.exists("Applicant Status", status):
        return status
    frappe.log_error(
        message=f"Applicant Status '{status}' does not exist. Using 'Submitted'.",
        title="Applicant Status Fallback",
    )
    return "Submitted"


# ──────────────────────────────────────────────
# WHITELIST API
# ──────────────────────────────────────────────


@frappe.whitelist()
def get_eligible_programs_for_campus(campus, admission_cycle):
    programs = frappe.db.sql("""
        SELECT DISTINCT erm.program
        FROM `tabEligibility Rule Mapping` erm
        WHERE erm.is_active         = 1
          AND erm.campus            = %(campus)s
          AND erm.admission_cycle   = %(admission_cycle)s
    """, {
        "campus":          campus,
        "admission_cycle": admission_cycle,
    }, as_dict=True)

    return [p.program for p in programs if p.program]


# ──────────────────────────────────────────────
# Async helper — create Eligibility Evaluation
# ──────────────────────────────────────────────


def create_eligibility_evaluation_async(
    applicant_name, status, failure_msg, categories,
    program, campus, admission_cycle, academic_year
):
    """Create or update Eligibility Evaluation record."""

    if not all([program, campus, admission_cycle, academic_year]):
        return

    existing = frappe.db.get_value(
        "Eligibility Evaluation",
        filters={"applicant_name": applicant_name},
        fieldname="name"
    )

    eval_data = {
        "doctype":           "Eligibility Evaluation",
        "applicant_name":    applicant_name,
        "academic_year":     academic_year,
        "admission_cycle":   admission_cycle,
        "program":           program,
        "campus":            campus,
        "evaluation_status": status,
        "failure_message":   failure_msg,
        "reservation_category": [
            {
                "category": row.get("category") if isinstance(row, dict) else row.category
            }
            for row in (categories or [])
        ] if categories else [],
    }

    if existing:
        doc = frappe.get_doc("Eligibility Evaluation", existing)
        doc.update(eval_data)
    else:
        doc = frappe.get_doc(eval_data)

    doc.save(ignore_permissions=True)


# ──────────────────────────────────────────────
# Hook functions
# ──────────────────────────────────────────────


def validate_applicant(doc, method):
    """Called via hooks.py doc_events validate"""
    doc.validate_eligibility()


def before_submit_applicant(doc, method):
    """Called via hooks.py doc_events before_submit"""
    if doc.evaluation_status == "Ineligible":
        frappe.throw(
            _("Not Eligible: {0}").format(
                doc.rejected_reason or "You are not eligible for the selected program."
            ),
            title=_("Submission Not Allowed")
        )

def set_intake_type(doc, method=None):
    """
    Copy intake_type from the linked Program.
    Program is the source of truth for intake type.
    BA LLB / BCom LLB / BBA LLB = CLAT
    LLM / LLM Business Law       = NLSAT
    PhD Law                      = Direct Merit
    """
    if doc.program:
        intake = frappe.db.get_value("Program", doc.program, "intake_type")
        if intake:
            doc.intake_type = intake

def notify_stage_entry(applicant_doc, stage):
    """
    Called when applicant enters a new stage.
    Creates portal notification. Sends email if template configured.
    Only fires if notify_applicant_on_entry = 1 on the stage.
    """
    if not getattr(stage, "notify_applicant_on_entry", 0):
        return

    try:
        frappe.get_doc({
            "doctype":           "Applicant Notification",
            "applicant":         applicant_doc.name,
            "title":             f"Stage Update: {stage.stage_name}",
            "message":           f"Your application has moved to the {stage.stage_name} stage.",
            "notification_type": "Stage Update",
            "link":              "/my-applications",
            "is_read":           0
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"notify_stage_entry failed: {e}", "Stage Notification")

@frappe.whitelist()
def get_bulk_applications_zip(campus=None, program=None, admission_cycle=None, academic_year=None, admission_year=None, application_status=None, print_format=None):
    """
    Whitelisted entry point for bulk applicant form download.
    Filters applicants, generates PDFs using selected print format, and returns a ZIP.
    Handles small batches synchronously and large batches via background queue.
    """
    filters = {}
    if campus: filters["campus"] = campus
    if program: filters["program"] = program
    if admission_cycle: filters["admission_cycle"] = admission_cycle
    if academic_year: filters["academic_year"] = academic_year
    if admission_year: filters["admission_year"] = admission_year
    if application_status: filters["application_status"] = application_status

    applicants = frappe.get_all("Applicant", filters=filters, pluck="name")

    if not applicants:
        frappe.throw(_("No applicants found matching the selected filters."))

    if not print_format:
        print_format = "Applicant Application Form"

    # LARGE BATCH HANDLING (> 10)
    if len(applicants) > 10:
        frappe.enqueue(
            "slcm.admission.doctype.applicant.applicant.background_bulk_worker",
            applicants=applicants,
            print_format=print_format,
            user=frappe.session.user,
            queue='long',
            timeout=3600
        )
        return {
            "queued": True,
            "message": _("Large batch detected ({0} applicants). Processing started in the background. You will receive a notification when finished.").format(len(applicants))
        }

    # SMALL BATCH SYNC
    return background_bulk_worker(applicants, print_format, sync=True)


@frappe.whitelist()
def bulk_convert_applicants_to_student(applicants=None):
    """
    Resolve Applicant Fee Assignment (Admission Fee, Paid / Partially Paid) per applicant,
    then delegate to the same bulk convert pipeline as Applicant Fee Assignment.

    Only applicants with application_status == Fee Paid are eligible (others are skipped with a reason).
    """
    from slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment import (
        bulk_convert_to_student as bulk_convert_assignments,
    )

    if isinstance(applicants, str):
        applicants = json.loads(applicants)
    if not applicants:
        return {"message": _("No applicants selected.")}

    eligible_assignments = []
    skipped = []
    seen = set()

    for an in applicants:
        if not an:
            continue
        if not frappe.db.exists("Applicant", an):
            skipped.append({"applicant": an, "reason": _("Applicant not found.")})
            continue
        st = frappe.db.get_value("Applicant", an, "application_status")
        if st != "Fee Paid":
            skipped.append(
                {
                    "applicant": an,
                    "reason": _("Only applicants with status Fee Paid can be converted (current: {0}).").format(
                        st or _("—")
                    ),
                }
            )
            continue
        rows = frappe.get_all(
            "Applicant Fee Assignment",
            filters={"applicant": an, "fee_type": "Admission Fee", "docstatus": 1},
            fields=["name", "status"],
            order_by="modified desc",
        )
        afa_name = None
        for r in rows:
            if r.status in ("Paid", "Partially Paid"):
                afa_name = r.name
                break
        if not afa_name:
            skipped.append(
                {
                    "applicant": an,
                    "reason": _(
                        "No submitted Admission Fee assignment in Paid or Partially Paid status was found."
                    ),
                }
            )
            continue
        if afa_name not in seen:
            seen.add(afa_name)
            eligible_assignments.append(afa_name)

    if not eligible_assignments:
        return {
            "message": _(
                "No eligible applicants. Select applicants with status Fee Paid and a paid or partially paid Admission Fee assignment."
            ),
            "skipped": skipped,
        }

    result = bulk_convert_assignments(eligible_assignments)
    if not isinstance(result, dict):
        return result
    result.setdefault("skipped", [])
    result["skipped"] = skipped + list(result["skipped"])
    return result


def background_bulk_worker(applicants, print_format, user=None, sync=False):
    """
    Worker function to generate PDFs and package into ZIP.
    """
    import zipfile
    from io import BytesIO
    from frappe.utils.file_manager import save_file

    total = len(applicants)
    success_count = 0
    errors = []
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for i, name in enumerate(applicants):
            try:
                # Update progress for background jobs
                if not sync:
                    frappe.publish_realtime("bulk_download_progress", {
                        "progress": i + 1,
                        "total": total,
                        "message": _("Generating PDF for {0}").format(name)
                    }, user=user)

                pdf_content = frappe.get_print(
                    doctype="Applicant",
                    name=name,
                    print_format=print_format,
                    as_pdf=True
                )
                
                # Fetch applicant ID for filename
                applicant_id = frappe.db.get_value("Applicant", name, "applicant_id") or name
                zip_file.writestr(f"{applicant_id}.pdf", pdf_content)
                success_count += 1
                
            except Exception as e:
                errors.append({"applicant": name, "error": str(e)})

    if success_count == 0:
        error_msg = _("Failed to generate any PDFs. Errors: {0}").format(len(errors))
        if sync: frappe.throw(error_msg)
        return

    # Save ZIP File
    zip_buffer.seek(0)
    file_name = f"Applicant_Forms_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
    saved_file = save_file(file_name, zip_buffer.getvalue(), "Applicant", "Bulk Download", is_private=1)

    if sync:
        return {"file_url": saved_file.file_url, "success": success_count, "errors": errors}

    # Background cleanup and notification
    notification_content = f"""
        <div style="font-family: sans-serif; padding: 5px;">
            <h4 style="color: #1a202c; margin-bottom: 12px;">{_('Bulk Form Generation Report')}</h4>
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <span style="background: #f0fff4; color: #2f855a; padding: 4px 10px; border-radius: 4px; border: 1px solid #c6f6d5; font-weight: bold; font-size: 12px;">
                    {success_count} {_('Generated')}
                </span>
                <span style="background: { '#fff5f5' if errors else '#f7fafc' }; color: { '#c53030' if errors else '#718096' }; padding: 4px 10px; border-radius: 4px; border: 1px solid { '#fed7d7' if errors else '#edf2f7' }; font-weight: bold; font-size: 12px;">
                    {len(errors)} {_('Failed')}
                </span>
            </div>
            <p style="font-size: 13px; color: #4a5568;">{_('Your ZIP archive is ready for download.')}</p>
            <div style="margin-top: 15px; border-top: 1px solid #edf2f7; padding-top: 12px;">
                <a href="{saved_file.file_url}" target="_blank" style="background: #1a202c; color: #ffffff !important; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 13px; display: inline-block;">
                    {_('Download ZIP')}
                </a>
            </div>
        </div>
    """

    from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
    enqueue_create_notification([user], {
        "subject": _("Bulk Applicant Forms Ready"),
        "email_content": notification_content,
        "type": "Alert",
        "document_type": "Applicant"
    })

    frappe.publish_realtime("bulk_download_complete", {
        "file_url": saved_file.file_url,
        "doctype": "Applicant"
    }, user=user)

    frappe.publish_realtime("msgprint", {
        "message": _("Successfully generated {0} application forms.").format(success_count),
        "title": _("Download Ready"),
        "indicator": "green" if not errors else "orange",
        "primary_action": {"label": _("Download ZIP"), "action": f"window.open('{saved_file.file_url}')"}
    }, user=user)