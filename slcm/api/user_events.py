import frappe

def user_before_insert(doc, method):
    """
    Triggered on User before_insert.
    If custom signup email is enabled, disable Frappe's default welcome mail.
    """
    if doc.user_type != "Website User":
        return

    institution = frappe.get_single("Institution Settings")
    enable_custom = getattr(institution, "enable_signup_email", 0)
    
    frappe.log_error(f"User: {doc.email}, enable_signup_email: {enable_custom}, send_welcome_email: {doc.send_welcome_email}", "Signup Email Hook: before_insert")

    if enable_custom:
        # If the creator intended to send a welcome email, we intercept it
        if doc.send_welcome_email:
            # Disable default welcome mail to prevent double sending
            doc.send_welcome_email = 0
            # Set a flag to signal our after_insert hook to send the custom one
            doc.flags.send_custom_signup_email = 1
            frappe.log_error(f"Suppressed default email for {doc.email}. Set flag: send_custom_signup_email", "Signup Email Hook: before_insert")

def send_signup_email(doc, method):
    """
    Triggered on User after_insert.
    Sends a custom signup email to self-registered applicants if flagged.
    """
    try:
        if not doc.flags.get("send_custom_signup_email"):
            # Check if it was bypassed but should have been triggered
            if doc.user_type == "Website User":
                institution = frappe.get_single("Institution Settings")
                if getattr(institution, "enable_signup_email", 0):
                    frappe.log_error(f"Flag 'send_custom_signup_email' not found for {doc.email}. Method: {method}", "Signup Email Hook: after_insert bypassed")
            return

        frappe.log_error(f"Processing custom signup email for {doc.email}", "Signup Email Hook: after_insert start")

        # Fetch "Institution Settings"
        institution = frappe.get_single("Institution Settings")
        
        # Double check if still enabled (though flag should be enough)
        if not getattr(institution, "enable_signup_email", 0):
            frappe.log_error("Custom email disabled in Institution Settings during processing", "Signup Email Error")
            return

        # Check SMTP configuration (optional warning)
        if not frappe.conf.get("mail_server"):
            frappe.log_error("SMTP not configured in site_config.json", "Signup Email Error")

        full_name = doc.full_name or doc.first_name or doc.email

        # Generate secure password setup link
        set_password_link = doc.reset_password()

        # Context for rendering
        context = {
            "institution_name": getattr(institution, "institution_name", ""),
            "logo": getattr(institution, "logo", ""),
            "full_name": full_name,
            "set_password_link": set_password_link,
            "login_url": getattr(institution, "login_url", "") or frappe.utils.get_url("/login"),
            "support_email": getattr(institution, "support_email", ""),
            "link_expiry_hours": getattr(institution, "link_expiry_hours", 24) or 24
        }

        # Render Subject
        subject_template = getattr(institution, "signup_email_subject", "")
        if not subject_template:
            subject_template = "Welcome to {{ institution_name }}"
        subject = frappe.render_template(subject_template, context)

        # Render Email Body
        message_template = getattr(institution, "signup_email_template", "")
        if not message_template:
            # If no template is configured, we can't send a custom one.
            # In this case, we might want to log it.
            frappe.log_error("No Signup Email Template configured in Institution Settings", "Signup Email Error")
            return
            
        message = frappe.render_template(message_template, context)

        # Send Email
        frappe.sendmail(
            recipients=[doc.email],
            subject=subject,
            message=message,
            now=True
        )
        frappe.log_error(f"Successfully triggered sendmail for {doc.email}", "Signup Email Hook: after_insert success")

    except Exception:
        frappe.log_error(title="SLCM Signup Email Error", message=frappe.get_traceback())
