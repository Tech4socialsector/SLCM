frappe.listview_settings['PACE Document Verification'] = {
    onload: function (listview) {
        const manager_roles = [
            "Admission Admin",
            "PACE Admission Manager",
            "System Manager",
            "Admission Officer",
            "Document Verification Admin",
            "Admission Manager",
            "PACE Verification Admin",
            "Administrator"
        ];
        const has_manager_role = manager_roles.some(role => frappe.user.has_role(role));

        if (has_manager_role) {
            // Add Bulk Assign to the 'Actions' menu
            listview.page.add_actions_menu_item(__('Bulk Assign Verifiers'), function () {
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
                            get_query: () => ({
                                query: "slcm.pace.api.get_verifiers"
                            })
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
                            callback: function (r) {
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

            // Bulk Auto Re-assign (Round Robin)
            listview.page.add_actions_menu_item(__('Bulk Auto Re-assign (Round Robin)'), function () {
                const selected_items = listview.get_checked_items();
                const names = selected_items.map(item => item.name);

                if (names.length === 0) {
                    frappe.msgprint(__('Please select at least one record.'));
                    return;
                }

                frappe.confirm(__('Are you sure you want to automatically re-assign {0} selected records via Round Robin?', [names.length]), function () {
                    frappe.call({
                        method: 'slcm.pace.assignment_logic.bulk_reassign_verifiers',
                        args: { names: names },
                        callback: function (r) {
                            if (r.message !== undefined) {
                                frappe.show_alert({
                                    message: __('{0} records re-assigned successfully', [r.message]),
                                    indicator: 'green'
                                });
                                listview.refresh();
                            }
                        }
                    });
                });
            });

            // Advanced Bulk Re-assign Dashboard (Inner Button)
            listview.page.add_inner_button(__('Reassign Documents'), function () {
                let selected_names = [];

                let d = new frappe.ui.Dialog({
                    title: __('Reassign Documents'),
                    size: 'large',
                    fields: [
                        {
                            label: __('From Verifier (Optional Filter)'),
                            fieldname: 'from_verifier',
                            fieldtype: 'Link',
                            options: 'User',
                            get_query: () => ({
                                query: "slcm.pace.api.get_verifiers"
                            }),
                            change: function () {
                                // Delay to ensure field value is updated before refresh
                                setTimeout(() => refresh_overdue_table(), 100);
                            }
                        },
                        {
                            label: __('To Verifier (Assign To)'),
                            fieldname: 'to_verifier',
                            fieldtype: 'Link',
                            options: 'User',
                            reqd: 1,
                            get_query: () => ({
                                query: "slcm.pace.api.get_verifiers"
                            })
                        },
                        {
                            fieldtype: 'HTML',
                            fieldname: 'overdue_html'
                        }
                    ],
                    primary_action_label: __('Reassign Selected Tasks'),
                    primary_action(values) {
                        if (selected_names.length === 0) {
                            frappe.msgprint(__('Please select at least one task to transfer.'));
                            return;
                        }

                        frappe.confirm(__('Are you sure you want to transfer {0} selected tasks to {1}?', [selected_names.length, values.to_verifier]), function () {
                            frappe.call({
                                method: 'slcm.pace.assignment_logic.transfer_verifications',
                                args: {
                                    from_verifier: values.from_verifier || '',
                                    to_verifier: values.to_verifier,
                                    names: selected_names
                                },
                                callback: function (r) {
                                    if (r.message !== undefined) {
                                        frappe.show_alert({
                                            message: __('{0} records transferred successfully', [r.message]),
                                            indicator: 'green'
                                        });
                                        d.hide();
                                        listview.refresh();
                                    }
                                }
                            });
                        });
                    }
                });

                function refresh_overdue_table() {
                    const verifier = d.get_value('from_verifier');

                    frappe.call({
                        method: 'slcm.pace.assignment_logic.get_overdue_for_verifier',
                        args: { verifier: verifier || "" },
                        callback: function (r) {
                            const docs = r.message || [];
                            selected_names = []; // Reset on reload

                            let html = `
                            <div style="margin-top: 15px;">
                                <h6 style="color: #d9534f; font-weight: bold;">
                                    ${verifier ? __('Overdue for {0}:', [verifier]) : __('All Overdue Applications:')} 
                                    <span class="badge badge-danger" id="overdue-count-badge" style="margin-left: 5px;">${docs.length}</span>
                                </h6>
                                <div style="border: 1px solid #d1d8dd; border-radius: 4px; max-height: 250px; overflow-y: auto;">
                                    <table class="table table-condensed table-hover" id="overdue-transfer-table" style="margin-bottom: 0; font-size: 13px;">
                                        <thead style="background: #f8f9fa;">
                                            <tr>
                                                <th style="width: 40px; text-align: center;"><input type="checkbox" id="select-all-overdue"></th>
                                                <th>${__('Applicant')}</th>
                                                <th>${__('Application ID')}</th>
                                                <th>${__('Current Verifier')}</th>
                                                <th>${__('Due Date')}</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                        `;

                            if (docs.length === 0) {
                                html += `<tr><td colspan="5" class="text-center text-muted">${__('No overdue records found.')}</td></tr>`;
                            } else {
                                docs.forEach(doc => {
                                    html += `
                                    <tr>
                                        <td style="text-align: center;"><input type="checkbox" class="overdue-checkbox" data-name="${doc.name}"></td>
                                        <td>${doc.applicant_name}</td>
                                        <td>${doc.application}</td>
                                        <td class="text-muted">${doc.assigned_verifier || __('Unassigned')}</td>
                                        <td class="text-danger">${doc.due_date}</td>
                                    </tr>
                                `;
                                });
                            }

                            html += `</tbody></table></div></div>`;
                            d.fields_dict.overdue_html.$wrapper.html(html);

                            // Select All Logic
                            d.$wrapper.find('#select-all-overdue').on('change', function () {
                                const checked = $(this).prop('checked');
                                d.$wrapper.find('.overdue-checkbox').prop('checked', checked).trigger('change');
                            });

                            // Individual Checkbox Logic
                            d.$wrapper.find('.overdue-checkbox').on('change', function () {
                                const name = $(this).data('name');
                                if ($(this).prop('checked')) {
                                    if (!selected_names.includes(name)) selected_names.push(name);
                                } else {
                                    selected_names = selected_names.filter(n => n !== name);
                                    d.$wrapper.find('#select-all-overdue').prop('checked', false);
                                }
                                update_transfer_button_label();
                            });

                            update_transfer_button_label();
                        }
                    });
                }

                function update_transfer_button_label() {
                    const btn_text = selected_names.length > 0
                        ? __('Transfer {0} Selected Tasks', [selected_names.length])
                        : __('Transfer Selected Tasks');
                    d.get_primary_btn().text(btn_text);
                }

                // Load all overdue on open
                refresh_overdue_table();
                d.show();
            });
        }
    }
};
