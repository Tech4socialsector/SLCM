# PACE EMAIL CONFIGURATION

Email Template Name: PACE Application Submitted
Subject: Pace Application Form Submitted Successfully - {{ doc.name }}

--- JINJA TEMPLATE CODE ---

<html>
<head>
<meta charset="UTF-8">
<style>
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 14px;
        color: #333333;
        line-height: 1.6;
        margin: 0;
        padding: 0;
        background-color: #f4f4f4;
    }
    .container {
        max-width: 600px;
        margin: 20px auto;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        overflow: hidden;
    }
    .header {
        background-color: #920c24;
        padding: 25px 20px;
        text-align: center;
        color: #ffffff;
    }
    .header h2 {
        margin: 0;
        font-size: 18px;
        letter-spacing: 0.5px;
    }
    .content {
        padding: 30px;
    }
    .footer {
        background-color: #f9f9f9;
        padding: 20px;
        text-align: center;
        font-size: 12px;
        color: #777777;
        border-top: 1px solid #eeeeee;
    }
    .button-container {
        text-align: center;
        margin: 30px 0;
    }
    .button {
        background-color: #920c24;
        color: #ffffff !important;
        padding: 12px 25px;
        text-decoration: none;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
    }
    .ref-box {
        background-color: #fff8f8;
        border: 1px solid #920c24;
        padding: 15px;
        margin: 20px 0;
        text-align: center;
    }
    .ref-number {
        font-size: 18px;
        font-weight: bold;
        color: #920c24;
    }
    .section-title {
        color: #920c24;
        font-size: 16px;
        font-weight: bold;
        margin-top: 25px;
        margin-bottom: 10px;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 5px;
    }
    ul {
        padding-left: 20px;
        margin-bottom: 20px;
    }
    li {
        margin-bottom: 8px;
    }
</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Pace Application Form Submitted Successfully</h2>
        </div>
        <div class="content">
            <p>Dear {{ first_name }},</p>

            <p>Your application to <strong>National Law School of India University (NLSIU)</strong> for the <strong>{{ program }} (PACE)</strong> has been successfully submitted. We appreciate your interest in the programme and your effort in completing the application.</p>

            <div class="ref-box">
                <div style="color: #666; margin-bottom: 5px;">Your Application Reference Number is:</div>
                <div class="ref-number">{{ applicant_id }}</div>
            </div>
            
            <p>Please keep this number for future communication and tracking purposes.</p>

            <div class="section-title">What happens next?</div>
            <ul>
                <li>Your application will be reviewed for eligibility and completeness.</li>
                <li>The admissions team will verify the documents submitted by you.</li>
                <li>Upon successful verification, your enrolment will be confirmed and communicated to you.</li>
            </ul>

            <p>You can track your application status at any time using the link below:</p>

            <div class="button-container">
                <a href="{{ admission_portal_url }}" class="button">Track Your Application</a>
            </div>

            <p>If any additional information or documents are required, our team will reach out to you. We recommend keeping an eye on your registered email for further updates.</p>

            <p>For any assistance, please contact the Office of Admissions.</p>

            <p style="margin-top: 40px; border-top: 1px solid #f0f0f0; padding-top: 20px;">
                Warm regards,<br>
                <strong>Office of Admissions</strong><br>
                National Law School of India University (NLSIU)
            </p>
        </div>
        <div class="footer">
            <p>This is an automated notification. Please do not reply to this email.</p>
            <p>&copy; {{ generated_on[:4] }} National Law School of India University (NLSIU). All rights reserved.</p>
        </div>
    </div>
</body>
</html>
