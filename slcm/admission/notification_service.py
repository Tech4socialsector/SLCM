import frappe
from frappe.utils import now
 
def notify_status_change(applicant, program, old_status, new_status, allocation_name, admission_cycle=None, row=None):
    """
    Sends an email notification to the applicant about a status change
    using the 'Seat Allocation Result Notification' template record and logs it.
    """
    try:
        applicant_doc = frappe.get_doc("Eligibility Result", applicant)
    except frappe.DoesNotExistError:
        frappe.logger().error(f"Notification error: Eligibility Result '{applicant}' not found.")
        return
 
    # Resolve email: Try Eligibility Result first, then fallback to Applicant
    email = getattr(applicant_doc, "email", None) or getattr(applicant_doc, "email_id", None)
    
    if not email and applicant_doc.applicant_id:
        email = frappe.db.get_value("Applicant", applicant_doc.applicant_id, "email")
        if email:
            frappe.logger().info(f"Notification: Using fallback email from Applicant {applicant_doc.applicant_id} for {applicant}")
 
    if not email:
        frappe.logger().warning(f"Notification skipped: No email found for applicant {applicant} (ID: {applicant_doc.applicant_id})")
        return
 
    # Fetch and render the Email Template record
    template_name = "Seat Allocation Result Notification"
    if not frappe.db.exists("Email Template", template_name):
        # Fallback to older name if some reason this one isn't there
        template_name = "Seat Allocation Status"
        if not frappe.db.exists("Email Template", template_name):
            frappe.logger().error(f"Notification error: Email Template '{template_name}' not found.")
            return
 
    template = frappe.get_doc("Email Template", template_name)
    
    # Construct combined context for the template (it expects 'doc')
    doc_context = applicant_doc.as_dict()
    if row:
        doc_context.update(row.as_dict())
    else:
        # Fallback fields if called manually without a row
        doc_context.update({
            "selection_status": new_status,
            "program": program,
            "admission_cycle": admission_cycle,
            "applicant": applicant
        })
 
    # Force Candidate Name resolution if missing or None
    raw_name = doc_context.get("candidate_name") or applicant_doc.candidate_name
    if not raw_name and doc_context.get("applicant_id"):
        raw_name = frappe.db.get_value("Applicant", doc_context["applicant_id"], "candidate_name")
    
    # Absolute string fallback
    safe_name = str(raw_name or "Applicant")
    if safe_name == "None":
        safe_name = "Applicant"
        
    doc_context["candidate_name"] = safe_name
    doc_context["applicant_name"] = safe_name

    # Resolve Merit Total Score for context
    merit_total_score = doc_context.get("total_score")
    if merit_total_score is None:
        # Try fetching from Merit List Applicant for this cycle
        merit_total_score = frappe.db.get_value("Merit List Applicant", {
            "applicant": applicant,
            "parentfield": "merit_applicants"
        }, "total_score")
    
    # Format if number
    if merit_total_score is not None:
        try:
            from frappe.utils import flt
            merit_total_score = flt(merit_total_score, 3)
        except:
            pass
    
    doc_context["merit_total_score"] = merit_total_score
    doc_context["total_score"] = merit_total_score

    from frappe.utils import get_url
    
    args = {
        "doc": doc_context,
        "candidate_name": safe_name,
        "applicant_name": safe_name,
        "program": program,
        "admission_cycle": admission_cycle,
        "status": new_status,
        "old_status": old_status,
        "new_status": new_status,
        "allocation_name": allocation_name,
        "merit_total_score": merit_total_score,
        "total_score": merit_total_score,
        "get_url": get_url,
        "base_url": get_url()
    }
 
    try:
        subject = frappe.render_template(template.subject, args)
        message = frappe.render_template(template.response, args)
    except Exception as e:
        frappe.logger().error(f"Notification error (Jinja rendering) for {applicant}: {e}")
        return
 
    # Enqueue the email sending with pre-rendered content
    try:
        if frappe.flags.in_test:
            frappe.sendmail(
                recipients=[email],
                subject=subject,
                message=message,
                reference_doctype="Seat Allocation",
                reference_name=allocation_name,
                now=False # Create record but don't try to send via SMTP if we are just testing queue creation
            )
        else:
            frappe.enqueue(
                method=frappe.sendmail,
                queue="short",
                recipients=[email],
                subject=subject,
                message=message,
                reference_doctype="Seat Allocation",
                reference_name=allocation_name,
                now=False
            )
        frappe.logger().info(f"Notification queued: Email to {email} for status {new_status}")

        # Log specialized communication
        from slcm.admission.utils.notifications import log_communication
        log_communication(
            applicant=applicant,
            communication_type="Email",
            category="Seat Allocation",
            subject=subject,
            content=message,
            reference_doctype="Seat Allocation",
            reference_name=allocation_name
        )
    except Exception as e:
        frappe.logger().error(f"Notification error (enqueue/sendmail) for {applicant}: {e}")
        return
 
    # Log to Admission Audit Log
    try:
        from slcm.admission.doctype.admission_audit_log.audit_service import log_admission_action
        log_admission_action(
            reference_doctype="Seat Allocation",
            reference_name=allocation_name,
            applicant=applicant,
            program=program,
            action_type="Notification Sent",
            old_value=old_status,
            new_value=new_status,
            remarks=f"Email notification ('{template_name}' template record) sent to {email}."
        )
    except ImportError:
        frappe.logger().warning("Notification: Could not import log_admission_action, skipping audit log.")
    except Exception as e:
        frappe.logger().error(f"Notification error (audit log) for {applicant}: {e}")
 
 
def notify_published_allocation(allocation_name):
    """
    Sends email notifications ONLY to the applicants listed in the 
    Seat Allocation document.
    """
    allocation = frappe.get_doc("Seat Allocation", allocation_name)
    
    if not allocation.selection_applicant:
        frappe.logger().info(f"Notification: No applicants found in {allocation_name}. Skipping.")
        return

    frappe.logger().info(f"Notification: Publishing {allocation_name}. Notifying {len(allocation.selection_applicant)} applicants.")
 
    for row in allocation.selection_applicant:
        notify_status_change(
            applicant=row.applicant_id,
            program=row.program,
            old_status="Draft",
            new_status=row.selection_status,
            allocation_name=allocation_name,
            admission_cycle=allocation.admission_cycle,
            row=row
        )

def notify_scholarship_status(application_name):
    """
    Sends a professionally designed HTML email notification to scholarship applicant.
    """
    app = frappe.get_doc("Scholarship Application", application_name)
    
    email = frappe.db.get_value("Applicant", app.applicant_id, "email")
    if not email:
        return

    from frappe.utils import get_url, fmt_money
    scheme_name = frappe.db.get_value("Scholarship Scheme", app.scholarship_scheme, "scheme_name")
    benefit_amount = fmt_money(app.calculated_benefit) if app.calculated_benefit else "0.00"
    portal_url = "https://apfslcm.boscosofttech.com/merit-and-scholarship/scholarships"
    
    # Common CSS Styles for the Email
    email_styles = """
        <style>
            .email-container { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }
            .header { background-color: #1a3c6e; color: #ffffff; padding: 30px; text-align: center; }
            .header h1 { margin: 0; font-size: 24px; letter-spacing: 1px; }
            .content { padding: 40px; background-color: #ffffff; }
            .status-badge { display: inline-block; padding: 6px 12px; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 12px; margin-bottom: 20px; }
            .status-approved { background-color: #d1fae5; color: #065f46; }
            .status-rejected { background-color: #fee2e2; color: #991b1b; }
            .details-box { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 20px; margin: 25px 0; }
            .label { font-weight: bold; color: #64748b; font-size: 13px; }
            .value { font-weight: bold; color: #1e293b; font-size: 14px; }
            .button { display: inline-block; background-color: #1a3c6e; color: #ffffff !important; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 20px; }
            .footer { background-color: #f1f5f9; color: #64748b; padding: 20px; text-align: center; font-size: 12px; }
        </style>
    """

    if app.status == "Approved":
        subject = f"Congratulations! Your Scholarship for {scheme_name} is Approved"
        body_content = f"""
            <div class="status-badge status-approved">Application Approved</div>
            <p>Dear <strong>{app.applicant_name}</strong>,</p>
            <p>On behalf of the Scholarship Committee, we are pleased to inform you that your application for the <strong>{scheme_name}</strong> has been officially approved.</p>
            
            <div class="details-box">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #edf2f7; font-weight: bold; color: #64748b; font-size: 13px; text-align: left;">Application ID:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #edf2f7; font-weight: bold; color: #1e293b; font-size: 14px; text-align: right;">{app.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #edf2f7; font-weight: bold; color: #64748b; font-size: 13px; text-align: left;">Scholarship Scheme:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #edf2f7; font-weight: bold; color: #1e293b; font-size: 14px; text-align: right;">{scheme_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold; color: #64748b; font-size: 13px; text-align: left;">Approved Benefit:</td>
                        <td style="padding: 10px 0; font-weight: bold; color: #1e293b; font-size: 14px; text-align: right;">{benefit_amount}</td>
                    </tr>
                </table>
            </div>
            
            <p>The approved benefit has been automatically applied to your Fee Assignment. You may log in to the student portal to view your updated fee details and complete any pending formalities.</p>
            
            <div style="text-align: center;">
                <a href="{portal_url}" class="button">View on Admission Portal</a>
            </div>
        """
    else:
        subject = f"Notification regarding your Scholarship Application: {scheme_name}"
        body_content = f"""
            <div class="status-badge status-rejected">Application Not Selected</div>
            <p>Dear <strong>{app.applicant_name}</strong>,</p>
            <p>Thank you for your application for the <strong>{scheme_name}</strong>. After a comprehensive review of all submissions, we regret to inform you that we are unable to grant your scholarship request at this time.</p>
            
            <div class="details-box">
                <p class="label" style="margin-bottom: 5px;">Reason for Decision:</p>
                <p class="value" style="color: #991b1b;">{app.rejection_reason or 'Eligibility criteria not met / Limited budget availability'}</p>
            </div>
            
            <p>Although you were not selected for this specific scheme, we encourage you to explore other financial aid opportunities available on the admission portal.</p>
            
            <div style="text-align: center;">
                <a href="{portal_url}" class="button">Check Other Schemes</a>
            </div>
        """

    full_html = f"""
        <html>
            <head>{email_styles}</head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <h1>SCHOLARSHIP BOARD</h1>
                    </div>
                    <div class="content">
                        {body_content}
                    </div>
                    <div class="footer">
                        <p>&copy; {frappe.utils.nowdate()[:4]} University Admissions Office. All rights reserved.</p>
                        <p>This is an automated notification. Please do not reply directly to this email.</p>
                    </div>
                </div>
            </body>
        </html>
    """

    try:
        frappe.enqueue(
            method=frappe.sendmail,
            queue="short",
            recipients=[email],
            subject=subject,
            message=full_html,
            reference_doctype="Scholarship Application",
            reference_name=app.name,
            now=frappe.flags.in_test
        )
    except Exception as e:
        frappe.logger().error(f"Scholarship Notification send error for {app.name}: {e}")


def notify_refund_processed(refund_request_name):
    """
    Sends a professional HTML email notification to the applicant 
    when their refund has been successfully processed via Razorpay.
    """
    refund = frappe.get_doc("Refund Request", refund_request_name)
    
    # Get applicant email
    email = frappe.db.get_value("Applicant", refund.applicant, "email")
    applicant_name = frappe.db.get_value("Applicant", refund.applicant, "candidate_name") or "Applicant"
    
    if not email:
        frappe.logger().warning(f"Refund Notification skipped: No email found for applicant {refund.applicant}")
        return

    from frappe.utils import fmt_money
    refund_amount_str = fmt_money(refund.refund_amount)
    
    subject = f"Refund Processed Successfully - {refund.name}"
    
    email_styles = """
        <style>
            .email-container { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }
            .header { background-color: #0d9488; color: #ffffff; padding: 30px; text-align: center; }
            .header h1 { margin: 0; font-size: 22px; letter-spacing: 1px; }
            .content { padding: 40px; background-color: #ffffff; }
            .success-badge { display: inline-block; padding: 6px 12px; border-radius: 4px; font-weight: bold; background-color: #dcfce7; color: #166534; font-size: 12px; margin-bottom: 20px; text-transform: uppercase; }
            .details-box { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 20px; margin: 25px 0; }
            .label { font-weight: bold; color: #64748b; font-size: 13px; text-align: left; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
            .value { font-weight: bold; color: #1e293b; font-size: 14px; text-align: right; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
            .footer { background-color: #f1f5f9; color: #64748b; padding: 20px; text-align: center; font-size: 12px; }
        </style>
    """

    body_html = f"""
        <div class="success-badge">Refund Completed</div>
        <p>Dear <strong>{applicant_name}</strong>,</p>
        <p>This is to inform you that your refund request regarding your admission withdrawal has been successfully processed.</p>
        
        <div class="details-box">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td class="label">Refund Request ID:</td>
                    <td class="value">{refund.name}</td>
                </tr>
                <tr>
                    <td class="label">Refund Amount:</td>
                    <td class="value" style="color: #0d9488;">{refund_amount_str}</td>
                </tr>
                <tr>
                    <td class="label">Transaction ID (Razorpay):</td>
                    <td class="value">{refund.razorpay_refund_id or 'N/A'}</td>
                </tr>
                <tr>
                    <td class="label">Original Payment Ref:</td>
                    <td class="value">{refund.razorpay_payment_id or 'N/A'}</td>
                </tr>
            </table>
        </div>
        
        <p>The amount should reflect in your original payment source (Bank Account/Card/UPI) within 5-7 working days, depending on your bank's processing time.</p>
        
        <p>If you have any further queries, please feel free to reach out to our admissions support team.</p>
    """

    full_html = f"""
        <html>
            <head>{email_styles}</head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <h1>ADMISSIONS OFFICE</h1>
                    </div>
                    <div class="content">
                        {body_html}
                    </div>
                    <div class="footer">
                        <p>&copy; {frappe.utils.nowdate()[:4]} University Admissions. All rights reserved.</p>
                        <p>This is an automated transaction confirmation.</p>
                    </div>
                </div>
            </body>
        </html>
    """

    try:
        frappe.enqueue(
            method=frappe.sendmail,
            queue="short",
            recipients=[email],
            subject=subject,
            message=full_html,
            reference_doctype="Refund Request",
            reference_name=refund.name,
            now=frappe.flags.in_test
        )
        frappe.logger().info(f"Refund Notification queued for {refund.name} to {email}")
    except Exception as e:
        frappe.logger().error(f"Refund Notification error for {refund.name}: {e}")



