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
        // Hide buttons only for users with the "Applicant" role
        // and who are NOT Administrators/System Managers (to ensure admins always have access)
        const is_applicant = frappe.user_roles.includes("Applicant");
        const is_admin = frappe.user_roles.includes("Administrator") || frappe.user_roles.includes("System Manager");

        if (!is_applicant || is_admin) {
            // 1. Update Entrance Test Rank
            listview.page.add_inner_button(__("Update Entrance Test Rank"), function () {
                open_update_rank_dialog(listview);
            }, __("Actions"));

            // 2. Publish Result
            listview.page.add_inner_button(__("Publish Result"), function () {
                open_publish_result_dialog(listview);
            }, __("Actions"));

            // 3. Export Marks Template
            listview.page.add_inner_button(__("Export Marks Template"), function () {
                open_export_marks_dialog_for_list(listview);
            }, __("Actions"));

            // 4. Reschedule
            listview.page.add_inner_button(__("Reschedule"), function () {
                open_reschedule_dialog(listview);
            }, __("Actions"));
        }
    }
};

/**
 * Helper to extract filter values from route_options, listview filter_area, or URL query string
 */
function get_listview_filter_val(listview, fieldname) {
    if (frappe.route_options && frappe.route_options[fieldname]) {
        return frappe.route_options[fieldname];
    }
    if (listview && listview.filter_area && typeof listview.filter_area.get_filters === "function") {
        try {
            const filters = listview.filter_area.get_filters();
            for (let f of filters) {
                if (Array.isArray(f) && f[1] === fieldname) {
                    return f[3];
                } else if (f && f.fieldname === fieldname) {
                    return f.value;
                }
            }
        } catch (e) {}
    }
    try {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has(fieldname)) {
            return urlParams.get(fieldname);
        }
    } catch (e) {}
    return "";
}

/**
 * Custom Update Rank Dialog for List View
 */
function open_update_rank_dialog(listview) {
    const default_ay = get_listview_filter_val(listview, "academic_year");
    const default_ac = get_listview_filter_val(listview, "admission_cycle");
    const default_pl = get_listview_filter_val(listview, "program_level");

    let d = new frappe.ui.Dialog({
        title: __("Update Entrance Test Rank"),
        fields: [
            {
                label: __("Academic Year"),
                fieldname: "academic_year",
                fieldtype: "Link",
                options: "Academic Year",
                default: default_ay,
                reqd: 1,
                change() { update_dialog_applicant_count(d); }
            },
            {
                label: __("Admission Cycle"),
                fieldname: "admission_cycle",
                fieldtype: "Link",
                options: "Admission Cycle",
                default: default_ac,
                reqd: 1,
                change() { update_dialog_applicant_count(d); }
            },
            {
                label: __("Programme Level"),
                fieldname: "program_level",
                fieldtype: "Select",
                options: "Undergraduate\nPostgraduate\nResearch Course",
                default: default_pl,
                reqd: 1,
                change() {
                    d.set_value("program", "");
                    update_dialog_applicant_count(d);
                }
            },
            {
                label: __("Applicant Type"),
                fieldname: "applicant_type",
                fieldtype: "Select",
                options: "Domestic Applicants\nInternational Applicants\nBoth",
                default: "Domestic Applicants",
                reqd: 1,
                change() { update_dialog_applicant_count(d); }
            },
            {
                label: __("Programme"),
                fieldname: "program",
                fieldtype: "Link",
                options: "Programme",
                depends_on: "eval:doc.program_level",
                change() { update_dialog_applicant_count(d); }
            },
            {
                fieldname: "total_applicants_html",
                fieldtype: "HTML"
            }
        ],
        primary_action_label: __("Generate"),
        primary_action(values) {
            d.hide();
            frappe.show_progress(__("Update Ranking"), 0, 100, __("Calculating scores and ranks..."));
            frappe.call({
                method: "slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.update_ranks_by_category",
                args: values,
                callback: function (r) {
                    frappe.show_progress(__("Update Ranking"), 100, 100, __("Completed"));
                    setTimeout(() => frappe.hide_progress(), 3000);
                    if (!r.exc) {
                        frappe.msgprint({
                            message: __("Rank updated successfully for {0} applicants.", [r.message]),
                            indicator: 'green',
                            alert: true
                        });
                        listview.refresh();
                    }
                },
                error: function () {
                    frappe.hide_progress();
                }
            });
        }
    });

    d.listview = listview;

    d.set_query("admission_cycle", function () {
        return { filters: { "status": "Active" } };
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

    d.show();

    if (default_ay || default_ac || default_pl) {
        d.set_values({
            academic_year: default_ay,
            admission_cycle: default_ac,
            program_level: default_pl,
            applicant_type: "Domestic Applicants"
        });
    }

    ["academic_year", "admission_cycle", "program_level", "applicant_type", "program"].forEach(fn => {
        if (d.fields_dict[fn] && d.fields_dict[fn].$input) {
            d.fields_dict[fn].$input.on("change blur input", () => update_dialog_applicant_count(d));
        }
    });

    update_dialog_applicant_count(d);
}

/**
 * Custom Publish Result Dialog for List View
 */
function open_publish_result_dialog(listview) {
    const default_ay = get_listview_filter_val(listview, "academic_year");
    const default_ac = get_listview_filter_val(listview, "admission_cycle");
    const default_pl = get_listview_filter_val(listview, "program_level");

    let pd = new frappe.ui.Dialog({
        title: __("Publish Entrance Test Result"),
        fields: [
            {
                label: __("Academic Year"),
                fieldname: "academic_year",
                fieldtype: "Link",
                options: "Academic Year",
                default: default_ay,
                reqd: 1,
                change() { update_dialog_applicant_count(pd); }
            },
            {
                label: __("Admission Cycle"),
                fieldname: "admission_cycle",
                fieldtype: "Link",
                options: "Admission Cycle",
                default: default_ac,
                reqd: 1,
                change() { update_dialog_applicant_count(pd); }
            },
            {
                label: __("Programme Level"),
                fieldname: "program_level",
                fieldtype: "Select",
                options: "Undergraduate\nPostgraduate\nResearch Course",
                default: default_pl,
                reqd: 1,
                change() {
                    pd.set_value("program", "");
                    update_dialog_applicant_count(pd);
                }
            },
            {
                label: __("Applicant Type"),
                fieldname: "applicant_type",
                fieldtype: "Select",
                options: "Domestic Applicants\nInternational Applicants\nBoth",
                default: "Domestic Applicants",
                reqd: 1,
                change() { update_dialog_applicant_count(pd); }
            },
            {
                label: __("Programme"),
                fieldname: "program",
                fieldtype: "Link",
                options: "Programme",
                depends_on: "eval:doc.program_level",
                change() { update_dialog_applicant_count(pd); }
            },
            {
                fieldname: "total_applicants_html",
                fieldtype: "HTML"
            }
        ],
        primary_action_label: __("Publish"),
        primary_action(values) {
            frappe.confirm(
                __("This will mark all matching Entrance Test Seat Allocation records as <b>Result Published</b> and send result emails to all applicants. Do you want to continue?"),
                function () {
                    pd.hide();
                    frappe.show_progress(__("Publishing Results"), 0, 100, __("Updating records and queueing emails..."));
                    frappe.call({
                        method: "slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.publish_results",
                        args: values,
                        callback: function (r) {
                            frappe.show_progress(__("Publishing Results"), 100, 100, __("Completed"));
                            setTimeout(() => frappe.hide_progress(), 3000);
                            if (!r.exc && r.message) {
                                frappe.msgprint({
                                    title: __("Results Published"),
                                    message: __(
                                        "<b>{0}</b> records published. <b>{1}</b> notification emails queued.",
                                        [r.message.published, r.message.notified]
                                    ),
                                    indicator: "green"
                                });
                                listview.refresh();
                            }
                        },
                        error: function () {
                            frappe.hide_progress();
                        }
                    });
                }
            );
        }
    });

    pd.listview = listview;

    pd.set_query("admission_cycle", function () {
        return { filters: { "status": "Active" } };
    });
    pd.set_query("program", function () {
        return {
            query: "slcm.admission.doctype.entrance_test_generation.entrance_test_generation.get_program_query",
            filters: {
                "program_level": pd.get_value("program_level"),
                "admission_cycle": pd.get_value("admission_cycle")
            }
        };
    });

    pd.show();

    if (default_ay || default_ac || default_pl) {
        pd.set_values({
            academic_year: default_ay,
            admission_cycle: default_ac,
            program_level: default_pl,
            applicant_type: "Domestic Applicants"
        });
    }

    ["academic_year", "admission_cycle", "program_level", "applicant_type", "program"].forEach(fn => {
        if (pd.fields_dict[fn] && pd.fields_dict[fn].$input) {
            pd.fields_dict[fn].$input.on("change blur input", () => update_dialog_applicant_count(pd));
        }
    });

    update_dialog_applicant_count(pd);
}

/**
 * Helper to update the Total Applicants HTML tile in dialogs
 */
function update_dialog_applicant_count(d) {
    const html_field = d.get_field("total_applicants_html");
    if (!html_field) return;

    let ay = d.get_value("academic_year") || "";
    let ac = d.get_value("admission_cycle") || "";
    let pl = d.get_value("program_level") || "";
    let at = d.get_value("applicant_type") || "Domestic Applicants";
    let prog = d.get_value("program") || "";

    frappe.call({
        method: "slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.get_applicant_count",
        args: {
            academic_year: ay,
            admission_cycle: ac,
            program_level: pl,
            applicant_type: at,
            program: prog
        },
        callback: function (r) {
            if (r && r.message) {
                const total = r.message.total !== undefined ? r.message.total : 0;
                const attended = r.message.attended !== undefined ? r.message.attended : 0;
                const absent = r.message.absent !== undefined ? r.message.absent : 0;
                html_field.$wrapper.html(`
                    <div style="background-color: #ebf8ff; border: 1px solid #bee3f8; border-radius: 8px; padding: 12px 16px; margin: 12px 0; display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #2b6cb0; font-weight: 600;">Total Applicants</div>
                            <div style="font-size: 22px; font-weight: 700; color: #2c5282; margin-top: 2px;">${total}</div>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <div style="background: #ffffff; padding: 6px 12px; border-radius: 6px; border: 1px solid #cbd5e0; font-size: 12px; font-weight: 600; color: #4a5568;">
                                Attended: <span style="color: #2b6cb0;">${attended}</span>
                            </div>
                            <div style="background: #ffffff; padding: 6px 12px; border-radius: 6px; border: 1px solid #cbd5e0; font-size: 12px; font-weight: 600; color: #4a5568;">
                                Absent: <span style="color: #e53e3e;">${absent}</span>
                            </div>
                        </div>
                    </div>
                `);
            }
        }
    });
}

/**
 * Custom Export Marks Template Dialog for List View
 */
function open_export_marks_dialog_for_list(listview) {
    let d = new frappe.ui.Dialog({
        title: __('Export Entrance Test Marks Template'),
        fields: [
            {
                label: __('Academic Year'),
                fieldname: 'academic_year',
                fieldtype: 'Link',
                options: 'Academic Year'
            },
            {
                label: __('Admission Cycle'),
                fieldname: 'admission_cycle',
                fieldtype: 'Link',
                options: 'Admission Cycle'
            },
            {
                label: __('Campus'),
                fieldname: 'campus',
                fieldtype: 'Link',
                options: 'Campus'
            },
            {
                label: __('Programme Level'),
                fieldname: 'program_level',
                fieldtype: 'Select',
                options: '\nUndergraduate\nPostgraduate\nResearch Course'
            },
            {
                label: __('Programme'),
                fieldname: 'program',
                fieldtype: 'Link',
                options: 'Programme'
            },
            {
                label: __('Entrance Test'),
                fieldname: 'entrance_test',
                fieldtype: 'Link',
                options: 'Entrance Test'
            },
            {
                label: __('Shortlisted Only (Stage 2 - Part B)'),
                fieldname: 'shortlisted_only',
                fieldtype: 'Check',
                default: 0,
                description: __('Check this for Stage 2 (Part B marks entry) to export shortlisted applicants only with Part A marks pre-filled.')
            },
            {
                label: __('File Format'),
                fieldname: 'file_format',
                fieldtype: 'Select',
                options: 'xlsx\ncsv',
                default: 'xlsx',
                reqd: 1
            }
        ],
        primary_action_label: __('Export Template'),
        primary_action(values) {
            d.hide();
            frappe.show_alert({ message: __('Generating Marks Template...'), indicator: 'blue' });

            frappe.call({
                method: 'slcm.admission.utils.entrance_test_marks_manager.export_entrance_test_marks_template',
                args: values,
                freeze: true,
                freeze_message: __('Building Export File...'),
                callback: function (r) {
                    if (r.message && r.message.file_url) {
                        const link = document.createElement('a');
                        link.href = r.message.file_url;
                        link.download = r.message.filename || 'Marks_Template.xlsx';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        frappe.show_alert({
                            message: __('Template downloaded successfully.'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    });

    d.set_query("admission_cycle", function () {
        return { filters: { "status": "Active" } };
    });

    d.show();
}

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

// Build provider checkboxes HTML (3-column grid style with search)
function _build_provider_html(providers) {
    if (!providers.length) {
        return '<p class="text-muted" style="padding:10px 0;">No providers match the selected campus.</p>';
    }
    const items = providers.map(p => `
        <label class="provider-card"
               data-center-name="${(p.center_name || p.name).toLowerCase()}"
               data-center-address="${(p.center_address || '').toLowerCase()}"
               style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px;
                      border:1.5px solid #cbd5e1; border-radius:8px; cursor:pointer;
                      background:#ffffff; transition: all 0.15s ease; margin:0; box-shadow:0 1px 2px rgba(0,0,0,0.04);
                      position:relative; min-height:64px; box-sizing:border-box;">
            <input type="checkbox" class="provider-checkbox"
                   data-name="${p.name}"
                   data-campus="${p.campus || ''}"
                   style="width:16px; height:16px; cursor:pointer; margin-top:2px; flex-shrink:0;">
            <span style="line-height:1.4; flex:1; overflow:hidden;">
                <span style="display:block; font-weight:700; font-size:13px; color:#1e293b; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${p.center_name || p.name}">
                    ${p.center_name || p.name}
                </span>
                ${p.center_address
            ? `<span style="display:block; font-size:11px; color:#64748b; margin-top:2px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;" title="${p.center_address}">
                           📍 ${p.center_address}
                       </span>`
            : `<span style="display:block; font-size:11px; color:#94a3b8; margin-top:2px; font-style:italic;">No address provided</span>`
        }
            </span>
        </label>
    `).join('');

    return `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div id="provider-sel-count" style="font-size:12px; color:#6c757d; font-weight:500;">
                0 provider(s) selected
            </div>
            <div style="position:relative; width:220px;">
                <input type="text" id="reschedule-center-search" placeholder="${__("🔍 Search centre...")}" 
                       style="width:100%; padding:5px 10px; border:1px solid #cbd5e1; border-radius:6px; font-size:12px; outline:none; background:#ffffff;">
            </div>
        </div>
        <div id="provider-list" style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; max-height:200px; overflow-y:auto; padding:6px; border:1px solid #e2e8f0; border-radius:8px; background:#f8fafc;">
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
                label: __('Programme Level'),
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

    // ── Center search filtering ───────────────────────────────────────────────
    d.$wrapper.on("input keyup search", "#reschedule-center-search", function () {
        const q = $(this).val().toLowerCase().trim();
        d.$wrapper.find(".provider-card").each(function () {
            const name = $(this).attr("data-center-name") || "";
            const addr = $(this).attr("data-center-address") || "";
            if (!q || name.includes(q) || addr.includes(q)) {
                $(this).css("display", "flex");
            } else {
                $(this).css("display", "none");
            }
        });
    });

    // ── Provider checkbox count & card highlight ──────────────────────────────
    d.$wrapper.on('change', '.provider-checkbox', function () {
        const n = d.$wrapper.find('.provider-checkbox:checked').length;
        d.$wrapper.find('#provider-sel-count').text(`${n} provider(s) selected`);

        d.$wrapper.find(".provider-card").each(function () {
            const $chk = $(this).find(".provider-checkbox");
            if ($chk.is(":checked")) {
                $(this).css({
                    "border-color": "#2da44e",
                    "background-color": "#f0fdf4",
                    "box-shadow": "0 2px 6px rgba(45,164,78,0.15)"
                });
            } else {
                $(this).css({
                    "border-color": "#cbd5e1",
                    "background-color": "#ffffff",
                    "box-shadow": "0 1px 2px rgba(0,0,0,0.04)"
                });
            }
        });
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
                                <th>Programme</th>
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
