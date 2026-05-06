import os
import base64
import mimetypes

import frappe
from frappe import _
from frappe.utils import random_string
from frappe.core.doctype.user.user import sign_up


def _photo_as_data_uri(photo_url):
    """Read a Frappe file (public or private) from disk and return a base64 data URI.
    This avoids wkhtmltopdf having to make HTTP requests (which often fail on localhost).
    """
    if not photo_url:
        return None
    try:
        if photo_url.startswith("/private/files/"):
            rel = photo_url[len("/private/files/"):]
            file_path = os.path.abspath(frappe.get_site_path("private", "files", rel))
        elif photo_url.startswith("/files/"):
            rel = photo_url[len("/files/"):]
            file_path = os.path.abspath(frappe.get_site_path("public", "files", rel))
        else:
            return None
        if not os.path.exists(file_path):
            return None
        with open(file_path, "rb") as f:
            data = f.read()
        mime_type = mimetypes.guess_type(file_path)[0] or "image/jpeg"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"
    except Exception:
        return None

@frappe.whitelist(allow_guest=True)
def register_fle_user(email, mobile_number=None):
    if not email:
        frappe.throw(_("Email is mandatory"))

    if frappe.db.exists("User", email):
        frappe.throw(_("User with this email already exists."))
        
    user_dict = {
        "doctype": "User",
        "email": email,
        "first_name": email.split('@')[0],
        "enabled": 1,
        "new_password": random_string(10),
        "user_type": "Website User",
        "send_welcome_email": 0,
        "redirect_url": "/fle/login.html",
    }
    if mobile_number:
        user_dict["mobile_no"] = mobile_number

    user = frappe.get_doc(user_dict)
    
    user.flags.ignore_permissions = True
    user.flags.ignore_password_policy = True
    user.insert()

    # Generate the password reset link silently (without emailing)
    frappe_link = user.reset_password(send_email=False)

    # Disable expiration for "Complete Registration" link by setting generation date 10 years in the future
    from frappe.utils import add_days, now_datetime
    user.db_set("last_reset_password_key_generated_on", add_days(now_datetime(), 3650))
    
    # Extract the path + query (e.g., /update-password?key=XYZ)
    import urllib.parse
    parsed = urllib.parse.urlparse(frappe_link)
    
    # Rebuild the link using frappe.utils.get_url which picks up the request host/port correctly,
    # but point it to our custom page.
    from frappe.utils import get_url
    correct_link = get_url(f"/fle/update_password.html?{parsed.query}")
    
    # Prepare and send the welcome email
    site_name = frappe.db.get_default("site_name") or frappe.get_conf().get("site_name")
    subject = _("Welcome to {0}").format(site_name) if site_name else _("Complete Registration")
    welcome_email_template = frappe.db.get_system_setting("welcome_email_template")

    user.send_login_mail(
        subject,
        "fle_new_user",
        dict(link=correct_link, site_url=get_url()),
        custom_template=welcome_email_template,
    )

    default_role = frappe.get_single_value("Portal Settings", "default_role")
    if default_role:
        user.add_roles(default_role)

    # Reliable fallback cache assignment
    frappe.cache().hset("redirect_after_login", user.name, "/fle/login.html")
    
    return {"status": "success", "message": "Check your email to set your password and activate your account!"}

@frappe.whitelist(allow_guest=True)
def custom_sign_up(email, full_name, mobile_no=None, redirect_to=None):
    if not email or not full_name:
        frappe.throw(_("Email and Full Name are required"))

    if frappe.db.exists("User", email):
        return 0, _("User with this email already exists.")
    
    if mobile_no and frappe.db.exists("User", {"mobile_no": mobile_no}):
        return 0, _("Mobile number already registered.")

    user_dict = {
        "doctype": "User",
        "email": email,
        "first_name": full_name,
        "enabled": 1,
        "send_welcome_email": 1,
        "user_type": "Website User"
    }
    if mobile_no:
        user_dict["mobile_no"] = mobile_no

    user = frappe.get_doc(user_dict)
    user.flags.ignore_permissions = True
    user.flags.ignore_password_policy = True
    user.insert()

    # Add default role
    default_role = frappe.get_single_value("Portal Settings", "default_role") or "Applicant"
    user.add_roles(default_role)

    return 1, _("Account created! Check your email to set your password.")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password_fle(new_password, key, confirm_password=None):
    # Call the core update_password function
    from frappe.core.doctype.user.user import update_password

    # This will log the user in and return a redirect URL (usually /me or /desk)
    core_redirect = update_password(new_password=new_password, key=key)

    # We want to force redirect to the FLE form
    user = frappe.session.user
    if user == "Guest":
        # If somehow not logged in, just go to login
        return "/fle/login.html"

    user_doc = frappe.get_doc("User", user)
    email = user_doc.email or ""
    mobile = user_doc.mobile_no or ""

    # Store prefill data server-side so the URL stays clean (email only)
    frappe.cache().hset("fle_prefill", user, {"email": email})

    # If the user has a paid FLE application, send them to the enrolled dashboard
    paid_doc = frappe.db.get_value(
        "Foundations for a Legal Education",
        {"email_address": email, "payment_status": ["in", ["Authorized", "Paid", "Captured"]]},
        "name",
    )
    if paid_doc:
        return "/fle/enrolled"

    # If the user has an unpaid/incomplete document, redirect to continue it
    existing_doc = frappe.db.get_value(
        "Foundations for a Legal Education",
        {"email_address": email, "payment_status": ["not in", ["Authorized", "Paid", "Captured"]]},
        "name",
    )
    if existing_doc:
        return f"/foundations-for-a-legal-education/{existing_doc}"
    return "/foundations-for-a-legal-education/new"

@frappe.whitelist(allow_guest=True, methods=["POST"])
def reset_password_fle(user: str):
    """FLE forgot-password: same response shape as reset_password for consistent UI handling."""
    try:
        user_doc = frappe.get_doc("User", user)
        if user_doc.name == "Administrator":
            return {
                "status": "not_allowed",
                "message": _("Password reset is not allowed for this account."),
            }
        if not user_doc.enabled:
            return {"status": "disabled", "message": _("This account has been disabled.")}

        user_doc.validate_reset_password()
        
        # Generate just the key without sending email yet
        frappe_link = user_doc.reset_password(send_email=False)
        
        import urllib.parse
        parsed = urllib.parse.urlparse(frappe_link)
        
        from frappe.utils import get_url
        # Build the custom link with the correct hostname/path
        # We use frappe.request.host_url if available to ensure we use the actual domain
        # the user accessed, rather than the internal site name
        base_url = frappe.request.host_url if hasattr(frappe, "request") and frappe.request else get_url()
        correct_link = f"{base_url}/fle/update_password.html?{parsed.query}"
        
        try:
            logo_path = os.path.abspath(frappe.get_site_path("public", "files", "nlsiu-logo.jpg"))
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("utf-8")
            logo_src = f"data:image/jpeg;base64,{logo_b64}"
        except Exception:
            logo_src = ""

        user_doc.send_login_mail(
            _("Password Reset"),
            "fle_password_reset",
            {"link": correct_link, "site_url": base_url, "logo_src": logo_src},
            now=True,
        )

        return {
            "status": "ok",
            "message": _(
                "We have sent a password reset link to {0}. Check your inbox and spam folder."
            ).format(user_doc.email or user_doc.full_name or _("user")),
        }
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        frappe.clear_messages()
        return {
            "status": "not_found",
            "message": _("No account found for this email address."),
        }

@frappe.whitelist(allow_guest=True)
def login_fle_user(usr, pwd):
    from frappe.auth import LoginManager

    # Check if the user exists before attempting authentication
    if not frappe.db.exists("User", usr):
        frappe.clear_messages()
        frappe.local.response["message"] = (
            "No account found for this email. "
            "Please register to create an account."
        )
        return

    try:
        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["message"] = "Incorrect password"
        return

    frappe.local.response["message"] = "Logged In"

    # Get the user to fetch email and mobile
    user_doc = frappe.get_doc("User", usr)
    email = user_doc.email or ""
    mobile = user_doc.mobile_no or ""

    # Store prefill data server-side so the URL stays clean (email only)
    frappe.cache().hset("fle_prefill", frappe.session.user, {"email": email})

    # If the user has a paid FLE application, send them to the enrolled dashboard
    paid_doc = frappe.db.get_value(
        "Foundations for a Legal Education",
        {"email_address": email, "payment_status": ["in", ["Authorized", "Paid", "Captured"]]},
        "name",
    )
    if paid_doc:
        frappe.local.response["home_page"] = "/fle/enrolled"
        return

    # If the user has an unpaid/incomplete document, redirect them to continue it
    existing_doc = frappe.db.get_value(
        "Foundations for a Legal Education",
        {"email_address": email, "payment_status": ["not in", ["Authorized", "Paid", "Captured"]]},
        "name",
    )
    if existing_doc:
        frappe.local.response["home_page"] = f"/foundations-for-a-legal-education/{existing_doc}"
    else:
        frappe.local.response["home_page"] = "/foundations-for-a-legal-education/new"

@frappe.whitelist()
def get_fle_prefill_data():
    """Return cached prefill data for the current user and clear it (one-time use)."""
    user = frappe.session.user
    if user == "Guest":
        return {}
    data = frappe.cache().hget("fle_prefill", user) or {}
    if data:
        frappe.cache().hdel("fle_prefill", user)
    return data


@frappe.whitelist()
def download_fle_receipt(docname):
    if not docname:
        frappe.throw(_("Document name required"))

    if not frappe.db.exists("Foundations for a Legal Education", docname):
        frappe.throw(_("Document not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("Foundations for a Legal Education", docname)

    # Only allow owner or System Manager
    if frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

    from frappe.utils.pdf import get_pdf
    from frappe.utils import flt, fmt_money

    def esc(v):
        return frappe.utils.escape_html(str(v or ""))

    logo_url = frappe.utils.get_url("/files/nlsiu-logo.jpg")
    photo_src = _photo_as_data_uri(doc.candidate_photo)
    if photo_src:
        photo_td = f'<td style="width: 100px; text-align: right; vertical-align: middle;"><img src="{photo_src}" style="width: 90px; height: 110px; border: 1px solid #E5E7EB;" /></td>'
    else:
        photo_td = '<td style="width: 100px;"></td>'

    amount_formatted = fmt_money(flt(doc.paid_amount), currency="INR") if doc.paid_amount else str(doc.paid_amount or "")

    html = f"""
        <html>
        <head>
            <meta charset="utf-8" />
            <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" rel="stylesheet" />
            <style>
                body {{ font-family: "Merriweather", serif; font-size: 11px; color: #111827; }}
                .h1 {{ font-size: 12px; font-weight: 700; margin: 12px 0 12px 0; }}
                .sub {{ color: #4b5563; margin: 0 0 12px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 10px 12px; border: 1px solid #E5E7EB; vertical-align: top; }}
                td.k {{ width: 35%; background: #F9FAFB; font-weight: 600; }}
                table.header-table {{ border: none; margin-bottom: 20px; border-bottom: 2px solid #a81119; padding-bottom: 10px; }}
                table.header-table td {{ border: none; padding: 0; vertical-align: middle; }}
                .header-title-container {{ text-align: center; color: #a81119; font-family: "Merriweather", serif; }}
                .university-name {{ font-size: 22px; font-weight: bold; margin: 0 0 6px 0; }}
                .red-ribbon {{ background-color: #8B0000; height: 6px; margin: 4px 0; width: 100%; }}
                .department-name {{ font-size: 14px; font-weight: bold; margin: 6px 0 0 0; }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td style="width: 80px;"><img src="{esc(logo_url)}" style="width: 60px; height: auto;" /></td>
                    <td class="header-title-container">
                        <div class="university-name">NATIONAL LAW SCHOOL OF INDIA UNIVERSITY, BENGALURU</div>
                        <div class="red-ribbon"></div>
                        <div class="department-name">Foundations for a Legal Education Certificate Course (FLE)</div>
                    </td>
                    {photo_td}
                </tr>
            </table>
            <div class="h1">Payment receipt</div>
            <p class="sub">Reference: {esc(docname)}</p>
            <table>
                <tr><td class="k">Name</td><td>{esc(doc.candidate_name)}</td></tr>
                <tr><td class="k">Email</td><td>{esc(doc.email_address)}</td></tr>
                <tr><td class="k">Payment status</td><td>{esc(doc.payment_status)}</td></tr>
                <tr><td class="k">Amount</td><td>{esc(amount_formatted)}</td></tr>
                <tr><td class="k">Transaction ID</td><td>{esc(doc.payment_id)}</td></tr>
                <tr><td class="k">Reference</td><td>{esc(docname)}</td></tr>
                <tr><td class="k">Date</td><td>{esc(doc.modified)}</td></tr>
            </table>
             <p style="text-align: center; font-size: 11px; color: #374151; margin-top: 18px; letter-spacing: 2px;">
                *********
            </p>
        </body>
        </html>
    """

    pdf_content = get_pdf(html)
    frappe.local.response.filename = f"Receipt-{docname}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"


@frappe.whitelist()
def get_fle_receipt_pdf_base64(docname):
    """Returns the payment receipt PDF as base64 for inline viewing."""
    if not docname:
        frappe.throw(_("Document name required"))

    if not frappe.db.exists("Foundations for a Legal Education", docname):
        frappe.throw(_("Document not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("Foundations for a Legal Education", docname)

    if frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

    from frappe.utils.pdf import get_pdf
    from frappe.utils import flt, fmt_money


    def esc(v):
        return frappe.utils.escape_html(str(v or ""))

    logo_url = frappe.utils.get_url("/files/nlsiu-logo.jpg")
    photo_src = _photo_as_data_uri(doc.candidate_photo)
    if photo_src:
        photo_td = f'<td style="width: 100px; text-align: right; vertical-align: middle;"><img src="{photo_src}" style="width: 90px; height: 110px; border: 1px solid #E5E7EB;" /></td>'
    else:
        photo_td = '<td style="width: 100px;"></td>'

    amount_formatted = fmt_money(flt(doc.paid_amount), currency="INR") if doc.paid_amount else str(doc.paid_amount or "")

    html = f"""
        <html>
        <head>
            <meta charset="utf-8" />
            <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" rel="stylesheet" />
            <style>
                body {{ font-family: "Merriweather", serif; font-size: 11px; color: #111827; }}
                .h1 {{ font-size: 12px; font-weight: 700; margin: 12px 0 12px 0; }}
                .sub {{ color: #4b5563; margin: 0 0 12px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 10px 12px; border: 1px solid #E5E7EB; vertical-align: top; }}
                td.k {{ width: 35%; background: #F9FAFB; font-weight: 600; }}
                table.header-table {{ border: none; margin-bottom: 20px; border-bottom: 2px solid #a81119; padding-bottom: 10px; }}
                table.header-table td {{ border: none; padding: 0; vertical-align: middle; }}
                .header-title-container {{ text-align: center; color: #a81119; font-family: "Merriweather", serif; }}
                .university-name {{ font-size: 22px; font-weight: bold; margin: 0 0 6px 0; }}
                .red-ribbon {{ background-color: #8B0000; height: 6px; margin: 4px 0; width: 100%; }}
                .department-name {{ font-size: 14px; font-weight: bold; margin: 6px 0 0 0; }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td style="width: 80px;"><img src="{esc(logo_url)}" style="width: 60px; height: auto;" /></td>
                    <td class="header-title-container">
                        <div class="university-name">NATIONAL LAW SCHOOL OF INDIA UNIVERSITY, BENGALURU</div>
                        <div class="red-ribbon"></div>
                        <div class="department-name">Foundations for a Legal Education Certificate Course (FLE)</div>
                    </td>
                    {photo_td}
                </tr>
            </table>
            <div class="h1">Payment receipt</div>
            <p class="sub">Reference: {esc(docname)}</p>
            <table>
                <tr><td class="k">Name</td><td>{esc(doc.candidate_name)}</td></tr>
                <tr><td class="k">Email</td><td>{esc(doc.email_address)}</td></tr>
                <tr><td class="k">Payment status</td><td>{esc(doc.payment_status)}</td></tr>
                <tr><td class="k">Amount</td><td>{esc(amount_formatted)}</td></tr>
                <tr><td class="k">Transaction ID</td><td>{esc(doc.payment_id)}</td></tr>
                <tr><td class="k">Reference</td><td>{esc(docname)}</td></tr>
                <tr><td class="k">Date</td><td>{esc(doc.modified)}</td></tr>
            </table>
            <p style="text-align: center; font-size: 11px; color: #374151; margin-top: 18px; letter-spacing: 2px;">
                *********
            </p>
        </body>
        </html>
    """

    pdf_content = get_pdf(html)
    return {
        "pdf": base64.b64encode(pdf_content).decode("utf-8"),
        "filename": f"Receipt-{docname}.pdf"
    }


@frappe.whitelist()
def download_fle_application_pdf(docname):
    if not docname:
        frappe.throw(_("Document name required"))

    if not frappe.db.exists("Foundations for a Legal Education", docname):
        frappe.throw(_("Document not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("Foundations for a Legal Education", docname)

    # Only allow owner or System Manager
    if frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

    from frappe.utils.pdf import get_pdf

    def esc(v):
        return frappe.utils.escape_html(str(v or ""))

    def row(label, value):
        return f'<tr><td class="k">{esc(label)}</td><td>{esc(value)}</td></tr>'

    def sec(title):
        return f'<tr><td colspan="2" class="sec-head">{esc(title)}</td></tr>'

    logo_url = frappe.utils.get_url("/files/nlsiu-logo.jpg")
    photo_src = _photo_as_data_uri(doc.candidate_photo)
    if photo_src:
        photo_td = f'<td style="width: 110px; text-align: right; vertical-align: middle;"><img src="{photo_src}" style="width: 100px; height: 125px; border: 1px solid #E5E7EB;" /></td>'
    else:
        photo_td = '<td style="width: 110px;"></td>'

    year_of_passing = doc.year_of_passing or ""
    if year_of_passing == "Prior to 2016" and doc.please_specify_the_year_of_passing:
        year_of_passing = f"Prior to 2016 ({doc.please_specify_the_year_of_passing})"

    occupation = doc.candidate_current_occupation or ""
    if occupation == "Other" and doc.if_other4:
        occupation = f"Other ({doc.if_other4})"

    state = doc.candidates_state or ""
    if state == "Other" and doc.if_other3:
        state = f"Other ({doc.if_other3})"

    board = doc.latest_board_attended or ""
    if board == "Other" and doc.if_others2:
        board = f"Other ({doc.if_others2})"

    exam = doc.last_class_attended or ""
    if exam == "Other" and doc.if_others1:
        exam = f"Other ({doc.if_others1})"

    where_heard = doc.where_did_you_hear or ""
    if where_heard == "Other" and doc.if_others_mention_here:
        where_heard = f"Other ({doc.if_others_mention_here})"

    html = f"""
        <html>
        <head>
            <meta charset="utf-8" />
            <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" rel="stylesheet" />
            <style>
                body {{ font-family: "Merriweather", serif; font-size: 11px; color: #111827; }}
                table.header-table {{ border: none; margin-bottom: 16px; border-bottom: 2px solid #a81119; padding-bottom: 8px; width: 100%; border-collapse: collapse; }}
                table.header-table td {{ border: none; padding: 0; vertical-align: middle; }}
                .header-title-container {{ text-align: center; color: #a81119; }}
                .university-name {{ font-size: 22px; font-weight: bold; margin: 0; }}
                .department-name {{ font-size: 14px; font-weight: bold; margin: 4px 0 0 0; }}
                .app-ref {{ font-size: 12px; margin: 4px 0 0 0; color: #374151; }}
                table.main {{ width: 100%; border-collapse: collapse; margin-bottom: 0; }}
                table.main td {{ padding: 7px 10px; border: 1px solid #E5E7EB; vertical-align: top; }}
                table.main td.k {{ width: 38%; background: #F9FAFB; font-weight: 600; }}
                table.main td.sec-head {{ background: #a81119; color: #fff; font-weight: 700; font-size: 14px; padding: 5px 10px; }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td style="width: 75px;"><img src="{esc(logo_url)}" style="width: 55px; height: auto;" /></td>
                    <td class="header-title-container">
                        <div class="university-name">NATIONAL LAW SCHOOL OF INDIA UNIVERSITY, BENGALURU</div>
                        <div class="red-ribbon"></div>
                        <div class="department-name">Foundations for a Legal Education Certificate Course (FLE)</div>
                    </td>
                    {photo_td}
                </tr>
            </table>
            <table class="main">
                {sec("Candidate details")}
                {row("Application number", doc.name)}
                {row("Submission date", doc.timestamp)}
                {row("Name on certificate", doc.candidate_name)}
                {row("Email address", doc.email_address)}
                {row("Current occupation", occupation)}
                {row("Gender", doc.candidate_gender)}
                {row("Date of birth", doc.candidate_dob)}
                {row("Nationality", doc.candidate_nationality)}
                {row("Country of residence", doc.country_of_residence)}
                {row("State", state)}
                {row("City", doc.city)}
                {row("Address", doc.address_line_1)}
                {row("Pincode", doc.pincode)}
                {row("Contact number", doc.candidate_contact_number)}
                {row("Where did you hear about FLE?", where_heard)}

                {sec("Educational background")}
                {row("Last examination attended", exam)}
                {row("Latest board", board)}
                {row("Year of passing", year_of_passing)}
                {row("Last institution attended", doc.last_institution_attended)}

                {sec("Parent / guardian details")}
                {row("Relationship with candidate", doc.relationship_with_candidate)}
                {row("Parent's name", doc.parent_name)}
                {row("Parent's contact number", doc.parent_contact_number)}
                {row("Parent's email address", doc.parent_email_address)}
                {row("Parent's occupation", doc.parent_occupation)}

                {sec("Payment details")}
                {row("Payment status", doc.payment_status)}
                {row("Amount paid", doc.paid_amount)}
                {row("Payment ID", doc.payment_id)}

                {sec("Application status")}
                {row("Enrollment status", doc.enrollment_status)}
                {row("Declaration consent", "Yes" if doc.declaration_consent else "No")}
            </table>
            <p style="text-align: center; font-size: 11px; color: #374151; margin-top: 18px; letter-spacing: 2px;">
                *********
            </p>
        </body>
        </html>
    """

    pdf_content = get_pdf(html)
    frappe.local.response.filename = f"FLE-Application-{docname}.pdf"
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"


@frappe.whitelist()
def get_fle_application_pdf_base64(docname):
    """Returns the application PDF as a base64 string for inline viewing."""
    if not docname:
        frappe.throw(_("Document name required"))

    if not frappe.db.exists("Foundations for a Legal Education", docname):
        frappe.throw(_("Document not found"), frappe.DoesNotExistError)

    doc = frappe.get_doc("Foundations for a Legal Education", docname)

    if frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            frappe.throw(_("Not permitted"), frappe.PermissionError)

    from frappe.utils.pdf import get_pdf


    def esc(v):
        return frappe.utils.escape_html(str(v or ""))

    def row(label, value):
        return f'<tr><td class="k">{esc(label)}</td><td>{esc(value)}</td></tr>'

    def sec(title):
        return f'<tr><td colspan="2" class="sec-head">{esc(title)}</td></tr>'

    logo_url = frappe.utils.get_url("/files/nlsiu-logo.jpg")
    photo_src = _photo_as_data_uri(doc.candidate_photo)
    if photo_src:
        photo_td = f'<td style="width: 110px; text-align: right; vertical-align: middle;"><img src="{photo_src}" style="width: 100px; height: 125px; border: 1px solid #E5E7EB;" /></td>'
    else:
        photo_td = '<td style="width: 110px;"></td>'

    year_of_passing = doc.year_of_passing or ""
    if year_of_passing == "Prior to 2016" and doc.please_specify_the_year_of_passing:
        year_of_passing = f"Prior to 2016 ({doc.please_specify_the_year_of_passing})"

    occupation = doc.candidate_current_occupation or ""
    if occupation == "Other" and doc.if_other4:
        occupation = f"Other ({doc.if_other4})"

    state = doc.candidates_state or ""
    if state == "Other" and doc.if_other3:
        state = f"Other ({doc.if_other3})"

    board = doc.latest_board_attended or ""
    if board == "Other" and doc.if_others2:
        board = f"Other ({doc.if_others2})"

    exam = doc.last_class_attended or ""
    if exam == "Other" and doc.if_others1:
        exam = f"Other ({doc.if_others1})"

    where_heard = doc.where_did_you_hear or ""
    if where_heard == "Other" and doc.if_others_mention_here:
        where_heard = f"Other ({doc.if_others_mention_here})"

    html = f"""
        <html>
        <head>
            <meta charset="utf-8" />
            <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap" rel="stylesheet" />
            <style>
                body {{ font-family: "Merriweather", serif; font-size: 11px; color: #111827; }}
                table.header-table {{ border: none; margin-bottom: 16px; border-bottom: 2px solid #a81119; padding-bottom: 8px; width: 100%; border-collapse: collapse; }}
                table.header-table td {{ border: none; padding: 0; vertical-align: middle; }}
                .header-title-container {{ text-align: center; color: #a81119; }}
                .university-name {{ font-size: 22px; font-weight: bold; margin: 0; }}
                .department-name {{ font-size: 14px; font-weight: bold; margin: 4px 0 0 0; }}
                .app-ref {{ font-size: 12px; margin: 4px 0 0 0; color: #374151; }}
                table.main {{ width: 100%; border-collapse: collapse; margin-bottom: 0; }}
                table.main td {{ padding: 7px 10px; border: 1px solid #E5E7EB; vertical-align: top; }}
                table.main td.k {{ width: 38%; background: #F9FAFB; font-weight: 600; }}
                table.main td.sec-head {{ background: #a81119; color: #fff; font-weight: 700; font-size: 14px; padding: 5px 10px; }}
            </style>
        </head>
        <body>
            <table class="header-table">
                <tr>
                    <td style="width: 75px;"><img src="{esc(logo_url)}" style="width: 55px; height: auto;" /></td>
                    <td class="header-title-container">
                        <div class="university-name">NATIONAL LAW SCHOOL OF INDIA UNIVERSITY, BENGALURU</div>
                        <div class="red-ribbon"></div>
                        <div class="department-name">Foundations for a Legal Education Certificate Course (FLE)</div>
                    </td>
                    {photo_td}
                </tr>
            </table>
            <table class="main">

                {sec("Candidate details")}
                {row("Application number", doc.name)}
                {row("Submission date", doc.timestamp)}
                {row("Name on certificate", doc.candidate_name)}
                {row("Email address", doc.email_address)}
                {row("Current occupation", occupation)}
                {row("Gender", doc.candidate_gender)}
                {row("Date of birth", doc.candidate_dob)}
                {row("Nationality", doc.candidate_nationality)}
                {row("Country of residence", doc.country_of_residence)}
                {row("State", state)}
                {row("City", doc.city)}
                {row("Address", doc.address_line_1)}
                {row("Pincode", doc.pincode)}
                {row("Contact number", doc.candidate_contact_number)}
                {row("Where did you hear about FLE?", where_heard)}

                {sec("Educational background")}
                {row("Last examination attended", exam)}
                {row("Latest board", board)}
                {row("Year of passing", year_of_passing)}
                {row("Last institution attended", doc.last_institution_attended)}

                {sec("Parent / guardian details")}
                {row("Relationship with candidate", doc.relationship_with_candidate)}
                {row("Parent's name", doc.parent_name)}
                {row("Parent's contact number", doc.parent_contact_number)}
                {row("Parent's email address", doc.parent_email_address)}
                {row("Parent's occupation", doc.parent_occupation)}

                {sec("Payment details")}
                {row("Payment status", doc.payment_status)}
                {row("Amount paid", doc.paid_amount)}
                {row("Payment ID", doc.payment_id)}

                {sec("Application status")}
                {row("Enrollment status", doc.enrollment_status)}
                {row("Declaration consent", "Yes" if doc.declaration_consent else "No")}
            </table>
            <p style="text-align: center; font-size: 11px; color: #374151; margin-top: 18px; letter-spacing: 2px;">
                *********
            </p>
        </body>
        </html>
    """

    pdf_content = get_pdf(html)
    return {
        "pdf": base64.b64encode(pdf_content).decode("utf-8"),
        "filename": f"FLE-Application-{docname}.pdf"
    }


@frappe.whitelist(allow_guest=True)
def get_payment_status(docname):
    if not docname:
        return {}
        
    if not frappe.db.exists("Foundations for a Legal Education", docname):
        return {}
        
    doc = frappe.get_doc("Foundations for a Legal Education", docname)
    
    # Allow if session user is the owner, or if they have System Manager role
    if frappe.session.user != "Guest" and frappe.session.user != doc.owner:
        if "System Manager" not in frappe.get_roles(frappe.session.user):
            return {}
            
    return {
        "payment_status": doc.payment_status,
        "docstatus": doc.docstatus
    }
from frappe.core.doctype.user.user import sign_up
@frappe.whitelist(allow_guest=True)
def custom_sign_up(email, full_name, mobile_no=None, redirect_to=None):
    # Proactively check for existing email or mobile number
    if frappe.db.exists("User", email):
        return [0, "Email address already registered"]
    
    if mobile_no and frappe.db.exists("User", {"mobile_no": mobile_no}):
        return [0, "Mobile number already registered"]
 
    try:
        res = sign_up(email, full_name, redirect_to)
        if res and res[0] == 1 and mobile_no:
            # Update mobile_no for the newly created user
            frappe.db.set_value("User", email, "mobile_no", mobile_no)
            frappe.db.commit()
        return res
    except Exception as e:
        if "Duplicate entry" in str(e):
            if "mobile_no" in str(e):
                return [0, "Mobile number already registered"]
            return [0, "Email address already registered"]
        return [0, str(e)]
 
@frappe.whitelist()
def get_districts(state):
    return frappe.get_all("District", filters={"state": state}, fields=["name"], order_by="name asc")
 
@frappe.whitelist()
def get_user_details():
    user = frappe.session.user
    if user == "Guest":
        return {}
    
    return frappe.db.get_value("User", user,
        ["name", "full_name", "email", "mobile_no", "user_image"], as_dict=True)
 
@frappe.whitelist()
def get_login_redirect():
    user = frappe.session.user
    if user == "Guest":
        return "/login"
    
    user_type = frappe.db.get_value("User", user, "user_type") or "Website User"
    if user_type == "System User":
        return "/desk"
        
    roles = frappe.get_roles(user)
    if "PACE Applicant" in roles and "Applicant" not in roles:
        return "/merit-and-scholarship/admission_dashboard?panel=profile"
    else:
        return "/merit-and-scholarship/admission_dashboard?panel=profile"

from frappe.rate_limiter import rate_limit
from frappe.core.doctype.user.user import get_password_reset_limit

@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_password_reset_limit, seconds=60 * 60)
def reset_password(user: str):
    """
    Send password reset email. Returns a dict {status, message} for portal JSON clients.
    """
    try:
        user_doc = frappe.get_doc("User", user)
        if user_doc.name == "Administrator":
            return {
                "status": "not_allowed",
                "message": _("Password reset is not allowed for this account."),
            }
        if not user_doc.enabled:
            return {"status": "disabled", "message": _("This account has been disabled.")}

        user_doc.validate_reset_password()
        
        # Generate the link without sending the email via Frappe core (which has a header list bug)
        link = user_doc.reset_password(send_email=False)
        
        # Send email manually
        from frappe.utils import get_url
        from frappe.utils.user import get_user_fullname
        
        subject = _("Password Reset")
        created_by = get_user_fullname(frappe.session["user"]) if frappe.session.get("user") else "Administrator"
        if created_by == "Guest":
            created_by = "Administrator"

        args = {
            "first_name": user_doc.first_name or user_doc.last_name or "user",
            "user": user_doc.name,
            "title": subject,
            "login_url": get_url(),
            "created_by": created_by,
            "link": link
        }
        
        reset_password_template = frappe.db.get_system_setting("reset_password_template")
        content = None
        template = "slcm_password_reset"
        
        if reset_password_template:
            from frappe.email.doctype.email_template.email_template import get_email_template
            email_template = get_email_template(reset_password_template, args)
            subject = email_template.get("subject")
            content = email_template.get("message")

        frappe.sendmail(
            recipients=user_doc.email,
            subject=subject,
            template=template if not reset_password_template else None,
            content=content if reset_password_template else None,
            args=args,
            now=True
        )

        return {
            "status": "ok",
            "message": _(
                "A password reset link has been sent to {0}. Check your inbox and spam folder."
            ).format(user_doc.email or user_doc.full_name or _("your email")),
        }
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        frappe.clear_messages()
        return {
            "status": "not_found",
            "message": _("No account found for this email address. Please check the spelling or register."),
        }

@frappe.whitelist(allow_guest=True)
def custom_update_password(new_password, logout_all_sessions=0, key=None, old_password=None):
    from frappe.core.doctype.user.user import update_password as core_update_password
    
    # Call the original Frappe core method to handle all the password reset logic, validations, and logins
    result = core_update_password(new_password, logout_all_sessions, key, old_password)
    
    # Now override the return URL based on our custom routing rules
    user = frappe.session.user
    if user and user != "Guest":
        user_type = frappe.db.get_value("User", user, "user_type")
        roles = frappe.get_roles(user)
        if user_type == "System User":
            return "/desk"
        elif "PACE Applicant" in roles and "Applicant" not in roles:
            return "/merit-and-scholarship/admission_dashboard?panel=profile"
        else:
            return "/merit-and-scholarship/admission_dashboard?panel=profile"
    
    return result

@frappe.whitelist(allow_guest=True)
def register_pace_user(email, mobile_number=None):
    if not email:
        frappe.throw(_("Email is mandatory"))
    if frappe.db.exists("User", email):
        frappe.throw(_("User with this email already exists."))
        
    user_dict = {
        "doctype": "User",
        "email": email,
        "first_name": email.split('@')[0],
        "enabled": 1,
        "new_password": random_string(10),
        "user_type": "Website User",
        "send_welcome_email": 0,
        "redirect_url": "/pace/login",
    }
    if mobile_number:
        user_dict["mobile_no"] = mobile_number

    user = frappe.get_doc(user_dict)
    user.flags.ignore_permissions = True
    user.flags.ignore_password_policy = True
    user.insert()

    # Generate the password reset link silently
    frappe_link = user.reset_password(send_email=False)
    
    from frappe.utils import add_days, now_datetime
    user.db_set("last_reset_password_key_generated_on", add_days(now_datetime(), 3650))
    
    import urllib.parse
    parsed = urllib.parse.urlparse(frappe_link)
    
    from frappe.utils import get_url
    correct_link = get_url(f"/update-password?{parsed.query}")
    
    site_name = frappe.db.get_default("site_name") or frappe.get_conf().get("site_name")
    subject = _("Welcome to {0}").format(site_name) if site_name else _("Complete Registration")
    welcome_email_template = frappe.db.get_system_setting("welcome_email_template")

    user.send_login_mail(
        subject,
        "new_user",
        dict(link=correct_link, site_url=get_url()),
        custom_template=welcome_email_template,
    )

    # Assign "PACE Applicant" role
    user.add_roles("PACE Applicant")

    frappe.cache().hset("redirect_after_login", user.name, "/merit-and-scholarship/admission_dashboard?panel=profile")
    return {"status": "success", "message": "Check your email to set your password and activate your account!"}

@frappe.whitelist(allow_guest=True)
def login_pace_user(usr, pwd):
    from frappe.auth import LoginManager
    if not frappe.db.exists("User", usr):
        frappe.clear_messages()
        frappe.local.response["message"] = "No account found for this email. Please register to create an account."
        return

    try:
        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.clear_messages()
        frappe.local.response["message"] = "Incorrect password"
        return

    frappe.local.response["message"] = "Logged In"
    frappe.local.response["home_page"] = "/merit-and-scholarship/admission_dashboard?panel=profile"

