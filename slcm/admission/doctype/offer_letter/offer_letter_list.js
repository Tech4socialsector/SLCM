frappe.listview_settings['Offer Letter'] = {
    add_fields: ["offer_status", "payable_amount"],
    get_indicator: function (doc) {
        if (doc.offer_status === "Payment Completed") {
            return [__("Paid"), "blue", "offer_status,=,Payment Completed"];
        } else if (doc.offer_status === "Accepted") {
            return [__("Accepted"), "green", "offer_status,=,Accepted"];
        }
    },
    refresh: function (listview) {
        // standalone button out of Actions dropdown
        listview.page.add_inner_button(__("Send Reminder"), function () {
            frappe.call({
                method: "slcm.api.service.offer_service.get_pending_offers_list",
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        slcm.utils.show_offer_reminder_dialog(r.message);
                    } else {
                        frappe.msgprint(__("No pending 'Issued' offers found before deadline."));
                    }
                }
            });
        });

        listview.page.add_inner_button(__("Bulk Download ZIP"), function () {
            let dialog = new frappe.ui.Dialog({
                title: __('Bulk Download Offer Letters'),
                fields: [
                    {
                        label: __('Campus'),
                        fieldname: 'campus',
                        fieldtype: 'Link',
                        options: 'Campus'
                    },
                    {
                        label: __('Programme'),
                        fieldname: 'program',
                        fieldtype: 'Link',
                        options: 'Program'
                    },
                    {
                        label: __('Admission Cycle'),
                        fieldname: 'admission_cycle',
                        fieldtype: 'Link',
                        options: 'Admission Cycle'
                    },
                    {
                        label: __('Academic Year'),
                        fieldname: 'academic_year',
                        fieldtype: 'Link',
                        options: 'Academic Year'
                    },
                    {
                        label: __('Admission Year'),
                        fieldname: 'admission_year',
                        fieldtype: 'Link',
                        options: 'Admission Year'
                    },
                    {
                        label: __('Offer Status'),
                        fieldname: 'offer_status',
                        fieldtype: 'Select',
                        options: '\nDraft\nIssued\nAccepted\nPayment Completed\nRejected\nExpired\nWithdrawn'
                    }
                ],
                primary_action_label: __('Download'),
                primary_action: function (values) {
                    dialog.hide();
                    frappe.call({
                        method: 'slcm.admission.doctype.offer_letter.offer_letter.get_bulk_offers_zip',
                        args: {
                            filters: values
                        },
                        callback: function (r) {
                            if (r.message) {
                                if (typeof r.message === 'string') {
                                    // Sync response (URL)
                                    let file_url = r.message;
                                    let w = window.open(file_url, '_blank');
                                    if (!w) {
                                        frappe.msgprint(__('Please allow popups to download the file.'));
                                    }
                                } else if (r.message.status === 'enqueued') {
                                    frappe.msgprint({
                                        title: __('Background Job Started'),
                                        message: r.message.message,
                                        indicator: 'blue'
                                    });
                                }
                            }
                        }
                    });
                }
            });
            dialog.show();
        });
        
    },
    onload: function (listview) {
        // Listen for bulk download progress
        frappe.realtime.on('bulk_offer_download_progress', (data) => {
            frappe.show_progress(data.title, data.progress[0], 100, data.description);
        });

        // AUTO-DOWNLOAD ON COMPLETION
        frappe.realtime.on("bulk_download_complete", (data) => {
            if (data.doctype === "Offer Letter") {
                frappe.hide_progress();
                if (data.file_url) {
                    window.open(data.file_url);
                }
            }
        });

        listview.page.add_action_item(__("Pay Fees (Online)"), function () {
            const selected = listview.get_checked_items();
            if (selected.length !== 1) {
                frappe.msgprint(__("Please select exactly one offer to pay."));
                return;
            }
            const offer = selected[0];
            if (offer.offer_status === "Payment Completed") {
                frappe.msgprint(__("Payment already completed for this offer."));
                return;
            }

            frappe.dom.freeze(__('Redirecting...'));
            frappe.call({
                method: "slcm.api.service.offer_service.get_online_payment_url",
                args: {
                    offer_name: offer.name
                },
                callback: function (r) {
                    frappe.dom.unfreeze();
                    if (r.message) {
                        window.location.href = r.message;
                    }
                }
            });
        });
    }
};

// Global helper for CRM-style offer reminders
frappe.provide('slcm.utils');
slcm.utils.show_offer_reminder_dialog = function (offers) {
    let current_page = 1;
    let page_size = 10;
    let total_pages = Math.ceil(offers.length / page_size);
    // Track selection globally across pages
    let selected_ids = new Set(offers.map(o => o.name));

    function render_table_page(dialog, page) {
        let start = (page - 1) * page_size;
        let end = start + page_size;
        let page_items = offers.slice(start, end);

        const $tbody = dialog.$wrapper.find('#reminder-table-body');
        $tbody.empty();

        page_items.forEach((o) => {
            const is_checked = selected_ids.has(o.name) ? 'checked' : '';
            $tbody.append(`
                <tr data-name="${o.name}">
                    <td style="width: 40px; text-align: center;">
                        <input type="checkbox" class="reminder-chk" data-name="${o.name}" ${is_checked}>
                    </td>
                    <td><b>${o.applicant_name}</b><br><small class="text-muted">${o.name}</small></td>
                    <td>${o.program}</td>
                    <td>${o.payment_deadline ? moment(o.payment_deadline).format("DD-MM-YYYY") : '-'}</td>
                </tr>
            `);
        });

        dialog.$wrapper.find('#current-page-info').text(`Page ${page} of ${total_pages} (${offers.length} total)`);

        // Disable/Enable buttons
        dialog.$wrapper.find('#prev-page-btn').prop('disabled', page === 1);
        dialog.$wrapper.find('#next-page-btn').prop('disabled', page === total_pages);

        // Update "Select All" checkbox state based on current page selection
        const all_page_selected = page_items.every(item => selected_ids.has(item.name));
        dialog.$wrapper.find('#reminder-select-all').prop('checked', all_page_selected);
    }

    let dialog = new frappe.ui.Dialog({
        title: __('Send Offer Reminders'),
        size: 'large',
        fields: [
            {
                fieldname: 'applicants_table_html',
                fieldtype: 'HTML',
                options: `
                    <div style="margin-bottom: 15px;">
                        <label style="font-weight: 600; display: block; margin-bottom: 8px;">${__('Select Target Applicants')}</label>
                        <div style="border: 1px solid #d1d8dd; border-radius: 4px;">
                            <table class="table table-bordered table-hover" style="margin: 0; background: #fff;">
                                <thead style="background: #f8f9fa;">
                                    <tr>
                                        <th style="width: 40px; text-align: center;">
                                            <input type="checkbox" id="reminder-select-all" checked>
                                        </th>
                                        <th>${__('Applicant')}</th>
                                        <th>${__('Program')}</th>
                                        <th>${__('Deadline')}</th>
                                    </tr>
                                </thead>
                                <tbody id="reminder-table-body">
                                </tbody>
                            </table>
                            <div style="padding: 10px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #d1d8dd; background: #fdfdfd;">
                                <div id="current-page-info" style="font-size: 12px; color: #666;"></div>
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span id="selection-summary" style="font-size: 11px; font-weight: bold; color: var(--primary-color);"></span>
                                    <button class="btn btn-xs btn-default" id="prev-page-btn">${__('Prev')}</button>
                                    <button class="btn btn-xs btn-default" id="next-page-btn">${__('Next')}</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `
            },
            {
                fieldname: 'message_section',
                fieldtype: 'Section Break',
                label: __('Message Content')
            },
            {
                label: __('Email Template'),
                fieldname: 'email_template',
                fieldtype: 'Link',
                options: 'Email Templates',
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            template_for_offer_letter: 1
                        }
                    };
                }
            },
            {
                label: __('Sender Email Account'),
                fieldname: 'sender_email',
                fieldtype: 'Link',
                options: 'Email Account',
                description: __('If blank, system default account will be used.')
            },
            {
                fieldname: 'channels_section',
                fieldtype: 'Section Break',
                label: __('Channels')
            },
            {
                fieldname: 'column_1',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'send_email',
                fieldtype: 'Check',
                label: __('Send Email'),
                default: 1
            },
            {
                fieldname: 'column_2',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'send_notification',
                fieldtype: 'Check',
                label: __('Send System Notification'),
                default: 1
            }
        ],
        primary_action_label: __('Send Reminders'),
        primary_action(values) {
            const final_selection = Array.from(selected_ids);

            if (final_selection.length === 0) {
                frappe.msgprint(__('Please select at least one applicant.'));
                return;
            }

            frappe.call({
                method: "slcm.api.service.offer_service.send_bulk_reminders",
                args: {
                    offer_names: final_selection,
                    email_template: values.email_template,
                    send_email: values.send_email,
                    send_notification: values.send_notification,
                    sender_email: values.sender_email
                },
                callback: function (r) {
                    if (r.message && r.message.status === "success") {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        });
                        dialog.hide();
                    }
                }
            });
        }
    });

    const update_selection_summary = () => {
        dialog.$wrapper.find('#selection-summary').text(`${selected_ids.size} selected`);
    };

    // Initial render
    render_table_page(dialog, current_page);
    update_selection_summary();

    // Event Listeners for pagination
    dialog.$wrapper.find('#prev-page-btn').on('click', () => {
        if (current_page > 1) {
            current_page--;
            render_table_page(dialog, current_page);
        }
    });

    dialog.$wrapper.find('#next-page-btn').on('click', () => {
        if (current_page < total_pages) {
            current_page++;
            render_table_page(dialog, current_page);
        }
    });

    // Handle individual checkbox change
    dialog.$wrapper.on('change', '.reminder-chk', function () {
        const id = $(this).attr('data-name');
        if ($(this).prop('checked')) {
            selected_ids.add(id);
        } else {
            selected_ids.delete(id);
        }
        update_selection_summary();

        // Update "Select All" state
        const start = (current_page - 1) * page_size;
        const page_items = offers.slice(start, start + page_size);
        const all_page_selected = page_items.every(item => selected_ids.has(item.name));
        dialog.$wrapper.find('#reminder-select-all').prop('checked', all_page_selected);
    });

    // Handle select all (for current page)
    dialog.$wrapper.find('#reminder-select-all').on('change', function () {
        const checked = $(this).prop('checked');
        const start = (current_page - 1) * page_size;
        const page_items = offers.slice(start, start + page_size);

        page_items.forEach(item => {
            if (checked) {
                selected_ids.add(item.name);
            } else {
                selected_ids.delete(item.name);
            }
        });

        dialog.$wrapper.find('.reminder-chk').prop('checked', checked);
        update_selection_summary();
    });

    dialog.show();
};
