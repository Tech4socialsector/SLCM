import frappe

def seed_email_templates():
    """
    Seeds default email templates for demo.
    Run: bench --site slcm.com execute slcm.admission.utils.demo_seed.seed_email_templates
    """
    templates = [
        {
            "template_name": "Application Submitted — NLSIU",
            "trigger_event": "Application Submitted",
            "subject": "Application Received — {{program}} | {{application_id}}",
            "body": """Dear {{candidate_name}},

Thank you for applying to {{program}} at National Law School of India University.

Your application ID is <b>{{application_id}}</b>.

We will notify you of the next steps. Please log in to your applicant portal to track your application status.

Regards,
Admissions Office
NLSIU""",
            "is_active": 1
        },
        {
            "template_name": "Status Changed — NLSIU",
            "trigger_event": "Status Changed",
            "subject": "Application Update — {{program}} | {{application_id}}",
            "body": """Dear {{candidate_name}},

Your application status for <b>{{program}}</b> has been updated.

New Status: <b>{{status}}</b>

Please log in to your applicant portal for details and next steps.

Regards,
Admissions Office
NLSIU""",
            "is_active": 1
        },
        {
            "template_name": "Offer Sent — NLSIU",
            "trigger_event": "Offer Sent",
            "subject": "Admission Offer — {{program}} | {{application_id}}",
            "body": """Dear {{candidate_name}},

Congratulations! You have been offered admission to <b>{{program}}</b> at NLSIU, {{campus}}.

Please log in to your applicant portal to accept your offer and complete payment before <b>{{deadline}}</b>.

Regards,
Admissions Office
NLSIU""",
            "is_active": 1
        },
        {
            "template_name": "Interview Scheduled — NLSIU",
            "trigger_event": "Interview Scheduled",
            "subject": "Interview Scheduled — {{program}} | {{application_id}}",
            "body": """Dear {{candidate_name}},

Your interview for <b>{{program}}</b> has been scheduled.

Date: {{interview_date}}
Time: {{interview_time}}
Location: {{location}}

Please arrive 15 minutes early with a valid photo ID.

Regards,
Admissions Office
NLSIU""",
            "is_active": 1
        }
    ]
    for t in templates:
        if not frappe.db.exists("Email Template Config", t["template_name"]):
            doc = frappe.get_doc({"doctype": "Email Template Config", **t})
            doc.insert(ignore_permissions=True)
            print(f"\u2713 Email template created: {t['template_name']}")
        else:
            print(f"  Already exists: {t['template_name']}")
    frappe.db.commit()
    print("\u2713 Email templates seeded.")
