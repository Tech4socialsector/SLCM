<!-- 
Name: PACE Verifier Assignment
Subject: Assignment Notification: New PACE Applications for Document Verification
-->

<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; border: 1px solid #ddd; padding: 20px;">
    <div style="text-align: center; border-bottom: 2px solid #7b1a1a; padding-bottom: 10px; margin-bottom: 20px;">
        <h2 style="color: #7b1a1a; margin: 0;">PACE Admissions Management</h2>
    </div>

    <p>Dear {{ verifier_name }},</p>

    <p>This is to inform you that <strong>{{ targets|length }}</strong> new PACE applications have been assigned to you for document verification. Please review the applicant details below and proceed with the verification process in the system.</p>

    <div style="margin: 25px 0;">
        <h3 style="color: #7b1a1a; border-left: 4px solid #7b1a1a; padding-left: 10px; margin-bottom: 15px;">Assigned Applicants List</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <thead>
                <tr style="background-color: #f8f8f8; border-bottom: 2px solid #7b1a1a;">
                    <th style="padding: 12px; text-align: left; border: 1px solid #eee;">S.No</th>
                    <th style="padding: 12px; text-align: left; border: 1px solid #eee;">Application ID</th>
                    <th style="padding: 12px; text-align: left; border: 1px solid #eee;">Applicant Full Name</th>
                    <th style="padding: 12px; text-align: left; border: 1px solid #eee;">Programme</th>
                </tr>
            </thead>
            <tbody>
                {% for app in targets %}
                <tr>
                    <td style="padding: 10px; border: 1px solid #eee; text-align: center;">{{ loop.index }}</td>
                    <td style="padding: 10px; border: 1px solid #eee; font-weight: bold; color: #7b1a1a;">{{ app.name }}</td>
                    <td style="padding: 10px; border: 1px solid #eee;">{{ app.applicant_name }}</td>
                    <td style="padding: 10px; border: 1px solid #eee;">{{ app.programme }}</td>
                </tr>
                {% endfor %}
            </tbody>
            <tfoot>
                <tr style="background-color: #fcfcfc; font-weight: bold;">
                    <td colspan="3" style="padding: 12px; border: 1px solid #eee; text-align: right;">Total Assignments:</td>
                    <td style="padding: 12px; border: 1px solid #eee; text-align: center; color: #7b1a1a;">{{ targets|length }}</td>
                </tr>
            </tfoot>
        </table>
    </div>

    <div style="background-color: #fff9f9; padding: 15px; border-radius: 4px; border: 1px solid #ffebeb; margin-bottom: 20px;">
        <p style="margin: 0; font-size: 13px;"><strong>Next Steps:</strong> Please log in to the <a href="{{ frappe.utils.get_url() }}/desk#List/PACE%20Document%20Verification/List" style="color: #7b1a1a; text-decoration: underline;">Verification Dashboard</a> to access these records and update their status (Verified / Returned for Correction).</p>
    </div>

    <p style="font-size: 14px;">If you encounter any technical issues or require clarification regarding these assignments, please contact the admissions administrator.</p>

    <div style="margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px; font-size: 13px; color: #666;">
        <p style="margin: 0;">Best Regards,</p>
        <p style="margin: 5px 0 0 0; font-weight: bold; color: #7b1a1a;">PACE Admissions Team</p>
        <p style="margin: 0;">National Law School of India University</p>
    </div>
</div>
