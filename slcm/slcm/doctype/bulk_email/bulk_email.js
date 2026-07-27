// Copyright (c) 2026, TFSS and contributors

frappe.ui.form.on('Bulk Email', {
    setup: function(frm) {
        frm.set_query('sender_email_account', function() {
            return {
                filters: {
                    enable_outgoing: 1
                }
            };
        });

        frappe.realtime.on("bulk_email_row_update", function(data) {
            if (frm.doc.name !== data.bulk_email) return;

            let row = (frm.doc.recipients || []).find(r => r.name === data.row_name);
            if (row) {
                row.status = data.status;
                if (data.error_message) row.error_message = data.error_message;
                frm.fields_dict.recipients.grid.refresh_row(row.name);
            }
        });
    },

    refresh: function(frm) {
        if (['Partial', 'Error'].includes(frm.doc.status) && frm.doc.failed_count > 0) {
            frm.add_custom_button(__('Resend Failed Recipients'), function() {
                frappe.call({
                    method: 'slcm.slcm.doctype.bulk_email.bulk_email.resend_failed',
                    args: {
                        bulk_email_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                            if (typeof slcm !== 'undefined' && slcm.show_bulk_email_progress) {
                                slcm.show_bulk_email_progress(frm.doc.name);
                            }
                        }
                    }
                });
            });
        }

        if (['Queued', 'In Progress'].includes(frm.doc.status)) {
            if (typeof slcm !== 'undefined' && slcm.show_bulk_email_progress) {
                slcm.show_bulk_email_progress(frm.doc.name);
            }
        }

        if (frm.doc.status === 'Error' && frm.doc.server_response) {
            frm.dashboard.set_headline_alert(
                `<div class="text-danger">
                    <strong>Job Error:</strong><br>
                    <pre style="max-height: 200px; overflow: auto; margin-top: 10px; background-color: #fff5f5; border: 1px solid #fed7d7;">${frappe.utils.escape_html(frm.doc.server_response)}</pre>
                </div>`
            );
        }
    },

    use_html: function(frm) {
        // Handled automatically by depends_on condition, but we can trigger refresh
        // No additional code needed here as frappe handles depends_on dynamically
    },

    email_template: function(frm) {
        if (frm.doc.email_template) {
            frappe.db.get_doc('Email Template', frm.doc.email_template).then(doc => {
                frm.set_value('subject', doc.subject);
                frm.set_value('use_html', doc.use_html);
                if (doc.use_html) {
                    frm.set_value('message_html', doc.response_html || doc.response);
                } else {
                    frm.set_value('message', doc.response);
                }
            });
        }
    }
});
