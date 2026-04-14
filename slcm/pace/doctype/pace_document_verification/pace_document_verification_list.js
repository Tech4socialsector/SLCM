frappe.listview_settings['PACE Document Verification'] = {
    onload: function(listview) {
        // Add Bulk Assign to the 'Actions' menu
        listview.page.add_actions_menu_item(__('Bulk Assign Verifiers'), function() {
            const selected_items = listview.get_checked_items();
            const names = selected_items.map(item => item.name);
            
            if (names.length === 0) {
                frappe.msgprint(__('Please select at least one verification record to assign.'));
                return;
            }

            let d = new frappe.ui.Dialog({
                title: __('Assign Verifier'),
                fields: [
                    {
                        label: __('Target Verifier'),
                        fieldname: 'verifier',
                        fieldtype: 'Link',
                        options: 'User',
                        reqd: 1,
                        get_query: () => ({ filters: { 'enabled': 1 } })
                    },
                    {
                        fieldtype: 'HTML',
                        fieldname: 'info',
                        options: `<div class="text-muted small">${__('This will assign {0} selected verification records to the target verifier.', [names.length])}</div>`
                    }
                ],
                primary_action_label: __('Assign'),
                primary_action(values) {
                    frappe.call({
                        method: 'slcm.pace.api.bulk_assign_verifications',
                        args: {
                            verifier: values.verifier,
                            verification_names: names
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === 'success') {
                                // Custom Top-Center Toast
                                const toast_id = 'assignment-toast-' + frappe.utils.get_random(5);
                                const toast_html = `
                                    <div id="${toast_id}" style="
                                        position: fixed;
                                        top: 20px;
                                        left: 50%;
                                        transform: translateX(-50%);
                                        z-index: 99999;
                                        background: white;
                                        padding: 16px 24px;
                                        border-radius: 12px;
                                        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
                                        border-left: 5px solid #28a745;
                                        min-width: 350px;
                                        animation: slide-down 0.4s ease-out;
                                        text-align: center;
                                    ">
                                        <style>
                                            @keyframes slide-down {
                                                from { top: -100px; opacity: 0; }
                                                to { top: 20px; opacity: 1; }
                                            }
                                            @keyframes fade-out {
                                                from { opacity: 1; }
                                                to { opacity: 0; }
                                            }
                                        </style>
                                        <div style="display: flex; align-items: center; justify-content: center; gap: 12px;">
                                            <i class="fa fa-check-circle" style="font-size: 24px; color: #28a745;"></i>
                                            <div style="text-align: left;">
                                                <div style="font-weight: bold; color: #1a1a1a; font-size: 15px;">Assignment Successful</div>
                                                <div style="font-size: 13px; color: #666; margin-top: 2px;">
                                                    <b>${r.message.assigned_count}</b> Students assigned to <span style="color: #007bff; font-weight: 600;">${values.verifier}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                `;
                                
                                $('body').append(toast_html);
                                
                                // Auto-remove after 4 seconds
                                setTimeout(() => {
                                    $(`#${toast_id}`).css('animation', 'fade-out 0.5s forwards');
                                    setTimeout(() => $(`#${toast_id}`).remove(), 500);
                                }, 4000);

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
        listview.page.add_inner_button(__('Unassigned Docs'), function() {
            listview.filter_area.clear();
            listview.filter_area.add('PACE Document Verification', 'assigned_verifier', 'is', 'not set');
            listview.filter_area.add('PACE Document Verification', 'overall_status', '=', 'Pending');
            listview.refresh();
        });

        listview.page.add_inner_button(__('Assign Documents'), function() {
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
                        get_query: () => ({ filters: { 'enabled': 1 } })
                    },
                    {
                        label: __('Auto-select (First N)'),
                        fieldname: 'count',
                        fieldtype: 'Int',
                        description: __('Enter count to automatically select first N unassigned records')
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
                        frappe.msgprint(__('Please select at least one record or enter an auto-select count.'));
                        return;
                    }

                    frappe.call({
                        method: 'slcm.pace.api.bulk_assign_verifications',
                        args: {
                            verifier: values.verifier,
                            count: values.count || 0,
                            filters: listview.filter_area.get(),
                            verification_names: selected
                        },
                        callback: function(r) {
                            if (r.message && r.message.status === 'success') {
                                // Custom Top-Center Toast
                                const toast_id = 'adv-assignment-toast-' + frappe.utils.get_random(5);
                                const toast_html = `
                                    <div id="${toast_id}" style="
                                        position: fixed;
                                        top: 20px;
                                        left: 50%;
                                        transform: translateX(-50%);
                                        z-index: 99999;
                                        background: white;
                                        padding: 16px 24px;
                                        border-radius: 12px;
                                        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
                                        border-left: 5px solid #28a745;
                                        min-width: 350px;
                                        animation: slide-down 0.4s ease-out;
                                        text-align: center;
                                    ">
                                        <div style="display: flex; align-items: center; justify-content: center; gap: 12px;">
                                            <i class="fa fa-check-circle" style="font-size: 24px; color: #28a745;"></i>
                                            <div style="text-align: left;">
                                                <div style="font-weight: bold; color: #1a1a1a; font-size: 15px;">Advanced Assignment Successful</div>
                                                <div style="font-size: 13px; color: #666; margin-top: 2px;">
                                                    <b>${r.message.assigned_count}</b> Students assigned to <span style="color: #007bff; font-weight: 600;">${values.verifier}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                `;
                                
                                $('body').append(toast_html);
                                
                                // Auto-remove after 4 seconds
                                setTimeout(() => {
                                    $(`#${toast_id}`).css('animation', 'fade-out 0.5s forwards');
                                    setTimeout(() => $(`#${toast_id}`).remove(), 500);
                                }, 4000);

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

            // Fetch unassigned verifications
            frappe.call({
                method: 'slcm.pace.api.get_unassigned_verifications',
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
                                        <th>${__('Application')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;

                    if (docs.length === 0) {
                        html += `<tr><td colspan="3" class="text-center text-muted p-4">${__('No unassigned verification records found.')}</td></tr>`;
                    } else {
                        docs.forEach(doc => {
                            html += `
                                <tr>
                                    <td style="text-align: center;"><input type="checkbox" class="doc-checkbox" data-name="${doc.name}"></td>
                                    <td style="font-weight: 500;">${doc.applicant_name || ''}</td>
                                    <td class="text-muted">${doc.application || ''}</td>
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
    }
};
