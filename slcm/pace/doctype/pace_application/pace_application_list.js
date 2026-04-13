frappe.listview_settings['PACE Application'] = {
    onload: function(listview) {
        // Add Bulk Assign to the 'Actions' menu
        listview.page.add_actions_menu_item(__('Bulk Assign Verifiers'), function() {
            const selected_items = listview.get_checked_items();
            const names = selected_items.map(item => item.name);
            
            if (names.length === 0) {
                frappe.msgprint(__('Please select at least one application to assign.'));
                return;
            }

            let d = new frappe.ui.Dialog({
                title: __('Assign Verifier & Start Verification'),
                fields: [
                    {
                        label: __('Target Verifier'),
                        fieldname: 'verifier',
                        fieldtype: 'Link',
                        options: 'User',
                        reqd: 1,
                        get_query: () => ({ query: "slcm.pace.api.get_verifiers" })
                    },
                    {
                        fieldtype: 'HTML',
                        fieldname: 'info',
                        options: `<div class="text-muted small">${__('This will assign {0} selected applications and generate their Document Verification records.', [names.length])}</div>`
                    }
                ],
                primary_action_label: __('Assign & Process'),
                primary_action(values) {
                    frappe.call({
                        method: 'slcm.pace.api.bulk_assign_applications',
                        args: {
                            verifier: values.verifier,
                            app_names: names
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({
                                    message: __('{0} applications assigned to {1}', [r.message.assigned_count, values.verifier]),
                                    indicator: 'green'
                                });
                                d.hide();
                                listview.refresh();
                            }
                        }
                    });
                }
            });
            d.show();
        });

        // Advanced Bulk Assign (Inner Button) for mass selection
        listview.page.add_inner_button(__('Unassigned Only'), function() {
            listview.filter_area.clear();
            listview.filter_area.add('PACE Application', 'status', '=', 'Submitted');
            listview.filter_area.add('PACE Application', 'assigned_verifier', 'is', 'not set');
            listview.refresh();
        });

        listview.page.add_inner_button(__('Advanced Bulk Assign'), function() {
            const dialog = new frappe.ui.Dialog({
                title: __('Advanced Assignment Dashboard'),
                size: 'large',
                fields: [
                    {
                        label: __('Target Verifier'),
                        fieldname: 'verifier',
                        fieldtype: 'Link',
                        options: 'User',
                        reqd: 1,
                        get_query: () => ({ query: "slcm.pace.api.get_verifiers" })
                    },
                    {
                        label: __('Auto-select (First N)'),
                        fieldname: 'count',
                        fieldtype: 'Int',
                        description: __('Enter count to automatically select first N unassigned applications')
                    },
                    {
                        fieldtype: 'Section Break',
                        label: __('Manual Selection (Unassigned)')
                    },
                    {
                        fieldname: 'selection_list',
                        fieldtype: 'HTML'
                    }
                ],
                primary_action_label: __('Assign Selected'),
                primary_action(values) {
                    const selected = [];
                    dialog.$wrapper.find('.doc-checkbox:checked').each(function() {
                        selected.push($(this).data('name'));
                    });

                    if (selected.length === 0 && !values.count) {
                        frappe.msgprint(__('Please select at least one application or enter an auto-select count.'));
                        return;
                    }

                    frappe.call({
                        method: 'slcm.pace.api.bulk_assign_applications',
                        args: {
                            verifier: values.verifier,
                            count: values.count || 0,
                            filters: listview.filter_area.get(),
                            app_names: selected
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({
                                    message: __('{0} applications assigned and verification created.', [r.message.assigned_count]),
                                    indicator: 'green'
                                });
                                dialog.hide();
                                listview.refresh();
                            }
                        }
                    });
                }
            });

            // Auto-select logic
            dialog.fields_dict.count.$input.on('change keyup', function() {
                const count = parseInt($(this).val()) || 0;
                dialog.$wrapper.find('.doc-checkbox').prop('checked', false);
                dialog.$wrapper.find('.doc-checkbox').slice(0, count).prop('checked', true);
            });

            // Fetch unassigned applications
            frappe.call({
                method: 'slcm.pace.api.get_unassigned_applications',
                args: {
                    filters: listview.filter_area.get(),
                    limit: 100
                },
                callback: function(r) {
                    const docs = r.message || [];
                    let html = `
                        <div style="border: 1px solid #d1d8dd; border-radius: 4px; max-height: 300px; overflow-y: auto;">
                            <table class="table table-bordered table-hover" style="margin-bottom: 0; font-size: 12px;">
                                <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 1;">
                                    <tr>
                                        <th style="width: 40px; text-align: center;"><input type="checkbox" id="select-all-apps"></th>
                                        <th>${__('Applicant Name')}</th>
                                        <th>${__('Program')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;

                    if (docs.length === 0) {
                        html += `<tr><td colspan="3" class="text-center text-muted p-4">${__('No unassigned submitted applications found.')}</td></tr>`;
                    } else {
                        docs.forEach(doc => {
                            html += `
                                <tr>
                                    <td style="text-align: center;"><input type="checkbox" class="doc-checkbox" data-name="${doc.name}"></td>
                                    <td style="font-weight: 500;">${doc.applicant_name}</td>
                                    <td class="text-muted">${doc.programme}</td>
                                </tr>
                            `;
                        });
                    }

                    html += `</tbody></table></div>`;
                    dialog.fields_dict.selection_list.$wrapper.html(html);
                    dialog.$wrapper.find('#select-all-apps').on('change', function() {
                        dialog.$wrapper.find('.doc-checkbox').prop('checked', $(this).prop('checked'));
                    });
                }
            });

            dialog.show();
        });

        // Original ZIP Actions
        listview.page.add_actions_menu_item(__('Download All Attachments (ZIP)'), function() {
            const selected_items = listview.get_checked_items();
            if (selected_items.length === 0) {
                frappe.msgprint(__('Please select at least one record to download.'));
                return;
            }
            const names = selected_items.map(item => item.name);
            frappe.show_alert({ message: __('Preparing Attachments...'), indicator: 'blue' });
            frappe.call({
                method: 'slcm.pace.doctype.pace_application.pace_application.bulk_download_attachments',
                args: { names: names },
                freeze: true,
                freeze_message: __('Generating ZIP Archive...'),
                callback: function(r) {
                    if (r.message) {
                        const file_url = r.message;
                        const link = document.createElement('a');
                        link.href = file_url;
                        link.download = file_url.split('/').pop();
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        frappe.show_alert({ message: __('Download started.'), indicator: 'green' });
                    }
                }
            });
        });
    }
};
