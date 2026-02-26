frappe.ui.form.on("Email Template Config", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Send Test Email", function() {
                frappe.prompt([
                    {label: "Recipient Email", fieldname: "email", fieldtype: "Data", reqd: 1}
                ], function(values) {
                    frappe.call({
                        method: "slcm.admission.doctype.email_template_config.email_template_config.send_test_email",
                        args: {template_name: frm.doc.name, recipient: values.email},
                        callback: function(r) {
                            frappe.show_alert({message: "Test email sent.", indicator: "green"}, 5);
                        }
                    });
                }, "Send Test Email", "Send");
            });
        }
        if (!frm.doc.is_active) {
            frm.dashboard.set_headline(
                '<span style="color:gray">⚪ This template is inactive — emails will not be sent</span>'
            );
        } else {
            frm.dashboard.set_headline(
                '<span style="color:green">🟢 Active — emails will fire on: ' + (frm.doc.trigger_event || "") + '</span>'
            );
        }
    },
    trigger_event: function(frm) {
        const placeholders = {
            "Application Submitted": "{{candidate_name}}, {{program}}, {{campus}}, {{applicant_id}}, {{submission_date}}",
            "Status Changed":        "{{candidate_name}}, {{program}}, {{campus}}, {{applicant_id}}, {{status}}, {{old_status}}",
            "Offer Sent":            "{{candidate_name}}, {{program}}, {{campus}}, {{applicant_id}}, {{offer_amount}}, {{deadline}}",
            "Document Rejected":     "{{candidate_name}}, {{program}}, {{document_name}}, {{rejection_reason}}",
            "Deadline Reminder":     "{{candidate_name}}, {{program}}, {{deadline}}, {{action_required}}",
            "Interview Scheduled":   "{{candidate_name}}, {{program}}, {{campus}}, {{interview_date}}, {{interview_time}}, {{location}}",
            "Payment Confirmed":     "{{candidate_name}}, {{program}}, {{campus}}, {{amount_paid}}, {{transaction_id}}, {{receipt_number}}"
        };
        if (frm.doc.trigger_event) {
            frm.set_value("available_placeholders", placeholders[frm.doc.trigger_event] || "");
            frappe.show_alert({
                message: "Placeholders updated for " + frm.doc.trigger_event,
                indicator: "blue"
            }, 4);
        }
    }
});
