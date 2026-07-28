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

        if (frm.doc.reference_doctype && !frm.doc.__islocal && (frm.doc.status === 'Queued' || frm.doc.status === 'Partial' || frm.doc.status === 'Error')) {
            let last_focused = 'subject';
            frm.fields_dict.subject.$input.on('focus', () => { last_focused = 'subject'; });
            
            setTimeout(() => {
                if (frm.fields_dict.message && frm.fields_dict.message.quill) {
                    frm.fields_dict.message.quill.root.addEventListener('focus', () => { last_focused = 'message'; });
                }
            }, 500);

            frappe.call({
                method: "slcm.slcm.doctype.bulk_email.bulk_email.get_available_fields",
                args: { reference_doctype: frm.doc.reference_doctype },
                callback: function (r) {
                    if (r.message) {
                        let chips_html = r.message.map(f => 
                            `<div class="btn btn-default btn-xs placeholder-chip" data-fieldname="${f.fieldname}" style="margin: 0 5px 5px 0; cursor: pointer;" title="Insert {{ ${f.fieldname} }}">
                                <span>{{ ${f.fieldname} }}</span><br>
                                <small class="text-muted" style="font-size: 10px;">${f.label}</small>
                            </div>`
                        ).join('');
                        
                        let panel_html = `
                            <div style="border: 1px solid #dfdff0; border-radius: 4px; padding: 10px; background-color: #fafbfc; max-height: 150px; overflow-y: auto;">
                                ${chips_html}
                            </div>
                        `;
                        frm.fields_dict.placeholders_html.$wrapper.html(panel_html);

                        frm.fields_dict.placeholders_html.$wrapper.find('.placeholder-chip').on('click', function() {
                            let fieldname = $(this).data('fieldname');
                            let text_to_insert = `{{ ${fieldname} }}`;
                            
                            if (frm.doc.use_html) {
                                last_focused = 'message_html';
                            }

                            if (last_focused === 'subject') {
                                let input = frm.fields_dict.subject.$input.get(0);
                                let start = input.selectionStart;
                                let end = input.selectionEnd;
                                let val = input.value;
                                input.value = val.slice(0, start) + text_to_insert + val.slice(end);
                                input.selectionStart = input.selectionEnd = start + text_to_insert.length;
                                input.focus();
                                frm.set_value('subject', input.value);
                            } else if (last_focused === 'message') {
                                let quill = frm.fields_dict.message.quill;
                                if (quill) {
                                    let range = quill.getSelection(true);
                                    let index = range ? range.index : 0;
                                    quill.insertText(index, text_to_insert);
                                    quill.setSelection(index + text_to_insert.length);
                                }
                            } else if (last_focused === 'message_html') {
                                let cm = frm.fields_dict.message_html.editor;
                                if (cm) {
                                    cm.replaceSelection(text_to_insert);
                                    cm.focus();
                                }
                            }
                        });
                    }
                }
            });
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
