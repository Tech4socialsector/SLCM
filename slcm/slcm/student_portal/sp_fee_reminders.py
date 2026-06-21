import frappe
from frappe.utils import get_url


def seed_email_templates():
	"""Insert Student Portal fee reminder Email Templates only if they do not already exist."""
	try:
		for t in _get_templates():
			if frappe.db.exists("Email Template", t["name"]):
				continue
			frappe.get_doc({"doctype": "Email Template", **t}).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		pass


def _get_templates():
	return [
		{
			"name": "Student Fee Reminder - 7 Days Before Due",
			"subject": "Fee Payment Reminder: {{ fee_head }} is due in 7 days",
			"reference_doctype": "Fee Demand",
			"use_html": 1,
			"enabled": 1,
			"response": _body_7day(),
		},
		{
			"name": "Student Fee Reminder - 1 Day Before Due",
			"subject": "Final Reminder: {{ fee_head }} is due tomorrow",
			"reference_doctype": "Fee Demand",
			"use_html": 1,
			"enabled": 1,
			"response": _body_1day(),
		},
		{
			"name": "Student Fee Overdue Notice",
			"subject": "Overdue Notice: {{ fee_head }} payment is past due",
			"reference_doctype": "Fee Demand",
			"use_html": 1,
			"enabled": 1,
			"response": _body_overdue(),
		},
	]


def _portal_fees_url():
	return get_url("/student-portal/fees")


def _email_wrapper(header_color, header_text, body_content):
	"""Wraps email body in a clean, professional layout."""
	fees_url = _portal_fees_url()
	return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:32px 0;">
  <tr><td align="center">
    <table width="580" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);">

      <!-- Header -->
      <tr>
        <td style="background:{header_color};padding:24px 32px;">
          <p style="margin:0;font-size:18px;font-weight:bold;color:#ffffff;">{header_text}</p>
          <p style="margin:4px 0 0;font-size:13px;color:rgba(255,255,255,0.8);">National Law School of India University</p>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="padding:28px 32px;">
          {body_content}

          <!-- CTA Button -->
          <div style="margin:28px 0 8px;text-align:center;">
            <a href="{fees_url}"
               style="display:inline-block;background:{header_color};color:#ffffff;
                      text-decoration:none;padding:12px 32px;border-radius:6px;
                      font-size:14px;font-weight:bold;letter-spacing:0.3px;">
              View &amp; Pay Now
            </a>
          </div>
          <p style="margin:12px 0 0;font-size:12px;color:#9ca3af;text-align:center;">
            Or copy this link: <a href="{fees_url}" style="color:#6b7280;">{fees_url}</a>
          </p>
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px;">
          <p style="margin:0;font-size:12px;color:#6b7280;">
            This is an automated reminder from the Finance &amp; Accounts Office.<br>
            If you have already made the payment, please disregard this email or
            contact <strong>{{ sender_name }}</strong> with your payment receipt.
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def _fee_details_table(accent_color):
	return f"""<table width="100%" cellpadding="0" cellspacing="0"
       style="border-collapse:collapse;margin:20px 0;font-size:14px;">
  <tr style="background:{accent_color};">
    <td style="padding:10px 14px;font-weight:bold;color:#374151;width:45%;
               border:1px solid #e5e7eb;">Fee Head</td>
    <td style="padding:10px 14px;color:#111827;border:1px solid #e5e7eb;">{{{{ fee_head }}}}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;font-weight:bold;color:#374151;
               border:1px solid #e5e7eb;">Outstanding Amount</td>
    <td style="padding:10px 14px;color:#111827;font-weight:bold;border:1px solid #e5e7eb;">
      &#8377;{{{{ outstanding_amount }}}}</td>
  </tr>
  <tr style="background:{accent_color};">
    <td style="padding:10px 14px;font-weight:bold;color:#374151;
               border:1px solid #e5e7eb;">Due Date</td>
    <td style="padding:10px 14px;color:#111827;border:1px solid #e5e7eb;">{{{{ due_date }}}}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;font-weight:bold;color:#374151;
               border:1px solid #e5e7eb;">Student ID</td>
    <td style="padding:10px 14px;color:#111827;border:1px solid #e5e7eb;">{{{{ student_id }}}}</td>
  </tr>
</table>"""


def _body_7day():
	body = f"""<p style="margin:0 0 6px;font-size:15px;color:#111827;">Dear <strong>{{{{ student_name }}}}</strong>,</p>
<p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.6;">
  This is a friendly reminder that the following fee payment is due in
  <strong style="color:#d97706;">7 days</strong>.
  Please ensure timely payment to avoid any late charges.
</p>
{_fee_details_table("#fef9ee")}
<p style="margin:0;font-size:13px;color:#6b7280;line-height:1.6;">
  Regards,<br><strong style="color:#374151;">{{{{ sender_name }}}}</strong><br>
  Finance &amp; Accounts Office, NLSIU
</p>"""
	return _email_wrapper("#d97706", "Fee Payment Reminder — 7 Days", body)


def _body_1day():
	body = f"""<p style="margin:0 0 6px;font-size:15px;color:#111827;">Dear <strong>{{{{ student_name }}}}</strong>,</p>
<p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.6;">
  This is a <strong>final reminder</strong> — your fee payment is due
  <strong style="color:#ea580c;">tomorrow</strong>.
  Please complete your payment today to avoid any late fees or penalties.
</p>
{_fee_details_table("#fff7ed")}
<p style="margin:0;font-size:13px;color:#6b7280;line-height:1.6;">
  Regards,<br><strong style="color:#374151;">{{{{ sender_name }}}}</strong><br>
  Finance &amp; Accounts Office, NLSIU
</p>"""
	return _email_wrapper("#ea580c", "Final Reminder — Due Tomorrow", body)


def _body_overdue():
	body = f"""<p style="margin:0 0 6px;font-size:15px;color:#111827;">Dear <strong>{{{{ student_name }}}}</strong>,</p>
<p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.6;">
  Your fee payment is <strong style="color:#dc2626;">overdue</strong>.
  Please clear your outstanding dues <strong>immediately</strong> to avoid further
  academic or administrative action.
</p>
{_fee_details_table("#fef2f2")}
<p style="margin:0;font-size:13px;color:#6b7280;line-height:1.6;">
  Regards,<br><strong style="color:#374151;">{{{{ sender_name }}}}</strong><br>
  Finance &amp; Accounts Office, NLSIU
</p>"""
	return _email_wrapper("#dc2626", "Overdue Fee Notice", body)
