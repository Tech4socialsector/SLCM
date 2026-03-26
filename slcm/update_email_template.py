import frappe

def update_template():
    template_name = "Seat Allocation Result Notification"
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f0f2f5;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:40px 16px;">
  <tr>
    <td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

        <!-- HEADER -->
        <tr>
          <td style="background:#1a3c6e;border-radius:8px 8px 0 0;padding:32px 40px;text-align:center;">
            <p style="margin:0 0 6px;font-size:11px;color:rgba(255,255,255,0.6);letter-spacing:2px;text-transform:uppercase;">
              Office of Admissions
            </p>
            <h1 style="margin:0;font-size:22px;font-weight:600;color:#ffffff;">
              Seat Allocation Update
            </h1>
            <p style="margin:8px 0 0;font-size:13px;color:rgba(255,255,255,0.7);">
              {{ doc.admission_cycle }} Admission Cycle
            </p>
          </td>
        </tr>

        <!-- GOLD LINE -->
        <tr>
          <td style="height:3px;background:linear-gradient(90deg,#c8a14b,#f0d080,#c8a14b);"></td>
        </tr>

        <!-- BODY -->
        <tr>
          <td style="background:#ffffff;padding:36px 40px;">

            <!-- GREETING -->
            <p style="margin:0 0 16px;font-size:15px;color:#1e293b;">
              Dear <strong>{{ doc.candidate_name or "Applicant" }}</strong>,
            </p>
            <p style="margin:0 0 28px;font-size:14px;color:#475569;line-height:1.7;">
              We are writing to inform you that your seat allocation result for the
              <strong style="color:#1a3c6e;">{{ doc.admission_cycle }}</strong> admission
              cycle has been updated. Please review your details below.
            </p>

            <!-- DETAILS TABLE -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;margin-bottom:24px;font-size:13px;">
              <tr style="background:#f8fafc;">
                <td style="padding:10px 16px;color:#64748b;width:150px;border-bottom:1px solid #e2e8f0;">Application ID</td>
                <td style="padding:10px 16px;color:#1e293b;font-weight:600;border-bottom:1px solid #e2e8f0;">{{ doc.applicant_id }}</td>
              </tr>
              <tr>
                <td style="padding:10px 16px;color:#64748b;border-bottom:1px solid #e2e8f0;">Campus</td>
                <td style="padding:10px 16px;color:#1e293b;font-weight:600;border-bottom:1px solid #e2e8f0;">{{ doc.campus }}</td>
              </tr>
              <tr style="background:#f8fafc;">
                <td style="padding:10px 16px;color:#64748b;border-bottom:1px solid #e2e8f0;">Programme</td>
                <td style="padding:10px 16px;color:#1e293b;font-weight:600;border-bottom:1px solid #e2e8f0;">{{ doc.program }}</td>
              </tr>
              <tr>
                <td style="padding:10px 16px;color:#64748b;border-bottom:1px solid #e2e8f0;">Category</td>
                <td style="padding:10px 16px;color:#1e293b;font-weight:600;border-bottom:1px solid #e2e8f0;">{{ doc.allocated_category or "General" }}</td>
              </tr>
              <tr style="background:#f8fafc;">
                <td style="padding:10px 16px;color:#64748b;border-bottom:1px solid #e2e8f0;">Merit Score</td>
                <td style="padding:10px 16px;color:#1e293b;font-weight:600;border-bottom:1px solid #e2e8f0;">{{ doc.total_score or "N/A" }}</td>
              </tr>
              <tr style="background:#1a3c6e;">
                <td style="padding:12px 16px;color:rgba(255,255,255,0.7);font-size:12px;">Current Status</td>
                <td style="padding:12px 16px;color:#ffffff;font-weight:700;letter-spacing:0.5px;">
                  {{ doc.selection_status | upper }}
                </td>
              </tr>
            </table>

            <!-- STATUS MESSAGE -->
            {% if doc.selection_status == "Fee Paid" %}
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0fdf4;border-left:4px solid #22c55e;border-radius:0 6px 6px 0;margin-bottom:28px;">
              <tr><td style="padding:16px 20px;">
                <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#166534;">✅ Admission Confirmed</p>
                <p style="margin:0;font-size:13px;color:#166534;line-height:1.7;">
                  Your fee payment has been received and your seat is fully secured.
                  Further details on orientation and class commencement will follow shortly.
                </p>
              </td></tr>
            </table>

            {% elif doc.selection_status in ["Selected", "Offer Issued", "Offer Accepted"] %}
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0fdf4;border-left:4px solid #22c55e;border-radius:0 6px 6px 0;margin-bottom:28px;">
              <tr><td style="padding:16px 20px;">
                <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#166534;">🎉 Congratulations — You Have Been Selected</p>
                <p style="margin:0;font-size:13px;color:#166534;line-height:1.7;">
                  Please log in to the portal to accept your offer and complete the fee payment
                  within the prescribed timeline to secure your seat.
                </p>
              </td></tr>
            </table>

            {% elif doc.selection_status == "Waitlisted" %}
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#fffbeb;border-left:4px solid #f59e0b;border-radius:0 6px 6px 0;margin-bottom:28px;">
              <tr><td style="padding:16px 20px;">
                <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#92400e;">⏳ You Are Currently Waitlisted</p>
                <p style="margin:0;font-size:13px;color:#92400e;line-height:1.7;">
                  {% if doc.overall_rank %}Your current rank is <strong>#{{ doc.overall_rank }}</strong>. {% endif %}
                  You will be notified automatically if a seat becomes available. No action is required at this time.
                </p>
              </td></tr>
            </table>

            {% elif doc.selection_status in ["Rejected", "Offer Declined", "Offer Expired"] %}
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#fef2f2;border-left:4px solid #ef4444;border-radius:0 6px 6px 0;margin-bottom:28px;">
              <tr><td style="padding:16px 20px;">
                <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#991b1b;">Application Status Update</p>
                <p style="margin:0;font-size:13px;color:#991b1b;line-height:1.7;">
                  We regret to inform you that your application was not successful in this round.
                  Please log in to the portal to explore available options or await future updates.
                </p>
              </td></tr>
            </table>
            {% endif %}

            <!-- CTA BUTTON -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
              <tr>
                <td align="center">
                  <a href="https://apfslcm.boscosofttech.com/admission-dashboard"
                     style="display:inline-block;background:#1a3c6e;color:#ffffff;padding:13px 32px;
                            text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">
                    Access Admission Portal &rarr;
                  </a>
                </td>
              </tr>
            </table>

            <!-- DIVIDER -->
            <div style="height:1px;background:#e2e8f0;margin-bottom:24px;"></div>

            <!-- SIGN OFF -->
            <p style="margin:0 0 4px;font-size:13px;color:#475569;line-height:1.7;">
              For any queries, please contact the admissions office.
            </p>
            <p style="margin:16px 0 0;font-size:13px;color:#334155;line-height:1.8;">
              Regards,<br>
              <strong>Admissions Office</strong><br>
              <span style="color:#64748b;font-size:12px;">{{ doc.campus }}</span>
            </p>

          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f8fafc;border-top:1px solid #e2e8f0;border-radius:0 0 8px 8px;
                     padding:16px 40px;text-align:center;">
            <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.6;">
              This is an automated message from the Admissions Portal. Please do not reply to this email.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""

    if frappe.db.exists("Email Template", template_name):
        doc = frappe.get_doc("Email Template", template_name)
        doc.response = html_content
        doc.save()
        frappe.db.commit()
        print(f"Successfully updated '{template_name}' template.")
    else:
        doc = frappe.new_doc("Email Template")
        doc.name = template_name
        doc.subject = "Seat Allocation Update"
        doc.response = html_content
        doc.save()
        frappe.db.commit()
        print(f"Successfully created '{template_name}' template.")

if __name__ == "__main__":
    update_template()
