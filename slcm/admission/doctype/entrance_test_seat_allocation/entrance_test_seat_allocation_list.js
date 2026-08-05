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

            // 5. Reject and Allocate Centre
            listview.page.add_inner_button(__("Reject and Allocate Centre"), function () {
                open_reject_and_allocate_dialog(listview);
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
    let applicants = [];
    const selected_applicant_names = new Set();
    let applicant_current_page = 1;
    const applicant_page_size = 10;
    let applicant_filters = {
        applicant_id: "",
        candidate_name: "",
        programme: "",
        pwd_only: false
    };

    function get_filtered_applicants() {
        return applicants.filter(a => {
            const id_match = !applicant_filters.applicant_id || (a.applicant || "").toLowerCase().includes(applicant_filters.applicant_id);
            const name_match = !applicant_filters.candidate_name || (a.candidate_name || "").toLowerCase().includes(applicant_filters.candidate_name);
            const prog_match = !applicant_filters.programme || (a.program || "").toLowerCase().includes(applicant_filters.programme);
            let pwd_match = true;
            if (applicant_filters.pwd_only) {
                pwd_match = (a.pwd == 1 || (a.pwd || "").toString().toLowerCase() === "yes");
            }
            return id_match && name_match && prog_match && pwd_match;
        });
    }

    function render_applicant_page() {
        const filtered = get_filtered_applicants();
        const total_pages = Math.ceil(filtered.length / applicant_page_size) || 1;
        if (applicant_current_page > total_pages) applicant_current_page = total_pages;
        if (applicant_current_page < 1) applicant_current_page = 1;

        const start = (applicant_current_page - 1) * applicant_page_size;
        const page_applicants = filtered.slice(start, start + applicant_page_size);

        if (!page_applicants.length) {
            d.$wrapper.find("#reschedule-applicant-table-body").html(`
                <tr>
                    <td colspan="5" style="text-align:center; padding:25px; color:#94a3b8; font-size:13px;">
                        No applicants match the filter criteria.
                    </td>
                </tr>
            `);
        } else {
            const rows_html = page_applicants.map((row, p_idx) => {
                const global_idx = start + p_idx + 1;
                const is_checked = selected_applicant_names.has(row.name);
                return `
                    <tr data-name="${row.name}">
                        <td style="text-align:center; width:40px; vertical-align:middle;">
                            <input type="checkbox" class="applicant-checkbox" 
                                   data-name="${row.name}" ${is_checked ? 'checked' : ''}>
                        </td>
                        <td style="text-align:center; width:60px; color:#64748b; font-size:12px; vertical-align:middle;">${global_idx}</td>
                        <td style="vertical-align:middle;">${row.applicant || "-"}</td>
                        <td style="vertical-align:middle;">
                            <b>${row.candidate_name || "Unknown"}</b>
                            ${(row.pwd == 1 || (row.pwd || "").toString().toLowerCase() === "yes") ? `<span style="font-size:10px; background:#fef3c7; color:#92400e; padding:1px 5px; border-radius:4px; margin-left:4px; border:1px solid #fde68a; font-weight:700;">♿ PWD</span>` : ''}
                        </td>
                        <td style="vertical-align:middle;">${row.program || "-"}</td>
                    </tr>
                `;
            }).join("");

            d.$wrapper.find("#reschedule-applicant-table-body").html(rows_html);
        }

        d.$wrapper.find("#applicant-page-info").text(`Page ${applicant_current_page} of ${total_pages}`);
        d.$wrapper.find("#applicant-prev-btn").prop("disabled", applicant_current_page <= 1);
        d.$wrapper.find("#applicant-next-btn").prop("disabled", applicant_current_page >= total_pages);

        update_applicant_counts(filtered.length);
    }

    function update_applicant_counts(filtered_length) {
        const sel_count = selected_applicant_names.size;
        const total_count = applicants.length;
        if (filtered_length !== undefined && filtered_length !== total_count) {
            d.$wrapper.find("#sel-count").text(`${sel_count} of ${total_count} selected (Filtered: ${filtered_length})`);
        } else {
            d.$wrapper.find("#sel-count").text(`${sel_count} of ${total_count} selected`);
        }
        const all_selected = total_count > 0 && sel_count === total_count;
        d.$wrapper.find("#select-all-chk").prop("checked", all_selected);
    }

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
                on_change: () => fetch_absent_applicants()
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Academic Year'),
                fieldname: 'academic_year',
                fieldtype: 'Link',
                options: 'Academic Year',
                on_change: () => fetch_absent_applicants()
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Campus'),
                fieldname: 'campus',
                fieldtype: 'Link',
                options: 'Campus',
                on_change: () => {
                    fetch_absent_applicants();
                    _filter_providers_by_campus(d, all_providers);
                }
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Admission Cycle'),
                fieldname: 'admission_cycle',
                fieldtype: 'Link',
                options: 'Admission Cycle',
                on_change: () => fetch_absent_applicants()
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
            const selected_applicants = Array.from(selected_applicant_names);
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
        selected_applicant_names.clear();
        for (let i = 0; i < Math.min(val, applicants.length); i++) {
            selected_applicant_names.add(applicants[i].name);
        }
        applicant_current_page = 1;
        render_applicant_page();
    });

    // ── Applicant Filtering & Pagination Events ────────────────────────────────
    d.$wrapper.on("input", "#filter-applicant-id", function () {
        applicant_filters.applicant_id = $(this).val().toLowerCase().trim();
        applicant_current_page = 1;
        render_applicant_page();
    });
    d.$wrapper.on("input", "#filter-candidate-name", function () {
        applicant_filters.candidate_name = $(this).val().toLowerCase().trim();
        applicant_current_page = 1;
        render_applicant_page();
    });
    d.$wrapper.on("input", "#filter-programme", function () {
        applicant_filters.programme = $(this).val().toLowerCase().trim();
        applicant_current_page = 1;
        render_applicant_page();
    });
    d.$wrapper.on("change", "#pwd-applicant-filter-chk", function () {
        applicant_filters.pwd_only = this.checked;
        applicant_current_page = 1;
        render_applicant_page();
    });
    d.$wrapper.on("click", "#applicant-clear-all-btn", function () {
        selected_applicant_names.clear();
        render_applicant_page();
    });
    d.$wrapper.on("click", "#applicant-prev-btn", function () {
        if (applicant_current_page > 1) {
            applicant_current_page--;
            render_applicant_page();
        }
    });
    d.$wrapper.on("click", "#applicant-next-btn", function () {
        const filtered = get_filtered_applicants();
        const total_pages = Math.ceil(filtered.length / applicant_page_size) || 1;
        if (applicant_current_page < total_pages) {
            applicant_current_page++;
            render_applicant_page();
        }
    });
    d.$wrapper.on("change", ".applicant-checkbox", function () {
        const name = $(this).data("name");
        if (this.checked) {
            selected_applicant_names.add(name);
        } else {
            selected_applicant_names.delete(name);
        }
        update_applicant_counts(get_filtered_applicants().length);
    });
    d.$wrapper.on("change", "#select-all-chk", function () {
        const filtered = get_filtered_applicants();
        if (this.checked) {
            filtered.forEach(a => selected_applicant_names.add(a.name));
        } else {
            filtered.forEach(a => selected_applicant_names.delete(a.name));
        }
        render_applicant_page();
    });

    // ── Initial applicant fetch ────────────────────────────────────────────────
    function fetch_absent_applicants() {
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
                fields: ['name', 'candidate_name', 'applicant', 'program', 'pwd'],
                limit_page_length: 0
            },
            callback: function (r) {
                applicants = r.message || [];
                selected_applicant_names.clear();
                applicant_current_page = 1;

                let html = `
                    <div style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; gap:12px; align-items:center;">
                            <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px;">
                                <input type="checkbox" id="select-all-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;">
                                Select All
                            </label>
                            <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px; margin-left:12px;" title="Filter PWD Applicants">
                                <input type="checkbox" id="pwd-applicant-filter-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;" ${applicant_filters.pwd_only ? 'checked' : ''}>
                                ♿ PWD
                            </label>
                            <button type="button" id="applicant-clear-all-btn" class="btn btn-xs btn-default" style="font-size:11px; padding:2px 8px; border-radius:4px;">
                                Clear All
                            </button>
                            <span id="sel-count" style="color:#6c757d; font-size:12px; font-weight:500;">
                                0 of ${applicants.length} selected
                            </span>
                        </div>
                        <div id="applicant-pagination" style="display:flex; align-items:center; gap:8px; font-size:12px;">
                            <button type="button" id="applicant-prev-btn" class="btn btn-xs btn-default" style="padding:2px 8px; font-size:11px;">
                                &laquo; Prev
                            </button>
                            <span id="applicant-page-info" style="font-weight:600; color:#475569;">Page 1 of 1</span>
                            <button type="button" id="applicant-next-btn" class="btn btn-xs btn-default" style="padding:2px 8px; font-size:11px;">
                                Next &raquo;
                            </button>
                        </div>
                    </div>
                    <div style="border:1px solid #d1d8dd; border-radius:8px; overflow:hidden; background:#ffffff;">
                        <table class="table table-bordered table-hover" style="margin:0; font-size:13px; width:100%;">
                            <thead style="background:#f8fafc;">
                                <tr>
                                    <th style="width:40px; text-align:center; vertical-align:middle; padding:8px 4px;"></th>
                                    <th style="width:60px; text-align:center; color:#3b82f6; vertical-align:middle; padding:8px 4px; font-weight:600;">No.</th>
                                    <th style="width:25%; color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Applicant ID</th>
                                    <th style="width:35%; color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Candidate Name</th>
                                    <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Programme</th>
                                </tr>
                                <tr style="background:#f1f5f9;">
                                    <th style="padding:4px 6px; text-align:center;"></th>
                                    <th style="padding:4px 6px; text-align:center;"></th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-applicant-id" placeholder="${__("Filter ID...")}" value="${applicant_filters.applicant_id}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-candidate-name" placeholder="${__("Filter Name...")}" value="${applicant_filters.candidate_name}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-programme" placeholder="${__("Filter Programme...")}" value="${applicant_filters.programme}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                </tr>
                            </thead>
                            <tbody id="reschedule-applicant-table-body"></tbody>
                        </table>
                    </div>`;
                
                d.get_field('applicants_html').$wrapper.html(html);
                render_applicant_page();
            }
        });
    }

    fetch_absent_applicants();
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
//  Reject and Allocate Centre Dialog
// ──────────────────────────────────────────────────────────────────────────────
function open_reject_and_allocate_dialog(listview) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Entrance Test Provider',
            filters: { active: 1, available_capacity: [">", 0] },
            fields: ['name', 'center_name', 'center_address', 'campus', 'provider_type', 'city'],
            limit_page_length: 200
        },
        callback: function (r) {
            const all_providers = r.message || [];
            if (!all_providers.length) {
                frappe.msgprint({ title: __('No Available Providers'), message: __('No active Entrance Test Providers with available seats found.'), indicator: 'orange' });
                return;
            }
            _show_reject_and_allocate_dialog(listview, all_providers);
        }
    });
}

function _show_reject_and_allocate_dialog(listview, all_providers) {
    let applicants = [];
    const selected_applicant_names = new Set();
    const selected_provider_names = new Set();

    let search_center_query = "";
    let center_pwd_only = false;
    let center_current_page = 1;
    const center_page_size = 9;

    let applicant_current_page = 1;
    const applicant_page_size = 10;
    let applicant_filters = { applicant_id: "", candidate_name: "", programme: "", entrance_test_city: "", old_centre: "", pwd_only: false };

    function get_filtered_providers() {
        let list = all_providers;
        const selected_city = d ? d.get_value("entrance_test_city") : "";
        if (selected_city) {
            list = list.filter(p => p.city === selected_city);
        }
        if (center_pwd_only) {
            list = list.filter(p => p.pwd_accessible == 1 || p.pwd_accessible === "1");
        }
        if (!search_center_query) return list;
        const q = search_center_query.toLowerCase().trim();
        return list.filter(p => {
            const name = (p.center_name || p.name).toLowerCase();
            const addr = (p.center_address || "").toLowerCase();
            return name.includes(q) || addr.includes(q);
        });
    }

    function render_center_page() {
        if(!d || !d.$wrapper) return;
        const filtered = get_filtered_providers();
        const total_pages = Math.ceil(filtered.length / center_page_size) || 1;
        if (center_current_page > total_pages) center_current_page = total_pages;
        if (center_current_page < 1) center_current_page = 1;

        const start = (center_current_page - 1) * center_page_size;
        const page_providers = filtered.slice(start, start + center_page_size);

        const $wrapper = d.$wrapper;

        if (!page_providers.length) {
            $wrapper.find("#provider-list").html(`
                <div style="grid-column: 1 / -1; padding:20px; text-align:center; color:#94a3b8; font-size:13px;">
                    No centres match your criteria.
                </div>
            `);
        } else {
            const html = page_providers.map(p => {
                const is_checked = selected_provider_names.has(p.name);
                const border_col = is_checked ? "#2da44e" : "#cbd5e1";
                const bg_col = is_checked ? "#f0fdf4" : "#ffffff";
                const box_shadow = is_checked ? "0 2px 6px rgba(45,164,78,0.15)" : "0 1px 2px rgba(0,0,0,0.04)";

                return `
                    <label class="provider-card" data-name="${p.name}"
                           style="display:flex; align-items:flex-start; gap:10px; padding:10px 12px;
                                  border:1.5px solid ${border_col}; border-radius:8px; cursor:pointer;
                                  background:${bg_col}; transition: all 0.15s ease; margin:0; box-shadow:${box_shadow};
                                  position:relative; min-height:64px; box-sizing:border-box;">
                        <input type="checkbox" class="provider-checkbox"
                               data-name="${p.name}"
                               ${is_checked ? 'checked' : ''}
                               style="width:16px; height:16px; cursor:pointer; margin-top:2px; flex-shrink:0;">
                        <span style="line-height:1.4; flex:1; overflow:hidden;">
                            <span style="display:block; font-weight:700; font-size:13px; color:#1e293b; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${p.center_name || p.name}">
                                ${p.center_name || p.name}
                                ${(p.pwd_accessible == 1 || p.pwd_accessible === "1") ? `<span style="font-size:10px; background:#dbeafe; color:#1e40af; padding:1px 5px; border-radius:4px; margin-left:4px; font-weight:600;">♿ PWD</span>` : ''}
                            </span>
                            ${p.center_address
                        ? `<span style="display:block; font-size:11px; color:#64748b; margin-top:2px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;" title="${p.center_address}">
                                       ${p.center_address}
                                   </span>`
                        : `<span style="display:block; font-size:11px; color:#94a3b8; margin-top:2px; font-style:italic;">No address provided</span>`
                    }
                        </span>
                    </label>
                `;
            }).join("");
            $wrapper.find("#provider-list").html(html);
        }

        $wrapper.find("#center-page-info").text(`Page ${center_current_page} of ${total_pages}`);
        $wrapper.find("#center-prev-btn").prop("disabled", center_current_page <= 1);
        $wrapper.find("#center-next-btn").prop("disabled", center_current_page >= total_pages);

        update_center_counts();
    }

    function update_center_counts() {
        if(!d || !d.$wrapper) return;
        const sel_count = selected_provider_names.size;
        const total_count = all_providers.length;
        const filtered_count = get_filtered_providers().length;
        if (center_pwd_only || search_center_query || d.get_value("entrance_test_city")) {
            d.$wrapper.find("#provider-sel-count").text(`Centres: ${filtered_count} of ${total_count} | ${sel_count} selected`);
        } else {
            d.$wrapper.find("#provider-sel-count").text(`Total Centres: ${total_count} | ${sel_count} selected`);
        }
        const all_selected = filtered_count > 0 && sel_count === filtered_count;
        d.$wrapper.find("#center-select-all-chk").prop("checked", all_selected);
    }

    function get_filtered_applicants() {
        return applicants.filter(a => {
            const id_match = !applicant_filters.applicant_id || (a.applicant || "").toLowerCase().includes(applicant_filters.applicant_id);
            const name_match = !applicant_filters.candidate_name || (a.candidate_name || "").toLowerCase().includes(applicant_filters.candidate_name);
            const prog_match = !applicant_filters.programme || (a.program || "").toLowerCase().includes(applicant_filters.programme);
            const city_match = !applicant_filters.entrance_test_city || (a.entrance_test_city || "").toLowerCase().includes(applicant_filters.entrance_test_city);
            const centre_match = !applicant_filters.old_centre || (a.center_name || "").toLowerCase().includes(applicant_filters.old_centre);
            let pwd_match = true;
            if (applicant_filters.pwd_only) {
                pwd_match = (a.pwd == 1 || (a.pwd || "").toString().toLowerCase() === "yes");
            }
            return id_match && name_match && prog_match && city_match && centre_match && pwd_match;
        });
    }

    function render_applicant_page() {
        if(!d || !d.$wrapper) return;
        const filtered = get_filtered_applicants();
        const total_pages = Math.ceil(filtered.length / applicant_page_size) || 1;
        if (applicant_current_page > total_pages) applicant_current_page = total_pages;
        if (applicant_current_page < 1) applicant_current_page = 1;

        const start = (applicant_current_page - 1) * applicant_page_size;
        const page_applicants = filtered.slice(start, start + applicant_page_size);

        if (!page_applicants.length) {
            d.$wrapper.find("#rej-applicant-table-body").html(`<tr><td colspan="6" style="text-align:center; padding:25px; color:#94a3b8; font-size:13px;">No applicants match the filter criteria.</td></tr>`);
        } else {
            const rows_html = page_applicants.map((row, p_idx) => {
                const global_idx = start + p_idx + 1;
                const is_checked = selected_applicant_names.has(row.name);
                return `
                    <tr data-name="${row.name}">
                        <td style="text-align:center; width:40px; vertical-align:middle;">
                            <input type="checkbox" class="applicant-checkbox" data-name="${row.name}" ${is_checked ? 'checked' : ''}>
                        </td>
                        <td style="text-align:center; width:60px; color:#64748b; font-size:12px; vertical-align:middle;">${global_idx}</td>
                        <td style="vertical-align:middle;">${row.applicant || "-"}</td>
                        <td style="vertical-align:middle;">
                            <b>${row.candidate_name || "Unknown"}</b>
                            ${(row.pwd == 1 || (row.pwd || "").toString().toLowerCase() === "yes") ? `<span style="font-size:10px; background:#fef3c7; color:#92400e; padding:1px 5px; border-radius:4px; margin-left:4px; border:1px solid #fde68a; font-weight:700;">♿ PWD</span>` : ''}
                        </td>
                        <td style="vertical-align:middle;">${row.program || "-"}</td>
                        <td style="vertical-align:middle;">${row.entrance_test_city || "-"}</td>
                        <td style="vertical-align:middle;">${row.center_name || "-"}</td>
                    </tr>
                `;
            }).join("");
            d.$wrapper.find("#rej-applicant-table-body").html(rows_html);
        }
        d.$wrapper.find("#applicant-page-info").text(`Page ${applicant_current_page} of ${total_pages}`);
        d.$wrapper.find("#applicant-prev-btn").prop("disabled", applicant_current_page <= 1);
        d.$wrapper.find("#applicant-next-btn").prop("disabled", applicant_current_page >= total_pages);
        update_applicant_counts(filtered.length);
    }

    function update_applicant_counts(filtered_length) {
        if(!d || !d.$wrapper) return;
        const sel_count = selected_applicant_names.size;
        const total_count = applicants.length;
        if (filtered_length !== undefined && filtered_length !== total_count) {
            d.$wrapper.find("#sel-count").text(`${sel_count} of ${total_count} selected (Filtered: ${filtered_length})`);
        } else {
            d.$wrapper.find("#sel-count").text(`${sel_count} of ${total_count} selected`);
        }
        const all_selected = total_count > 0 && sel_count === total_count;
        d.$wrapper.find("#select-all-chk").prop("checked", all_selected);
    }

    function update_allocation_type_ui() {
        if(!d || !d.$wrapper) return;
        const alloc_type = d.get_value("allocation_type");
        if (alloc_type === "Allocate Directly") {
            d.$wrapper.find("#center-pwd-filter-chk").prop("disabled", false);
            d.$wrapper.find("#center-search-input").prop("disabled", false);
            d.$wrapper.find(".provider-checkbox").prop("disabled", false);
        } else {
            // Allow Applicant Selection
            // They can still select preferences if they want, but usually it's just letting applicant pick
        }
    }

    let d = new frappe.ui.Dialog({
        title: __('Reject and Allocate Centre'),
        size: 'extra-large',
        fields: [
            { fieldtype: 'Section Break', label: __('Filters for Applicants') },
            {
                label: __('Allocation Status'),
                fieldname: 'filter_allocation_status',
                fieldtype: 'Select',
                options: '\nNot Allocated\nPreferences Assigned\nAllocated\nReallocated\nCancelled\nRejected',
                onchange: () => fetch_applicants()
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Entrance Test Status'),
                fieldname: 'filter_entrance_test_status',
                fieldtype: 'Select',
                options: '\nAttended\nAbsent\nRescheduled\nNot Scheduled\nScheduled',
                onchange: () => fetch_applicants()
            },

            { fieldtype: 'Section Break' },
            {
                label: __("Allocate Type"),
                fieldname: "allocation_type",
                fieldtype: "Select",
                options: ["Allocate Directly", "Allow Applicant Selection"],
                default: "Allocate Directly",
                reqd: 1,
                onchange: function() {
                    update_allocation_type_ui();
                }
            },
            { fieldtype: "Column Break" },
            {
                label: __("Entrance Test City"),
                fieldname: "entrance_test_city",
                fieldtype: "Link",
                options: "Entrance Test City",
                onchange: function() {
                    center_current_page = 1;
                    render_center_page();
                }
            },
            { fieldtype: "Section Break" },
            {
                fieldtype: "HTML",
                fieldname: "provider_section_label",
                options: `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                        <div style="font-weight:600; font-size:13px; color:#333;">
                            ${__("Select Entrance Test Centres")}
                            <span style="font-weight:400; font-size:11px; color:#888; margin-left:8px;">
                                — Select one or more centres as preferences for applicants
                            </span>
                        </div>
                        <div style="position:relative; width:240px;">
                            <input type="text" id="center-search-input" placeholder="${__("🔍 Search centre...")}" 
                                   style="width:100%; padding:6px 12px; border:1px solid #cbd5e1; border-radius:6px; font-size:12px; outline:none; background:#ffffff; transition:border 0.15s;">
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; background:#f1f5f9; padding:6px 12px; border-radius:6px; font-size:12px;">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <label style="margin:0; font-weight:600; cursor:pointer; display:flex; align-items:center; color:#334155;">
                                <input type="checkbox" id="center-select-all-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;">
                                Select All Centres
                            </label>
                            <label style="margin:0; font-weight:600; cursor:pointer; display:flex; align-items:center; color:#334155; margin-left:12px;" title="Filter PWD Accessible Centres">
                                <input type="checkbox" id="center-pwd-filter-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;">
                                ♿ PWD
                            </label>
                            <button type="button" id="center-clear-all-btn" class="btn btn-xs btn-default" style="font-size:11px; padding:2px 8px; border-radius:4px;">
                                Clear All
                            </button>
                        </div>
                        <div id="provider-sel-count" style="color:#475569; font-weight:600; font-size:12px;">
                            Total Centres: ${all_providers.length} | 0 selected
                        </div>
                    </div>
                `
            },
            {
                fieldtype: "HTML",
                fieldname: "provider_checkboxes",
                options: `
                    <div id="provider-list" style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; min-height:150px; padding:6px; border:1px solid #e2e8f0; border-radius:8px; background:#f8fafc;">
                    </div>
                    <div style="display:flex; justify-content:flex-end; align-items:center; margin-top:8px;">
                        <div id="center-pagination" style="display:flex; align-items:center; gap:8px; font-size:12px;">
                            <button type="button" id="center-prev-btn" class="btn btn-xs btn-default" style="padding:2px 8px; font-size:11px;">
                                &laquo; Prev
                            </button>
                            <span id="center-page-info" style="font-weight:600; color:#475569;">Page 1 of 1</span>
                            <button type="button" id="center-next-btn" class="btn btn-xs btn-default" style="padding:2px 8px; font-size:11px;">
                                Next &raquo;
                            </button>
                        </div>
                    </div>
                `
            },
            { fieldtype: 'Section Break', label: __('Select Applicants') },
            {
                label: __("Auto-select (Enter Number)"),
                fieldname: "auto_select_count",
                fieldtype: "Int",
                description: __("Enter count to automatically select first N unallocated students")
            },
            { fieldtype: "Section Break" },
            { fieldtype: 'HTML', fieldname: 'applicants_html' }
        ],
        primary_action_label: __('Reject and Allocate'),
        primary_action(values) {
            const selected_applicants = Array.from(selected_applicant_names);
            const selected_providers_array = Array.from(selected_provider_names);

            if (!selected_applicants.length) {
                frappe.msgprint(__('Please select at least one applicant.'));
                return;
            }
            if (values.allocation_type === "Allocate Directly" && !selected_providers_array.length) {
                frappe.msgprint(__('Please select at least one provider (test centre).'));
                return;
            }

            const confirm_dialog = new frappe.ui.Dialog({
                title: __('Confirm Re-allocation'),
                size: "large",
                fields: [
                    {
                        fieldtype: "HTML",
                        fieldname: "confirm_html",
                        options: `
                            <div style="background:#f8fafc; border:1.5px solid #cbd5e1; border-radius:10px; padding:14px 18px; margin-bottom:16px;">
                                <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                                    <span style="font-size:15px; font-weight:700; color:#1e293b;">
                                        Confirm Re-allocation Process
                                    </span>
                                    <span style="font-size:11px; background:#e0e7ff; color:#3730a3; padding:2px 8px; border-radius:4px; font-weight:600; margin-left:auto;">
                                        ${values.allocation_type}
                                    </span>
                                </div>
                                <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:13px; color:#334155;">
                                    <div>
                                        <span style="font-weight:600;">Total Applicants Selected:</span>
                                        <span style="font-weight:700; color:#1e40af; font-size:14px; margin-left:4px;">${selected_applicants.length}</span>
                                    </div>
                                    <div>
                                        <span style="font-weight:600;">Centres Selected:</span>
                                        <span style="font-weight:700; color:#6d28d9; font-size:14px; margin-left:4px;">${selected_providers_array.length}</span>
                                    </div>
                                </div>
                            </div>
                            <div style="background:#fff7ed; border:1px solid #ffedd5; padding:10px 14px; border-radius:8px; font-size:12px; color:#9a3412;">
                                <b>Note:</b> This will update the existing allocation records to reflect the new centre(s). The old centre capacity will be restored.
                            </div>
                        `
                    }
                ],
                primary_action_label: __('Confirm & Re-allocate'),
                primary_action: function () {
                    confirm_dialog.hide();
                    frappe.call({
                        method: 'slcm.admission.doctype.entrance_test_seat_allocation.entrance_test_seat_allocation.reject_and_allocate_applicants',
                        args: {
                            applicants: selected_applicants,
                            providers: selected_providers_array
                        },
                        freeze: true,
                        freeze_message: __('Re-allocating...'),
                        callback: function (r) {
                            if (!r.exc) {
                                d.hide();
                                listview.refresh();
                                frappe.show_alert({ message: __('Successfully re-allocated {0} applicants.', [selected_applicants.length]), indicator: 'green' });
                            }
                        }
                    });
                },
                secondary_action_label: __("Cancel"),
                secondary_action: function () {
                    confirm_dialog.hide();
                }
            });
            confirm_dialog.show();
        }
    });

    d.show();

    // Initial render for providers
    render_center_page();

    // Provider events
    d.$wrapper.on("input", "#center-search-input", function () {
        search_center_query = $(this).val();
        center_current_page = 1;
        render_center_page();
    });

    d.$wrapper.on("change", "#center-pwd-filter-chk", function () {
        center_pwd_only = this.checked;
        center_current_page = 1;
        render_center_page();
    });

    d.$wrapper.on("click", "#center-clear-all-btn", function () {
        selected_provider_names.clear();
        render_center_page();
    });

    d.$wrapper.on("click", "#center-prev-btn", function () {
        if (center_current_page > 1) {
            center_current_page--;
            render_center_page();
        }
    });

    d.$wrapper.on("click", "#center-next-btn", function () {
        const filtered = get_filtered_providers();
        const total_pages = Math.ceil(filtered.length / center_page_size) || 1;
        if (center_current_page < total_pages) {
            center_current_page++;
            render_center_page();
        }
    });

    d.$wrapper.on("change", ".provider-checkbox", function () {
        const name = $(this).data("name");
        if (this.checked) {
            selected_provider_names.add(name);
        } else {
            selected_provider_names.delete(name);
        }
        render_center_page(); // re-render to update selected styling
    });

    d.$wrapper.on("change", "#center-select-all-chk", function () {
        const filtered = get_filtered_providers();
        if (this.checked) {
            filtered.forEach(p => selected_provider_names.add(p.name));
        } else {
            filtered.forEach(p => selected_provider_names.delete(p.name));
        }
        render_center_page();
    });


    // Applicant Events
    d.$wrapper.on("input", "#filter-applicant-id", function () { applicant_filters.applicant_id = $(this).val().toLowerCase().trim(); applicant_current_page = 1; render_applicant_page(); });
    d.$wrapper.on("input", "#filter-candidate-name", function () { applicant_filters.candidate_name = $(this).val().toLowerCase().trim(); applicant_current_page = 1; render_applicant_page(); });
    d.$wrapper.on("input", "#filter-programme", function () { applicant_filters.programme = $(this).val().toLowerCase().trim(); applicant_current_page = 1; render_applicant_page(); });
    d.$wrapper.on("input", "#filter-entrance-test-city", function () { applicant_filters.entrance_test_city = $(this).val().toLowerCase().trim(); applicant_current_page = 1; render_applicant_page(); });
    d.$wrapper.on("input", "#filter-old-centre", function () { applicant_filters.old_centre = $(this).val().toLowerCase().trim(); applicant_current_page = 1; render_applicant_page(); });
    d.$wrapper.on("change", "#pwd-applicant-filter-chk", function () { applicant_filters.pwd_only = this.checked; applicant_current_page = 1; render_applicant_page(); });
    d.$wrapper.on("click", "#applicant-clear-all-btn", function () { selected_applicant_names.clear(); render_applicant_page(); });
    d.$wrapper.on("click", "#applicant-prev-btn", function () { if (applicant_current_page > 1) { applicant_current_page--; render_applicant_page(); } });
    d.$wrapper.on("click", "#applicant-next-btn", function () { const filtered = get_filtered_applicants(); const total_pages = Math.ceil(filtered.length / applicant_page_size) || 1; if (applicant_current_page < total_pages) { applicant_current_page++; render_applicant_page(); } });
    d.$wrapper.on("change", ".applicant-checkbox", function () { const name = $(this).data("name"); if (this.checked) selected_applicant_names.add(name); else selected_applicant_names.delete(name); update_applicant_counts(get_filtered_applicants().length); });
    d.$wrapper.on("change", "#select-all-chk", function () { const filtered = get_filtered_applicants(); if (this.checked) filtered.forEach(a => selected_applicant_names.add(a.name)); else filtered.forEach(a => selected_applicant_names.delete(a.name)); render_applicant_page(); });

    // Handle auto select count
    d.fields_dict.auto_select_count.df.onchange = function() {
        const count = d.get_value("auto_select_count");
        if (count > 0) {
            const filtered = get_filtered_applicants();
            selected_applicant_names.clear();
            for (let i = 0; i < Math.min(count, filtered.length); i++) {
                selected_applicant_names.add(filtered[i].name);
            }
            render_applicant_page();
        }
    };

    function fetch_applicants() {
        const filters = {};
        if (d.get_value('filter_allocation_status')) filters.allocation_status = d.get_value('filter_allocation_status');
        if (d.get_value('filter_entrance_test_status')) filters.entrance_test_status = d.get_value('filter_entrance_test_status');

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Entrance Test Seat Allocation',
                filters: filters,
                fields: ['name', 'candidate_name', 'applicant', 'program', 'pwd', 'center_name', 'entrance_test_list.entrance_test_city'],
                limit_page_length: 0
            },
            callback: function (r) {
                applicants = r.message || [];
                selected_applicant_names.clear();
                applicant_current_page = 1;

                let html = `
                    <div style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; gap:12px; align-items:center;">
                            <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px;">
                                <input type="checkbox" id="select-all-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;">
                                Select All Applicants
                            </label>
                            <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px; margin-left:12px;">
                                <input type="checkbox" id="pwd-applicant-filter-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;" ${applicant_filters.pwd_only ? 'checked' : ''}>
                                ♿ PWD
                            </label>
                            <button type="button" id="applicant-clear-all-btn" class="btn btn-xs btn-default" style="font-size:11px; padding:2px 8px; border-radius:4px;">Clear All</button>
                            <span id="sel-count" style="color:#6c757d; font-size:12px; font-weight:500;">0 of ${applicants.length} selected</span>
                        </div>
                        <div id="applicant-pagination" style="display:flex; align-items:center; gap:8px; font-size:12px;">
                            <button type="button" id="applicant-prev-btn" class="btn btn-xs btn-default" style="padding:2px 8px; font-size:11px;">&laquo; Prev</button>
                            <span id="applicant-page-info" style="font-weight:600; color:#475569;">Page 1 of 1</span>
                            <button type="button" id="applicant-next-btn" class="btn btn-xs btn-default" style="padding:2px 8px; font-size:11px;">Next &raquo;</button>
                        </div>
                    </div>
                    <div style="border:1px solid #d1d8dd; border-radius:8px; overflow:hidden; background:#ffffff;">
                        <table class="table table-bordered table-hover" style="margin:0; font-size:13px; width:100%;">
                            <thead style="background:#f8fafc;">
                                <tr>
                                    <th style="width:40px; text-align:center; vertical-align:middle; padding:8px 4px;"></th>
                                    <th style="width:60px; text-align:center; color:#3b82f6; vertical-align:middle; padding:8px 4px; font-weight:600;">No.</th>
                                    <th style="width:20%; color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Applicant ID</th>
                                    <th style="width:25%; color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Candidate Name</th>
                                    <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Programme</th>
                                    <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Entrance Test City</th>
                                    <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Old Centre Name</th>
                                </tr>
                                <tr style="background:#f1f5f9;">
                                    <th style="padding:4px 6px; text-align:center;"></th>
                                    <th style="padding:4px 6px; text-align:center;"></th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-applicant-id" placeholder="${__("Filter ID...")}" value="${applicant_filters.applicant_id}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff;">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-candidate-name" placeholder="${__("Filter Name...")}" value="${applicant_filters.candidate_name}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff;">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-programme" placeholder="${__("Filter Programme...")}" value="${applicant_filters.programme}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff;">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-entrance-test-city" placeholder="${__("Filter City...")}" value="${applicant_filters.entrance_test_city || ''}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff;">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-old-centre" placeholder="${__("Filter Old Centre...")}" value="${applicant_filters.old_centre || ''}"
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff;">
                                    </th>
                                </tr>
                            </thead>
                            <tbody id="rej-applicant-table-body"></tbody>
                        </table>
                    </div>`;
                
                d.get_field('applicants_html').$wrapper.html(html);
                render_applicant_page();
            }
        });
    }

    fetch_applicants();
}
