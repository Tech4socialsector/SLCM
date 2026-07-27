// slcm/public/js/bulk_email_dialog.js

frappe.provide('slcm');

slcm.show_bulk_email_dialog = function (reference_doctype, docnames, listview) {
    let email_field = reference_doctype === "Applicant" ? "email" : "email_address";
    let name_field = reference_doctype === "Applicant" ? "name" : "applicant_name";

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: reference_doctype,
            filters: { "name": ["in", docnames] },
            fields: ["name", name_field, email_field]
        },
        callback: function (r) {
            let recipients = [];
            let recipients_data = [];
            if (r.message) {
                r.message.forEach(d => {
                    if (d[email_field]) {
                        let display_name = d[name_field] || d.name;
                        recipients.push(`${display_name} <${d[email_field]}>`);
                        recipients_data.push({
                            id: d.name,
                            applicant_name: display_name,
                            email: d[email_field]
                        });
                    }
                });
            }

            if (recipients.length === 0) {
                frappe.msgprint(__('None of the selected records have valid email addresses.'));
                return;
            }

            let d = new frappe.ui.Dialog({
                title: __('Compose Bulk Email'),
                size: 'extra-large',
                fields: [
                    {
                        fieldname: 'sender_email_account',
                        label: __('Sender Email Account'),
                        fieldtype: 'Link',
                        options: 'Email Account',
                        reqd: 1,
                        get_query: () => {
                            return { filters: { enable_outgoing: 1 } };
                        }
                    },
                    {
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'email_template',
                        label: __('Email Template'),
                        fieldtype: 'Link',
                        options: 'Email Template',
                        onchange: function () {
                            let template = d.get_value('email_template');
                            if (template) {
                                frappe.db.get_doc('Email Template', template).then(doc => {
                                    d.set_value('subject', doc.subject);
                                    d.set_value('message_type', doc.use_html ? 'HTML' : 'Text');
                                    if (doc.use_html) {
                                        d.set_value('message_html', doc.response_html || doc.response);
                                    } else {
                                        d.set_value('message', doc.response);
                                    }
                                });
                            }
                        }
                    },
                    {
                        fieldtype: 'Section Break'
                    },
                    {
                        fieldname: 'cc',
                        label: __('CC'),
                        fieldtype: 'Small Text'
                    },
                    {
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'bcc',
                        label: __('BCC'),
                        fieldtype: 'Small Text'
                    },
                    {
                        fieldtype: 'Section Break'
                    },
                    {
                        fieldname: 'subject',
                        label: __('Subject'),
                        fieldtype: 'Data',
                        reqd: 1
                    },
                    {
                        fieldtype: 'Section Break'
                    },
                    {
                        fieldname: 'attachment',
                        label: __('Attachment'),
                        fieldtype: 'Attach'
                    },
                    {
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'message_type',
                        label: __('Message Type'),
                        fieldtype: 'Select',
                        options: 'Text\nHTML',
                        default: 'Text',
                        onchange: function() {
                            let type = d.get_value('message_type');
                            d.set_df_property('message', 'hidden', type === 'HTML' ? 1 : 0);
                            d.set_df_property('message_html', 'hidden', type === 'Text' ? 1 : 0);
                        }
                    },
                    {
                        fieldtype: 'Section Break'
                    },
                    {
                        fieldname: 'message',
                        label: __('Message'),
                        fieldtype: 'Text Editor'
                    },
                    {
                        fieldname: 'message_html',
                        label: __('Message (HTML)'),
                        fieldtype: 'Code',
                        options: 'HTML',
                        hidden: 1
                    },
                    {
                        fieldtype: 'Section Break',
                        label: __('Selected Recipients (' + recipients_data.length + ')')
                    },
                    {
                        fieldname: 'recipients_table',
                        label: __('Recipients'),
                        fieldtype: 'Table',
                        read_only: 1,
                        cannot_add_rows: true,
                        cannot_delete_rows: true,
                        in_place_edit: false,
                        data: recipients_data,
                        fields: [
                            { fieldname: 'id', fieldtype: 'Data', label: __('ID'), in_list_view: 1, read_only: 1, columns: 3 },
                            { fieldname: 'applicant_name', fieldtype: 'Data', label: __('Name'), in_list_view: 1, read_only: 1, columns: 4 },
                            { fieldname: 'email', fieldtype: 'Data', label: __('Email'), in_list_view: 1, read_only: 1, columns: 3 }
                        ]
                    }
                ],
                primary_action_label: __('Send'),
                primary_action: function (values) {
                    if (values.message_type === "HTML" && !values.message_html) {
                        frappe.msgprint(__('HTML Message cannot be empty.'));
                        return;
                    }
                    if (values.message_type === "Text" && !values.message) {
                        frappe.msgprint(__('Message cannot be empty.'));
                        return;
                    }

                    d.hide();

                    let filters_applied = null;
                    if (listview && listview.filter_area) {
                        filters_applied = JSON.stringify(listview.filter_area.get());
                    }

                    frappe.call({
                        method: "slcm.slcm.doctype.bulk_email.bulk_email.create_and_queue",
                        args: {
                            reference_doctype: reference_doctype,
                            recipient_names: JSON.stringify(docnames),
                            sender_email_account: values.sender_email_account,
                            cc: values.cc,
                            bcc: values.bcc,
                            subject: values.subject,
                            use_html: values.message_type === "HTML" ? 1 : 0,
                            message: values.message,
                            message_html: values.message_html,
                            attachment: values.attachment,
                            email_template: values.email_template,
                            filters_applied: filters_applied
                        },
                        callback: function (r) {
                            if (r.message) {
                                let bulk_email_name = r.message;
                                slcm.show_bulk_email_progress(bulk_email_name);
                            }
                        }
                    });
                }
            });

            d.show();

            // Inject CSS to forcefully hide the edit pencil icon and checkboxes since this table is strictly for viewing
            let style = `
                <style>
                    .frappe-control[data-fieldname="recipients_table"] .grid-row-check { display: none !important; }
                    .frappe-control[data-fieldname="recipients_table"] svg use[href="#icon-edit"],
                    .frappe-control[data-fieldname="recipients_table"] svg.icon-edit,
                    .frappe-control[data-fieldname="recipients_table"] .btn-open-row { display: none !important; }
                </style>
            `;
            $(style).appendTo(d.$wrapper);
        }
    });
};

slcm.show_bulk_email_progress = function (bulk_email_name) {
    let progress_dialog = new frappe.ui.Dialog({
        title: __('Sending Bulk Emails'),
        fields: [
            {
                fieldname: 'progress_html',
                fieldtype: 'HTML',
                options: `<div style="text-align: center; padding: 20px;">
                    <div class="progress" style="height: 20px; margin-bottom: 10px;">
                        <div class="progress-bar progress-bar-success" role="progressbar" style="width: 0%;" id="be-progress-bar"></div>
                    </div>
                    <p id="be-progress-text">Sending Emails...</p>
                </div>`
            }
        ],
        primary_action_label: __('View Log'),
        primary_action: function () {
            progress_dialog.hide();
            frappe.set_route('Form', 'Bulk Email', bulk_email_name);
        }
    });

    progress_dialog.get_primary_btn().prop('disabled', true);
    progress_dialog.show();

    frappe.realtime.on("bulk_email_progress", function (data) {
        if (data.bulk_email !== bulk_email_name) return;

        let percent = (data.sent + data.failed) / data.total * 100;
        $('#be-progress-bar').css('width', percent + '%');
        $('#be-progress-text').text(`Processed ${data.sent + data.failed} of ${data.total} (Sent: ${data.sent}, Failed: ${data.failed})`);
    });

    const handle_complete = function(data) {
        let percent = 100;
        let color_class = data.status === 'Success' ? 'progress-bar-success' : (data.status === 'Error' ? 'progress-bar-danger' : 'progress-bar-warning');
        
        $('#be-progress-bar').css('width', percent + '%').removeClass('progress-bar-success').addClass(color_class);
        
        if (data.crashed) {
            $('#be-progress-text').html(`<strong>Job Failed</strong><br>Something went wrong before all emails could be sent — check the Server Response field on the log for details.`);
        } else {
            $('#be-progress-text').html(`<strong>Completed!</strong> ${data.sent} Sent, ${data.failed} Failed. Status: ${data.status}`);
        }
        
        progress_dialog.get_primary_btn().prop('disabled', false);
    };

    frappe.realtime.on("bulk_email_complete", function(data) {
        if (data.bulk_email !== bulk_email_name) return;
        handle_complete(data);
    });

    // Check state periodically as a robust fallback for flaky WebSocket connections
    let poll_interval = setInterval(() => {
        frappe.db.get_value('Bulk Email', bulk_email_name, ['status', 'sent_count', 'failed_count', 'total_recipients', 'server_response']).then(r => {
            if (!r.message) return;
            let doc = r.message;
            if (['Success', 'Partial', 'Error'].includes(doc.status)) {
                clearInterval(poll_interval);
                handle_complete({
                    bulk_email: bulk_email_name,
                    sent: doc.sent_count || 0,
                    failed: doc.failed_count || 0,
                    total: doc.total_recipients || 0,
                    status: doc.status,
                    crashed: doc.status === 'Error' && doc.server_response && doc.server_response.includes("CRASHED")
                });
            } else {
                let sent = doc.sent_count || 0;
                let failed = doc.failed_count || 0;
                let total = doc.total_recipients || 1;
                let percent = (sent + failed) / total * 100;
                $('#be-progress-bar').css('width', percent + '%');
                $('#be-progress-text').text(`Processed ${sent + failed} of ${doc.total_recipients || 0} (Sent: ${sent}, Failed: ${failed})`);
            }
        });
    }, 2000);

    progress_dialog.onhide = () => {
        clearInterval(poll_interval);
    };
};
