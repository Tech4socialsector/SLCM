frappe.listview_settings['Entrance Test Seat Allocation'] = {
    onload: function(listview) {
        // Add to the 'Actions' menu that appears when records are selected
        listview.page.add_actions_menu_item(__('Bulk Records Download'), function() {
            const selected_items = listview.get_checked_items();
            
            if (selected_items.length === 0) {
                frappe.msgprint(__('Please select at least one record to download.'));
                return;
            }

            const names = selected_items.map(item => item.name);
            
            // Show a progress indicator for bulk generation
            frappe.show_alert({
                message: __('Preparing Records...'),
                indicator: 'blue'
            });

            frappe.call({
                method: 'slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.bulk_download_all_records',
                args: {
                    names: names
                },
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
                        
                        frappe.show_alert({
                            message: __('Download started successfully.'),
                            indicator: 'green'
                        });
                    }
                }
            });
        });
    },
    refresh: function (listview) {
        // Hide "Update Rank" and "Reschedule" only for users with the "Applicant" role
        // and who are NOT Administrators/System Managers (to ensure admins always have access)
        const is_applicant = frappe.user_roles.includes("Applicant");
        const is_admin = frappe.user_roles.includes("Administrator") || frappe.user_roles.includes("System Manager");

        if (!is_applicant || is_admin) {
            // Update Rank button (only once)
            if (!listview.page.wrapper.find('.btn-update-rank').length) {
                const ubtn = listview.page.add_inner_button(__("Update Rank"), function () {
                    let d = new frappe.ui.Dialog({
                        title: __("Update Rank"),
                        fields: [
                            {
                                label: __("Academic Year"),
                                fieldname: "academic_year",
                                fieldtype: "Link",
                                options: "Academic Year",
                                reqd: 1
                            },
                            {
                                label: __("Admission Cycle"),
                                fieldname: "admission_cycle",
                                fieldtype: "Link",
                                options: "Admission Cycle",
                                reqd: 1
                            },
                            {
                                label: __("Program Level"),
                                fieldname: "program_level",
                                fieldtype: "Select",
                                options: "Undergraduate\nPostgraduate\nResearch Course",
                                reqd: 1
                            },
                            {
                                label: __("Programme"),
                                fieldname: "program",
                                fieldtype: "Link",
                                options: "Programme",
                                depends_on: "eval:doc.program_level"
                            },
                            {
                                label: __("Entrance Test List"),
                                fieldname: "entrance_test_list",
                                fieldtype: "Link",
                                options: "Entrance Test List",
                                description: __("Optional - limit ranks to this specific entrance test event")
                            }
                        ],
                        primary_action_label: __("Generate"),
                        primary_action(values) {
                            // Hide dialog immediately to show progress bar clearly
                            d.hide();

                            frappe.call({
                                method: "slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.update_ranks_by_category",
                                args: values,
                                callback: function (r) {
                                    if (!r.exc) {
                                        // Show toast at the top center
                                        frappe.msgprint({
                                            message: __("Rank updated successfully for {0} applicants.", [r.message]),
                                            indicator: 'green',
                                            alert: true
                                        });
                                        listview.refresh();
                                    }
                                }
                            });
                        }
                    });
                    d.set_query("admission_cycle", function () {
                        return {
                            filters: {
                                "status": "Active"
                            }
                        };
                    });
                    d.set_query("program", function () {
                        return {
                            query: "slcm.admission.doctype.entrance_test_generation.entrance_test_generation.get_program_query",
                            filters: {
                                "program_level": d.get_value("program_level"),
                                "admission_cycle": d.get_value("admission_cycle")
                            }
                        };
                    });
                    d.fields_dict.program_level.df.on_change = () => {
                        d.set_value("program", "");
                    };
                    d.show();
                });
                ubtn.addClass('btn-update-rank');
            }

            // Reschedule button (also only once)
            if (!listview.page.wrapper.find('.btn-reschedule').length) {
                const rbtn = listview.page.add_button(__('Reschedule'), function () {
                    open_reschedule_dialog(listview);
                }, 'btn-primary');
                rbtn.addClass('btn-reschedule');
            }
        }
    }
};

// ──────────────────────────────────────────────────────────────────────────────
//  open_reschedule_dialog
//  Pre-fetches all active providers FIRST (same pattern as entrance_test_list.js),
//  then builds and shows the dialog with providers already embedded.
// ──────────────────────────────────────────────────────────────────────────────
function open_reschedule_dialog(listview) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Entrance Test Provider',
            filters: { 
                active: 1,
                available_capacity: [">", 0]
            },
            fields: ['name', 'center_name', 'center_address', 'campus', 'provider_type'],
            limit_page_length: 200
        },
        callback: function (r) {
            const all_providers = r.message || [];
            if (!all_providers.length) {
                frappe.msgprint({
                    title: __('No Available Providers'),
                    message: __('No active Entrance Test Providers with available seats found in the system.'),
                    indicator: 'orange'
                });
                return;
            }
            _show_reschedule_dialog(listview, all_providers);
        }
    });
}

// Build provider checkboxes HTML (same style as entrance_test_list.js)
function _build_provider_html(providers) {
    if (!providers.length) {
        return '<p class="text-muted" style="padding:10px 0;">No providers match the selected campus.</p>';
    }
    const items = providers.map(p => `
        <label style="display:flex; align-items:flex-start; gap:8px; padding:8px 12px;
                       border:1px solid #d1d8dd; border-radius:4px; cursor:pointer;
                       margin-bottom:6px; background:#fff; transition:background 0.15s;
                       flex: 1 1 calc(50% - 6px);">
            <input type="checkbox" class="provider-checkbox"
                   data-name="${p.name}"
                   data-campus="${p.campus || ''}"
                   style="width:16px; height:16px; cursor:pointer; margin-top:3px; flex-shrink:0;">
            <span>
                <b>${p.center_name || p.name}</b>
                <span style="color:#6c757d; font-size:11px; margin-left:6px;">(${p.name})</span>
                ${p.center_address ? `<br><small style="color:#888;">${p.center_address}</small>` : ''}
                ${p.campus ? `<br><small style="color:#aaa;">Campus: ${p.campus}</small>` : ''}
            </span>
        </label>
    `).join('');

    return `
        <div id="provider-sel-count" style="font-size:12px; color:#6c757d; margin-bottom:8px;">
            0 provider(s) selected
        </div>
        <div id="provider-list" style="display:flex; flex-wrap:wrap; gap:6px; max-height:190px; overflow-y:auto; padding:2px;">
            ${items}
        </div>
    `;
}

function _show_reschedule_dialog(listview, all_providers) {
    let d = new frappe.ui.Dialog({
        title: __('Reschedule Entrance Test'),
        size: 'extra-large',
        fields: [
            // ── Filters (horizontal 4-column) ─────────────────────────────────
            { fieldtype: 'Section Break', label: __('Filters') },
            {
                label: __('Program Level'),
                fieldname: 'program_level',
                fieldtype: 'Select',
                options: 'Undergraduate\nPostgraduate\nResearch Course',
                on_change: () => fetch_absent_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Academic Year'),
                fieldname: 'academic_year',
                fieldtype: 'Link',
                options: 'Academic Year',
                on_change: () => fetch_absent_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Campus'),
                fieldname: 'campus',
                fieldtype: 'Link',
                options: 'Campus',
                on_change: () => {
                    fetch_absent_applicants(d);
                    _filter_providers_by_campus(d, all_providers);
                }
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Admission Cycle'),
                fieldname: 'admission_cycle',
                fieldtype: 'Link',
                options: 'Admission Cycle',
                on_change: () => fetch_absent_applicants(d)
            },

            // ── Providers (pre-built HTML) ─────────────────────────────────────
            {
                fieldtype: 'Section Break',
                label: __('Select Entrance Test Providers (Preferences)')
            },
            {
                fieldtype: 'HTML',
                fieldname: 'providers_html',
                options: _build_provider_html(all_providers)
            },

            // ── Settings ──────────────────────────────────────────────────────
            { fieldtype: 'Section Break', label: __('Reschedule Settings') },
            {
                label: __('New Allocation Date'),
                fieldname: 'allocation_date',
                fieldtype: 'Datetime',
                reqd: 1,
                description: __('Must be today or a future date/time')
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Auto-select (Enter Number)'),
                fieldname: 'auto_select_count',
                fieldtype: 'Int',
                description: __('Auto-select first N absent applicants')
            },
            {
                label: __("Entrance Test Name"),
                fieldname: "re_entrance_test_name",
                fieldtype: "Link",
                options: "Entrance Test",
                reqd: 1
            },
            { fieldtype: 'Section Break' },
            {
                label: __('Reason for Reschedule'),
                fieldname: 'reschedule_reason',
                fieldtype: 'Small Text',
                reqd: 1,
                description: __('This reason will be included in the email sent to applicants')
            },

            // ── Applicants table ───────────────────────────────────────────────
            { fieldtype: 'Section Break', label: __('Select Absent Applicants') },
            {
                fieldtype: 'HTML',
                fieldname: 'applicants_html'
            }
        ],
        primary_action_label: __('Reschedule'),
        primary_action(values) {
            const selected_applicants = [];
            d.$wrapper.find('.applicant-checkbox:checked').each(function () {
                selected_applicants.push($(this).data('name'));
            });
            const selected_providers = [];
            d.$wrapper.find('.provider-checkbox:checked').each(function () {
                selected_providers.push($(this).data('name'));
            });

            if (!selected_applicants.length) {
                frappe.msgprint(__('Please select at least one applicant.'));
                return;
            }
            if (!selected_providers.length) {
                frappe.msgprint(__('Please select at least one provider.'));
                return;
            }

            frappe.call({
                method: 'slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.reschedule_applicants',
                args: {
                    applicants: selected_applicants,
                    providers: selected_providers,
                    allocation_date: values.allocation_date,
                    reschedule_reason: values.reschedule_reason,
                    re_entrance_test_name: values.re_entrance_test_name
                },
                freeze: true,
                freeze_message: __('Rescheduling Applicants...'),
                callback: function (r) {
                    if (!r.exc) {
                        d.hide();
                        listview.refresh();
                        frappe.show_alert({
                            message: __('Successfully rescheduled {0} applicants.', [selected_applicants.length]),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    });

    d.show();

    d.set_query("admission_cycle", function () {
        return {
            filters: {
                "status": "Active"
            }
        };
    });

    // Set query for re_entrance_test_name with correct filtering
    d.set_query("re_entrance_test_name", () => {
        const campus = d.get_value("campus");
        const academic_year = d.get_value("academic_year");
        const admission_cycle = d.get_value("admission_cycle");
        return {
            filters: [
                ["Entrance Test", "campus", "=", campus],
                ["Entrance Test", "academic_year", "=", academic_year],
                ["Entrance Test", "admission_cycle", "=", admission_cycle],
                ["Entrance Test", "is_active", "=", 1]
            ]
        };
    });

    // ── Provider checkbox count (event delegation on wrapper) ──────────────────
    d.$wrapper.on('change', '.provider-checkbox', function () {
        const n = d.$wrapper.find('.provider-checkbox:checked').length;
        d.$wrapper.find('#provider-sel-count').text(`${n} provider(s) selected`);
    });

    // ── Min-date restriction: block past dates on New Allocation Date ──────────
    setTimeout(() => {
        const $input = d.fields_dict.allocation_date.$input;
        // Frappe wraps the datetime input — try to get flatpickr instance
        const fp = $input[0]._flatpickr;
        if (fp) {
            fp.set('minDate', new Date());
        } else {
            // Fallback: set min attribute on the raw input
            const now = frappe.datetime.get_datetime_as_string(new Date());
            $input.attr('min', now);
        }
    }, 400);

    // Also validate on change in case the user types a date manually
    d.fields_dict.allocation_date.$input.on('change blur', function () {
        const val = d.get_value('allocation_date');
        if (val && frappe.datetime.str_to_obj(val) < new Date()) {
            frappe.show_alert({ message: __('New Allocation Date must be today or in the future.'), indicator: 'red' });
            d.set_value('allocation_date', null);
        }
    });

    // ── Auto-select logic ──────────────────────────────────────────────────────
    d.fields_dict.auto_select_count.$input.on('input', function () {
        const val = parseInt($(this).val()) || 0;
        d.$wrapper.find('.applicant-checkbox').prop('checked', false);
        d.$wrapper.find('.applicant-checkbox').slice(0, val).prop('checked', true);
        update_selected_count(d);
    });

    // ── Initial applicant fetch ────────────────────────────────────────────────
    fetch_absent_applicants(d);
}

// Re-render provider list filtered by campus (no extra API call needed)
function _filter_providers_by_campus(d, all_providers) {
    const campus = d.get_value('campus');
    const filtered = campus ? all_providers.filter(p => p.campus === campus) : all_providers;
    d.get_field('providers_html').$wrapper.html(_build_provider_html(filtered));
    d.$wrapper.off('change.prov').on('change.prov', '.provider-checkbox', function () {
        const n = d.$wrapper.find('.provider-checkbox:checked').length;
        d.$wrapper.find('#provider-sel-count').text(`${n} provider(s) selected`);
    });
}

// ──────────────────────────────────────────────────────────────────────────────
//  fetch_absent_applicants
// ──────────────────────────────────────────────────────────────────────────────
function fetch_absent_applicants(d) {
    const filters = {
        entrance_test_status: 'Absent',
        is_rescheduled: 0
    };

    if (d.get_value('program_level')) filters.program_level = d.get_value('program_level');
    if (d.get_value('academic_year')) filters.academic_year = d.get_value('academic_year');
    if (d.get_value('campus')) filters.campus = d.get_value('campus');
    if (d.get_value('admission_cycle')) filters.admission_cycle = d.get_value('admission_cycle');

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Entrance Test Seat Allocation',
            filters: filters,
            fields: ['name', 'candidate_name', 'applicant', 'program'],
            limit_page_length: 50
        },
        callback: function (r) {
            const applicants = r.message || [];
            let html = `
                <div style="margin-bottom:10px; display:flex; gap:12px; align-items:center;">
                    <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center;">
                        <input type="checkbox" id="select-all-applicants">
                        <span style="margin-left:8px;">Select All</span>
                    </label>
                    <span id="selected-count" style="color:#6c757d; font-size:12px;">0 of ${applicants.length} selected</span>
                </div>
                <div style="max-height:250px; overflow-y:auto; border:1px solid #d1d8dd; border-radius:4px;">
                    <table class="table table-bordered table-hover" style="margin:0; font-size:13px;">
                        <thead style="position:sticky; top:0; background:#f4f5f6; z-index:1;">
                            <tr>
                                <th style="width:40px;"></th>
                                <th>Candidate Name</th>
                                <th>Applicant ID</th>
                                <th>Program</th>
                            </tr>
                        </thead>
                        <tbody>`;

            if (applicants.length) {
                applicants.forEach(app => {
                    html += `
                        <tr>
                            <td style="text-align:center;">
                                <input type="checkbox" class="applicant-checkbox" data-name="${app.name}">
                            </td>
                            <td><b>${app.candidate_name || '-'}</b></td>
                            <td>${app.applicant || '-'}</td>
                            <td>${app.program || '-'}</td>
                        </tr>`;
                });
            } else {
                html += '<tr><td colspan="5" style="text-align:center; color:#aab;">No absent applicants found.</td></tr>';
            }

            html += '</tbody></table></div>';
            d.get_field('applicants_html').$wrapper.html(html);

            // Select All
            d.$wrapper.find('#select-all-applicants').on('change', function () {
                d.$wrapper.find('.applicant-checkbox').prop('checked', this.checked);
                update_selected_count(d, applicants.length);
            });

            // Individual
            d.$wrapper.on('change', '.applicant-checkbox', function () {
                update_selected_count(d, applicants.length);
            });

            update_selected_count(d, applicants.length);
        }
    });
}

function update_selected_count(d, total) {
    const n = d.$wrapper.find('.applicant-checkbox:checked').length;
    const t = total !== undefined ? total : d.$wrapper.find('.applicant-checkbox').length;
    d.$wrapper.find('#selected-count').text(`${n} of ${t} selected`);
    d.$wrapper.find('#select-all-applicants').prop('checked', t > 0 && n === t);
}
