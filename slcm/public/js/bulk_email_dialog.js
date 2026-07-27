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
            fields: ["name", name_field, email_field],
            limit_page_length: 0
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
                        fieldtype: 'Section Break'
                    },
                    {
                        fieldname: 'recipients_html',
                        label: __('Recipients'),
                        fieldtype: 'HTML'
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

                    d.job_started = true;
                    d.render_recipient_page(d.current_page); // Re-render to disable 'Remove' buttons

                    let final_recipients = d.recipient_data.filter(r => !r.removed).map(r => r.id);
                    if (final_recipients.length === 0) {
                        frappe.msgprint(__('No valid recipients left.'));
                        return;
                    }

                    let filters_applied = null;
                    if (listview && listview.filter_area) {
                        filters_applied = JSON.stringify(listview.filter_area.get());
                    }

                    frappe.call({
                        method: "slcm.slcm.doctype.bulk_email.bulk_email.create_and_queue",
                        args: {
                            reference_doctype: reference_doctype,
                            recipient_names: JSON.stringify(final_recipients),
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
                                d.hide();
                                slcm.show_bulk_email_progress(bulk_email_name, null);
                            }
                        }
                    });
                }
            });

            d.recipient_data = recipients_data.map(r => ({ ...r, status: 'Queued', removed: false }));
            d.current_page = 0;
            d.job_started = false;
            const page_size = 20;

            d.render_recipient_page = function(page) {
                d.current_page = page;
                let active = d.recipient_data.filter(r => !r.removed);
                let total = active.length;
                let start = page * page_size;
                let end = Math.min(start + page_size, total);
                let slice = active.slice(start, end);
                let total_pages = Math.ceil(total / page_size);

                let rows = slice.map((r, i) => {
                    let color = r.status === 'Sent' ? 'green' : (r.status === 'Failed' ? 'red' : (r.status === 'Sending' ? 'blue' : 'orange'));
                    let status_html = `<span class="indicator-pill ${color}">${r.status}</span>`;
                    if (r.error_message) {
                        status_html += ` <i class="fa fa-info-circle text-muted" title="${frappe.utils.escape_html(r.error_message)}"></i>`;
                    }
                    
                    let remove_btn = (r.status === 'Queued' && !d.job_started) 
                        ? `<button class="btn btn-xs btn-danger btn-remove-recipient" data-id="${r.id}">&times;</button>`
                        : '';

                    return `<tr id="be-row-${r.id}" style="border-bottom: 1px solid #dfdff0;">
                        <td style="padding: 8px;">${start + i + 1}</td>
                        <td style="padding: 8px;">${frappe.utils.escape_html(r.applicant_name)} &lt;${frappe.utils.escape_html(r.email)}&gt;</td>
                        <td style="padding: 8px;" class="be-status">${status_html}</td>
                        <td style="padding: 8px; text-align: center;">${remove_btn}</td>
                    </tr>`;
                }).join('');

                let html = `
                <div style="margin-bottom: 15px;"><strong>${__('Selected Recipients')} (${total})</strong></div>
                <div style="border: 1px solid #dfdff0; border-radius: 4px; margin-bottom: 10px;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 12px;">
                        <thead style="background-color: #f8f8f8; box-shadow: 0 1px 0 #dfdff0;">
                            <tr>
                                <th style="padding: 8px; width: 50px;">No.</th>
                                <th style="padding: 8px;">Recipient</th>
                                <th style="padding: 8px; width: 120px;">Status</th>
                                <th style="padding: 8px; width: 60px; text-align: center;">Remove</th>
                            </tr>
                        </thead>
                        <tbody>${rows || '<tr><td colspan="4" style="padding: 8px; text-align: center;">No recipients</td></tr>'}</tbody>
                    </table>
                </div>
                <div class="list-paging-area" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0;">
                    <div>
                        <button class="btn btn-default btn-sm btn-prev" ${page === 0 || total === 0 ? 'disabled' : ''}>&lsaquo; Prev</button>
                        <button class="btn btn-default btn-sm btn-next" ${page >= total_pages - 1 || total === 0 ? 'disabled' : ''}>Next &rsaquo;</button>
                    </div>
                    <div class="text-muted text-medium">
                        Showing ${total === 0 ? 0 : start + 1}–${end} of ${total}
                    </div>
                </div>`;

                d.fields_dict.recipients_html.$wrapper.html(html);

                d.fields_dict.recipients_html.$wrapper.find('.btn-remove-recipient').on('click', function() {
                    let id = $(this).data('id');
                    let rec = d.recipient_data.find(r => r.id === id);
                    if (rec) {
                        rec.removed = true;
                        let new_active = d.recipient_data.filter(r => !r.removed);
                        let new_total_pages = Math.ceil(new_active.length / page_size);
                        if (d.current_page >= new_total_pages && d.current_page > 0) {
                            d.current_page--;
                        }
                        d.render_recipient_page(d.current_page);
                    }
                });

                d.fields_dict.recipients_html.$wrapper.find('.btn-prev').on('click', () => d.render_recipient_page(d.current_page - 1));
                d.fields_dict.recipients_html.$wrapper.find('.btn-next').on('click', () => d.render_recipient_page(d.current_page + 1));
            };

            d.show();
            d.render_recipient_page(0);

            // Listen for realtime row updates and update the dialog's data structure
            frappe.realtime.on("bulk_email_row_update", function(data) {
                // If this dialog is closed/hidden, don't update
                if (!d.$wrapper.is(':visible')) return;

                let rec = d.recipient_data.find(r => r.id === data.recipient_reference);
                if (rec) {
                    rec.status = data.status;
                    if (data.error_message) rec.error_message = data.error_message;

                    // If it is on the current page, update the DOM directly to avoid flicker
                    let active = d.recipient_data.filter(r => !r.removed);
                    let start = d.current_page * page_size;
                    let end = start + page_size;
                    let slice = active.slice(start, end);
                    
                    if (slice.find(r => r.id === rec.id)) {
                        let color = rec.status === 'Sent' ? 'green' : (rec.status === 'Failed' ? 'red' : (rec.status === 'Sending' ? 'blue' : 'orange'));
                        let status_html = `<span class="indicator-pill ${color}">${rec.status}</span>`;
                        if (rec.error_message) {
                            status_html += ` <i class="fa fa-info-circle text-muted" title="${frappe.utils.escape_html(rec.error_message)}"></i>`;
                        }
                        $(`#be-row-${rec.id} .be-status`).html(status_html);
                    }
                }
            });
        }
    });
};

slcm.show_bulk_email_progress = function (bulk_email_name, recipients_data) {
    let progress_html = `<div style="text-align: center; padding: 20px;">
        <div class="progress" style="height: 20px; margin-bottom: 10px;">
            <div class="progress-bar progress-bar-success" role="progressbar" style="width: 0%;" id="be-progress-bar"></div>
        </div>
        <p id="be-progress-text">Sending Emails...</p>
    </div>`;

    if (recipients_data && recipients_data.length) {
        // Obsolete: Dialog now manages its own table in d.render_recipient_page
    }

    let progress_dialog = new frappe.ui.Dialog({
        title: __('Sending Bulk Emails'),
        fields: [
            {
                fieldname: 'progress_html',
                fieldtype: 'HTML',
                options: progress_html
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
    frappe.realtime.on("bulk_email_row_update", function(data) {
        if (data.bulk_email !== bulk_email_name) return;

        if (recipients_data && recipients_data.length) {
            // Obsolete: Dialog handles its own updates, see above
        }
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
