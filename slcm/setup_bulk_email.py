import frappe

def run():
    # 1. Create Bulk Email Recipient
    if not frappe.db.exists("DocType", "Bulk Email Recipient"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Bulk Email Recipient",
            "module": "SLCM",
            "custom": 0,
            "istable": 1,
            "editable_grid": 1,
            "fields": [
                {
                    "fieldname": "reference_doctype",
                    "fieldtype": "Link",
                    "options": "DocType",
                    "label": "Reference DocType",
                    "hidden": 1
                },
                {
                    "fieldname": "recipient_reference",
                    "fieldtype": "Dynamic Link",
                    "label": "Recipient Reference",
                    "options": "reference_doctype",
                    "in_list_view": 1,
                    "read_only": 1
                },
                {
                    "fieldname": "recipient_name",
                    "fieldtype": "Data",
                    "label": "Recipient Name",
                    "in_list_view": 1,
                    "read_only": 1
                },
                {
                    "fieldname": "email",
                    "fieldtype": "Data",
                    "label": "Email",
                    "in_list_view": 1,
                    "read_only": 1
                },
                {
                    "fieldname": "status",
                    "fieldtype": "Select",
                    "label": "Status",
                    "options": "Pending\nSent\nFailed",
                    "in_list_view": 1,
                    "read_only": 1
                },
                {
                    "fieldname": "error_message",
                    "fieldtype": "Code",
                    "label": "Error Message",
                    "read_only": 1
                }
            ]
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Created Bulk Email Recipient")
    else:
        print("Bulk Email Recipient already exists")

    # 2. Create Bulk Email
    if not frappe.db.exists("DocType", "Bulk Email"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "Bulk Email",
            "module": "SLCM",
            "custom": 0,
            "autoname": "BE-.YYYY.-.#####",
            "fields": [
                {
                    "fieldname": "reference_doctype",
                    "fieldtype": "Select",
                    "label": "Reference DocType",
                    "options": "Applicant\nPACE Application",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "sender_email_account",
                    "fieldtype": "Link",
                    "label": "Sender Email Account",
                    "options": "Email Account",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "email_template",
                    "fieldtype": "Link",
                    "label": "Email Template",
                    "options": "Email Template"
                },
                {
                    "fieldname": "column_break_1",
                    "fieldtype": "Column Break"
                },
                {
                    "fieldname": "status",
                    "fieldtype": "Select",
                    "label": "Status",
                    "options": "Queued\nIn Progress\nSuccess\nPartial\nError",
                    "read_only": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "triggered_by",
                    "fieldtype": "Link",
                    "label": "Triggered By",
                    "options": "User",
                    "default": "frappe.session.user",
                    "read_only": 1
                },
                {
                    "fieldname": "triggered_on",
                    "fieldtype": "Datetime",
                    "label": "Triggered On",
                    "default": "now",
                    "read_only": 1
                },
                {
                    "fieldname": "section_break_content",
                    "fieldtype": "Section Break",
                    "label": "Content"
                },
                {
                    "fieldname": "subject",
                    "fieldtype": "Data",
                    "label": "Subject",
                    "reqd": 1
                },
                {
                    "fieldname": "use_html",
                    "fieldtype": "Check",
                    "label": "Use HTML",
                    "default": "0"
                },
                {
                    "fieldname": "cc",
                    "fieldtype": "Small Text",
                    "label": "CC"
                },
                {
                    "fieldname": "bcc",
                    "fieldtype": "Small Text",
                    "label": "BCC"
                },
                {
                    "fieldname": "attachment",
                    "fieldtype": "Attach",
                    "label": "Attachment"
                },
                {
                    "fieldname": "message",
                    "fieldtype": "Text Editor",
                    "label": "Message",
                    "depends_on": "eval:!doc.use_html"
                },
                {
                    "fieldname": "message_html",
                    "fieldtype": "Code",
                    "label": "Message (HTML)",
                    "options": "HTML",
                    "depends_on": "eval:doc.use_html"
                },
                {
                    "fieldname": "filters_applied",
                    "fieldtype": "Code",
                    "label": "Filters Applied",
                    "options": "JSON",
                    "read_only": 1
                },
                {
                    "fieldname": "section_break_recipients",
                    "fieldtype": "Section Break",
                    "label": "Recipients"
                },
                {
                    "fieldname": "total_recipients",
                    "fieldtype": "Int",
                    "label": "Total Recipients",
                    "read_only": 1
                },
                {
                    "fieldname": "sent_count",
                    "fieldtype": "Int",
                    "label": "Sent Count",
                    "read_only": 1
                },
                {
                    "fieldname": "failed_count",
                    "fieldtype": "Int",
                    "label": "Failed Count",
                    "read_only": 1
                },
                {
                    "fieldname": "recipients",
                    "fieldtype": "Table",
                    "label": "Recipients",
                    "options": "Bulk Email Recipient"
                }
            ],
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1, "write": 1, "create": 1, "delete": 1,
                    "email": 1, "print": 1, "export": 1, "report": 1, "share": 1
                },
                {
                    "role": "Admission Admin",
                    "read": 1, "write": 1, "create": 1, "delete": 1,
                    "email": 1, "print": 1, "export": 1, "report": 1, "share": 1
                },
                {
                    "role": "PACE Admission Manager",
                    "read": 1, "write": 1, "create": 1, "delete": 1,
                    "email": 1, "print": 1, "export": 1, "report": 1, "share": 1
                }
            ]
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Created Bulk Email")
    else:
        print("Bulk Email already exists")
