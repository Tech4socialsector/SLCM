frappe.ui.form.on("Entrance Test List", {
    refresh: function (frm) {
        // Hide button only if user is strictly an Entrance Test Provider (and not an Admin/Manager)
        let is_provider_only = frappe.user_roles.includes("Entrance Test Provider") && 
                               !frappe.user_roles.includes("System Manager") && 
                               !frappe.user_roles.includes("Entrance Test Admin") &&
                               !frappe.user_roles.includes("Interview Admin");

        if (frm.doc.status === "Generated" && !is_provider_only) {
            frm.add_custom_button(__("Allocate Seats"), function () {
                open_allocation_dialog(frm);
            }, __("Actions"));
            
            frm.add_custom_button(__("Generate Preference"), function () {
                open_generate_preference_dialog(frm);
            }, __("Actions"));
        }
    }
});

function open_allocation_dialog(frm) {
    const all_applicants = frm.doc.entrance_test_applicant || [];
    const applicants = all_applicants.filter(a => a.allocation_status === "Not Allocated");

    if (!applicants.length) {
        const total = all_applicants.length;
        if (total === 0) {
            frappe.msgprint({
                title: __("No Applicants Found"),
                message: __("This Entrance Test List is empty. Please ensure applicants are added before attempting allocation."),
                indicator: "orange"
            });
        } else {
            frappe.msgprint({
                title: __("Allocation Already Completed"),
                message: __("All <b>{0}</b> applicants in this list have already been successfully allocated seats or converted to their next preference. <br><br>The system has verified that there are no pending students left for seat allocation in this list. If you need to allocate new students, please add them to this list or generate a new one.", [total]),
                indicator: "blue"
            });
        }
        return;
    }

    // Fetch all active Entrance Test Providers with available capacity for this city (or campus fallback)
    const provider_filters = { 
        active: 1, 
        available_capacity: [">", 0]
    };
    if (frm.doc.entrance_test_city) {
        provider_filters.city = frm.doc.entrance_test_city;
    } else if (frm.doc.campus) {
        provider_filters.campus = frm.doc.campus;
    }

    frappe.call({
        method: "slcm.admission.doctype.entrance_test_list.entrance_test_list.get_providers_with_capacity",
        args: {
            city: frm.doc.entrance_test_city || "",
            campus: frm.doc.campus || ""
        },
        callback: function (r) {
            const providers = r.message || [];
            if (!providers.length) {
                const target_label = frm.doc.entrance_test_city ? __("city '{0}'", [frm.doc.entrance_test_city]) : __("campus '{0}'", [frm.doc.campus]);
                frappe.msgprint({
                    title: __("No Available Providers"),
                    message: __("No active Entrance Test Providers found for {0}.", [target_label]),
                    indicator: "orange"
                });
                return;
            }
            _show_allocation_dialog(frm, applicants, providers);
        }
    });
}

function _show_allocation_dialog(frm, applicants, providers) {
    const selected_provider_names = new Set();
    const selected_applicant_names = new Set();

    let search_center_query = "";
    let center_pwd_only = false;
    let center_current_page = 1;
    const center_page_size = 9;

    let applicant_current_page = 1;
    const applicant_page_size = 10;

    function get_filtered_providers() {
        let list = providers;
        if (center_pwd_only) {
            list = list.filter(p => p.pwd_accessible == 1);
        }
        if (!search_center_query) return list;
        const q = search_center_query.toLowerCase().trim();
        return list.filter(p => {
            const name = (p.center_name || p.name).toLowerCase();
            const addr = (p.center_address || "").toLowerCase();
            return name.includes(q) || addr.includes(q);
        });
    }

    let d = new frappe.ui.Dialog({
        title: __("Allocate Seats"),
        size: "extra-large",
        fields: [
            {
                label: __("Allocate Type"),
                fieldname: "allocation_type",
                fieldtype: "Select",
                options: [
                    "Allocate Directly",
                    "Allow Applicant Selection"
                ],
                default: "Allocate Directly",
                reqd: 1,
                onchange: function() {
                    update_allocation_type_ui();
                }
            },
            {
                fieldtype: "Column Break"
            },
            {
                label: __("Entrance Test City"),
                fieldname: "entrance_test_city",
                fieldtype: "Link",
                options: "Entrance Test City",
                default: frm.doc.entrance_test_city || "",
                onchange: function() {
                    fetch_and_render_providers();
                }
            },
            {
                label: __("Check Available Seats By Programme"),
                fieldname: "check_available_seats_by_programme",
                fieldtype: "Link",
                options: "Programme",
                onchange: function() {
                    fetch_and_render_providers();
                }
            },
            {
                fieldtype: "Section Break"
            },
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
                            Total Centres: ${providers.length} | 0 selected
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
            {
                label: __("Select Applicants"),
                fieldtype: "Section Break"
            },
            {
                label: __("Auto-select (Enter Number)"),
                fieldname: "auto_select_count",
                fieldtype: "Int",
                description: __("Enter count to automatically select first N unallocated students")
            },
            {
                fieldtype: "Section Break"
            },
            {
                fieldtype: "HTML",
                fieldname: "applicant_table",
                options: `
                    <div style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                        <div style="display:flex; gap:12px; align-items:center;">
                            <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px;">
                                <input type="checkbox" id="select-all-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;">
                                Select All Applicants
                            </label>
                            <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px; margin-left:12px;" title="Filter PWD Applicants">
                                <input type="checkbox" id="pwd-applicant-filter-chk" style="width:15px; height:15px; cursor:pointer; margin-right:6px;">
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
                        <table class="table table-bordered table-hover" 
                               style="margin:0; font-size:13px; width:100%;">
                            <thead style="background:#f8fafc;">
                                <tr>
                                    <th style="width:40px; text-align:center; vertical-align:middle; padding:8px 4px;"></th>
                                    <th style="width:60px; text-align:center; color:#3b82f6; vertical-align:middle; padding:8px 4px; font-weight:600;">No.</th>
                                    <th style="width:25%; color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Applicant ID</th>
                                    <th style="width:35%; color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Candidate Name</th>
                                    <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Programme Level</th>
                                    <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Programme</th>
                                </tr>
                                <tr style="background:#f1f5f9;">
                                    <th style="padding:4px 6px; text-align:center;"></th>
                                    <th style="padding:4px 6px; text-align:center;"></th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-applicant-id" placeholder="${__("Filter ID...")}" 
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-candidate-name" placeholder="${__("Filter Name...")}" 
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-programme-level" placeholder="${__("Filter Level...")}" 
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                    <th style="padding:4px 6px;">
                                        <input type="text" id="filter-programme" placeholder="${__("Filter Programme...")}" 
                                               style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; font-weight:normal; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                    </th>
                                </tr>
                            </thead>
                            <tbody id="applicant-table-body"></tbody>
                        </table>
                    </div>
                `
            }
        ],
        primary_action_label: __("Allocate Seats"),
        primary_action(values) {
            const allocation_type = values.allocation_type || "Allocate Directly";

            if (!selected_provider_names.size) {
                frappe.msgprint(__("Please select at least one Entrance Test Provider."));
                return;
            }

            if (allocation_type === "Allocate Directly" && selected_provider_names.size > 1) {
                frappe.msgprint(__("For 'Allocate Directly', please select only one Entrance Test Centre."));
                return;
            }

            if (!selected_applicant_names.size) {
                frappe.msgprint(__("Please select at least one applicant."));
                return;
            }

            const selected_providers = Array.from(selected_provider_names);
            const selected_applicants = Array.from(selected_applicant_names);

            // Check seat availability first and show confirmation dialog for both types
            frappe.call({
                method: "check_seat_availability",
                doc: frm.doc,
                args: {
                    providers: selected_providers,
                    selected_applicants: selected_applicants,
                    allocation_type: allocation_type
                },
                freeze: true,
                freeze_message: __("Checking seat availability..."),
                callback: function (r) {
                    if (r.exc) return;
                    const result = r.message;
                    if (!result.can_allocate) {
                        frappe.msgprint({
                            title: __("Cannot Allocate"),
                            message: result.error || __("Unable to process allocation."),
                            indicator: "red"
                        });
                        return;
                    }
                    _show_allocation_confirmation(frm, d, result, selected_providers, selected_applicants, allocation_type);
                }
            });
        }
    });

    d.show();
    const $wrapper = d.$wrapper;

    function render_center_page() {
        const list = get_filtered_providers();
        const total_pages = Math.ceil(list.length / center_page_size) || 1;
        if (center_current_page > total_pages) center_current_page = total_pages;
        if (center_current_page < 1) center_current_page = 1;

        const start = (center_current_page - 1) * center_page_size;
        const page_items = list.slice(start, start + center_page_size);

        if (!page_items.length) {
            $wrapper.find("#provider-list").html(`
                <div style="grid-column: 1 / -1; text-align:center; padding:25px; color:#94a3b8; font-size:13px;">
                    No centres found matching search.
                </div>
            `);
        } else {
            const html = page_items.map(p => {
                const is_checked = selected_provider_names.has(p.name);
                const border_col = is_checked ? "#2da44e" : "#cbd5e1";
                const bg_col = is_checked ? "#f0fdf4" : "#ffffff";
                const box_shadow = is_checked ? "0 2px 6px rgba(45,164,78,0.15)" : "0 1px 2px rgba(0,0,0,0.04)";

                return `
                    <label class="provider-card"
                           data-name="${p.name}"
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
                                ${p.pwd_accessible ? `<span style="font-size:10px; background:#dbeafe; color:#1e40af; padding:1px 5px; border-radius:4px; margin-left:4px; font-weight:600;">♿ PWD</span>` : ''}
                                <span style="font-size:10px; background:${(p.available_capacity || 0) > 0 ? '#dcfce7' : '#fee2e2'}; color:${(p.available_capacity || 0) > 0 ? '#166534' : '#991b1b'}; padding:1px 5px; border-radius:4px; margin-left:4px; font-weight:600;">available seat: ${p.available_capacity || 0}</span>
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
        const sel_count = selected_provider_names.size;
        const total_count = providers.length;
        const filtered_count = get_filtered_providers().length;
        if (center_pwd_only || search_center_query) {
            $wrapper.find("#provider-sel-count").text(`Centres: ${filtered_count} of ${total_count} | ${sel_count} selected`);
        } else {
            $wrapper.find("#provider-sel-count").text(`Total Centres: ${total_count} | ${sel_count} selected`);
        }
        const all_selected = filtered_count > 0 && sel_count === filtered_count;
        $wrapper.find("#center-select-all-chk").prop("checked", all_selected);
    }

    let applicant_filters = {
        applicant_id: "",
        candidate_name: "",
        programme_level: "",
        programme: "",
        pwd_only: false
    };

    function get_filtered_applicants() {
        return applicants.filter(a => {
            const id_match = !applicant_filters.applicant_id || (a.applicant_id || "").toLowerCase().includes(applicant_filters.applicant_id);
            const name_match = !applicant_filters.candidate_name || (a.candidate_name || "").toLowerCase().includes(applicant_filters.candidate_name);
            const level_match = !applicant_filters.programme_level || (a.program_level || "").toLowerCase().includes(applicant_filters.programme_level);
            const prog_match = !applicant_filters.programme || (a.program || "").toLowerCase().includes(applicant_filters.programme);
            
            let pwd_match = true;
            if (applicant_filters.pwd_only) {
                pwd_match = (a.pwd == 1 || (a.pwd || "").toString().toLowerCase() === "yes");
            }
            
            return id_match && name_match && level_match && prog_match && pwd_match;
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
            $wrapper.find("#applicant-table-body").html(`
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
                        <td style="vertical-align:middle;">${row.applicant_id || "-"}</td>
                        <td style="vertical-align:middle;">
                            <b>${row.candidate_name || "Unknown"}</b>
                            ${(row.pwd == 1 || (row.pwd || "").toString().toLowerCase() === "yes") ? `<span style="font-size:10px; background:#fef3c7; color:#92400e; padding:1px 5px; border-radius:4px; margin-left:4px; border:1px solid #fde68a; font-weight:700;">♿ PWD</span>` : ''}
                        </td>
                        <td style="vertical-align:middle;">${row.program_level || "-"}</td>
                        <td style="vertical-align:middle;">${row.program || "-"}</td>
                    </tr>
                `;
            }).join("");

            $wrapper.find("#applicant-table-body").html(rows_html);
        }

        $wrapper.find("#applicant-page-info").text(`Page ${applicant_current_page} of ${total_pages}`);
        $wrapper.find("#applicant-prev-btn").prop("disabled", applicant_current_page <= 1);
        $wrapper.find("#applicant-next-btn").prop("disabled", applicant_current_page >= total_pages);

        update_applicant_counts(filtered.length);
    }

    function update_applicant_counts(filtered_length) {
        const sel_count = selected_applicant_names.size;
        const total_count = applicants.length;
        if (filtered_length !== undefined && filtered_length !== total_count) {
            $wrapper.find("#sel-count").text(`${sel_count} of ${total_count} selected (Filtered: ${filtered_length})`);
        } else {
            $wrapper.find("#sel-count").text(`${sel_count} of ${total_count} selected`);
        }
        const all_selected = total_count > 0 && sel_count === total_count;
        $wrapper.find("#select-all-chk").prop("checked", all_selected);
    }

    function update_allocation_type_ui() {
        const alloc_type = d ? d.get_value("allocation_type") : "Allocate Directly";
        if (alloc_type === "Allocate Directly") {
            if (selected_provider_names.size > 1) {
                const first = Array.from(selected_provider_names)[0];
                selected_provider_names.clear();
                selected_provider_names.add(first);
            }
            $wrapper.find("#center-select-all-chk").prop("disabled", true).prop("checked", false);
            $wrapper.find("#center-select-all-chk").closest("label").css("opacity", "0.4").css("pointer-events", "none");
        } else {
            $wrapper.find("#center-select-all-chk").prop("disabled", false);
            $wrapper.find("#center-select-all-chk").closest("label").css("opacity", "1.0").css("pointer-events", "auto");
        }
        render_center_page();
    }

    function fetch_and_render_providers() {
        const city_name = d ? d.get_value("entrance_test_city") : frm.doc.entrance_test_city;
        const prog_name = d ? d.get_value("check_available_seats_by_programme") : "";

        frappe.call({
            method: "slcm.admission.doctype.entrance_test_list.entrance_test_list.get_providers_with_capacity",
            args: {
                city: city_name || "",
                campus: (!city_name && frm.doc.campus) ? frm.doc.campus : "",
                programme: prog_name || ""
            },
            callback: function (r) {
                providers = r.message || [];
                selected_provider_names.clear();
                center_current_page = 1;
                update_allocation_type_ui();
            }
        });
    }

    // Initial renders
    render_center_page();
    render_applicant_page();
    update_allocation_type_ui();

    // Event Bindings
    $wrapper.find("#center-search-input").on("input keyup search", function () {
        search_center_query = $(this).val();
        center_current_page = 1;
        render_center_page();
    });

    $wrapper.find("#center-pwd-filter-chk").on("change", function () {
        center_pwd_only = this.checked;
        center_current_page = 1;
        render_center_page();
    });

    $wrapper.on("change", ".provider-checkbox", function () {
        const name = $(this).attr("data-name");
        const alloc_type = d ? d.get_value("allocation_type") : "Allocate Directly";

        if (alloc_type === "Allocate Directly") {
            if (this.checked) {
                selected_provider_names.clear();
                selected_provider_names.add(name);
            } else {
                selected_provider_names.delete(name);
            }
            render_center_page();
        } else {
            if (this.checked) {
                selected_provider_names.add(name);
            } else {
                selected_provider_names.delete(name);
            }
            const $card = $(this).closest(".provider-card");
            if (this.checked) {
                $card.css({
                    "border-color": "#2da44e",
                    "background-color": "#f0fdf4",
                    "box-shadow": "0 2px 6px rgba(45,164,78,0.15)"
                });
            } else {
                $card.css({
                    "border-color": "#cbd5e1",
                    "background-color": "#ffffff",
                    "box-shadow": "0 1px 2px rgba(0,0,0,0.04)"
                });
            }
            update_center_counts();
        }
    });

    $wrapper.find("#center-select-all-chk").on("change", function () {
        if (this.checked) {
            providers.forEach(p => selected_provider_names.add(p.name));
        } else {
            selected_provider_names.clear();
        }
        render_center_page();
    });

    $wrapper.find("#center-clear-all-btn").on("click", function () {
        selected_provider_names.clear();
        $wrapper.find("#center-select-all-chk").prop("checked", false);
        render_center_page();
    });

    $wrapper.find("#center-prev-btn").on("click", function () {
        if (center_current_page > 1) {
            center_current_page--;
            render_center_page();
        }
    });

    $wrapper.find("#center-next-btn").on("click", function () {
        const list = get_filtered_providers();
        const total_pages = Math.ceil(list.length / center_page_size) || 1;
        if (center_current_page < total_pages) {
            center_current_page++;
            render_center_page();
        }
    });

    $wrapper.find("#pwd-applicant-filter-chk").on("change", function () {
        applicant_filters.pwd_only = this.checked;
        applicant_current_page = 1;
        render_applicant_page();
    });

    $wrapper.on("input keyup search", "#filter-applicant-id, #filter-candidate-name, #filter-programme-level, #filter-programme", function () {
        applicant_filters.applicant_id = $wrapper.find("#filter-applicant-id").val().toLowerCase().trim();
        applicant_filters.candidate_name = $wrapper.find("#filter-candidate-name").val().toLowerCase().trim();
        applicant_filters.programme_level = $wrapper.find("#filter-programme-level").val().toLowerCase().trim();
        applicant_filters.programme = $wrapper.find("#filter-programme").val().toLowerCase().trim();
        applicant_current_page = 1;
        render_applicant_page();
    });

    $wrapper.on("change", ".applicant-checkbox", function () {
        const name = $(this).attr("data-name");
        if (this.checked) {
            selected_applicant_names.add(name);
        } else {
            selected_applicant_names.delete(name);
        }
        const filtered_len = get_filtered_applicants().length;
        update_applicant_counts(filtered_len);
    });

    $wrapper.find("#select-all-chk").on("change", function () {
        if (this.checked) {
            applicants.forEach(a => selected_applicant_names.add(a.name));
        } else {
            selected_applicant_names.clear();
        }
        render_applicant_page();
    });

    $wrapper.find("#applicant-clear-all-btn").on("click", function () {
        selected_applicant_names.clear();
        $wrapper.find("#select-all-chk").prop("checked", false);
        render_applicant_page();
    });

    $wrapper.find("#applicant-prev-btn").on("click", function () {
        if (applicant_current_page > 1) {
            applicant_current_page--;
            render_applicant_page();
        }
    });

    $wrapper.find("#applicant-next-btn").on("click", function () {
        const list = get_filtered_applicants();
        const total_pages = Math.ceil(list.length / applicant_page_size) || 1;
        if (applicant_current_page < total_pages) {
            applicant_current_page++;
            render_applicant_page();
        }
    });

    d.fields_dict.auto_select_count.$input.on("input", function () {
        let val = parseInt($(this).val()) || 0;
        selected_applicant_names.clear();
        applicants.slice(0, val).forEach(a => selected_applicant_names.add(a.name));
        render_applicant_page();
    });
}

function _show_allocation_confirmation(frm, parent_dialog, result, selected_providers, selected_applicants, allocation_type) {
    const total = result.total_selected || 0;
    const total_avail = result.effective_total_available != null ? result.effective_total_available : (result.total_available_seats || 0);
    const breakdown = result.programme_breakdown || [];
    const centres = result.centre_details || [];
    const has_shortage = result.has_programme_shortage || false;
    const overall_sufficient = result.overall_sufficient || false;
    const total_pwd = result.total_pwd || 0;
    const has_pwd_centre = result.has_pwd_centre || false;
    const pwd_conflict = result.pwd_conflict || false;
    const pwd_applicants = result.pwd_applicants || [];
    const is_direct = allocation_type === "Allocate Directly";

    // Build the summary header
    const has_issues = !overall_sufficient || pwd_conflict;
    const overall_color = has_issues ? "#dc2626" : "#16a34a";
    const overall_bg = has_issues ? "#fef2f2" : "#f0fdf4";
    const overall_border = has_issues ? "#fecaca" : "#bbf7d0";
    const status_msg = !overall_sufficient ? 'Seat Shortage Detected' : pwd_conflict ? 'PWD Accessibility Conflict Detected' : 'Seats Available — Ready to Allocate';

    let pwd_summary = '';
    if (total_pwd > 0) {
        pwd_summary = `
                <div>
                    <span style="font-weight:600;">♿ PWD Applicants:</span>
                    <span style="font-weight:700; color:${pwd_conflict ? '#dc2626' : '#0f766e'}; font-size:14px; margin-left:4px;">${total_pwd}</span>
                    ${pwd_conflict ? '<span style="font-size:11px; background:#fee2e2; color:#991b1b; padding:2px 6px; border-radius:4px; margin-left:6px; font-weight:600;">No PWD Centre Selected!</span>' : ''}
                </div>`;
    }

    // For "Allocate Directly" show the actual centre name; for multi-centre show count
    let centre_info_html = '';
    let avail_label = '';
    if (is_direct && centres.length === 1) {
        const c = centres[0];
        const pwd_tag = c.pwd_accessible ? '<span style="font-size:9px; background:#dbeafe; color:#1e40af; padding:1px 5px; border-radius:3px; margin-left:4px; font-weight:600;">♿ PWD</span>' : '';
        centre_info_html = `
                <div>
                    <span style="font-weight:600;">Selected Centre:</span>
                    <span style="font-weight:700; color:#6d28d9; font-size:13px; margin-left:4px;">${c.center_name}</span>${pwd_tag}
                </div>`;
        avail_label = `Available Seats at ${c.center_name}:`;
    } else {
        centre_info_html = `
                <div>
                    <span style="font-weight:600;">Centres Selected:</span>
                    <span style="font-weight:700; color:#6d28d9; font-size:14px; margin-left:4px;">${centres.length}</span>
                </div>`;
        avail_label = `Total Available Seats (All Centres):`;
    }

    let summary_html = `
        <div style="background:${overall_bg}; border:1.5px solid ${overall_border}; border-radius:10px; padding:14px 18px; margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                <span style="font-size:15px; font-weight:700; color:${overall_color};">
                    ${status_msg}
                </span>
                <span style="font-size:11px; background:#e0e7ff; color:#3730a3; padding:2px 8px; border-radius:4px; font-weight:600; margin-left:auto;">
                    ${is_direct ? 'Allocate Directly' : 'Allow Applicant Selection'}
                </span>
            </div>
            <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:13px; color:#334155;">
                <div>
                    <span style="font-weight:600;">Total Applicants Selected:</span>
                    <span style="font-weight:700; color:#1e40af; font-size:14px; margin-left:4px;">${total}</span>
                </div>
                <div>
                    <span style="font-weight:600;">${avail_label}</span>
                    <span style="font-weight:700; color:${total_avail >= total ? '#16a34a' : '#dc2626'}; font-size:14px; margin-left:4px;">${total_avail}</span>
                </div>
                ${centre_info_html}
                ${pwd_summary}
            </div>
        </div>
    `;

    // Build programme-wise breakdown table
    let programme_rows = "";
    breakdown.forEach(prog => {
        const status_bg = prog.sufficient ? "#dcfce7" : "#fee2e2";
        const status_color = prog.sufficient ? "#166534" : "#991b1b";
        const status_text = prog.sufficient ? "Sufficient" : `Shortage: ${prog.shortage}`;

        // Build centre-wise availability cells
        let centre_cells = "";
        centres.forEach(cd => {
            const prog_cd = (prog.centre_details || []).find(c => c.center_name === cd.center_name);
            if (prog_cd) {
                const avail_color = prog_cd.available > 0 ? "#16a34a" : "#dc2626";
                centre_cells += `
                    <td class="centre-cell-click" data-center-id="${cd.provider}" style="text-align:center; padding:8px 10px; border-bottom:1px solid #e2e8f0; font-size:12px; vertical-align:middle; cursor:pointer;" title="Click to view centre details">
                        <span style="font-weight:700; color:${avail_color};">${prog_cd.available}</span>
                        <span style="color:#94a3b8; font-size:10px;"> / ${prog_cd.capacity}</span>
                    </td>
                `;
            } else {
                centre_cells += `
                    <td class="centre-cell-click" data-center-id="${cd.provider}" style="text-align:center; padding:8px 10px; border-bottom:1px solid #e2e8f0; font-size:12px; color:#94a3b8; vertical-align:middle; cursor:pointer;" title="Click to view centre details">
                        —
                    </td>
                `;
            }
        });

        programme_rows += `
            <tr>
                <td style="padding:8px 12px; font-weight:600; color:#1e293b; border-bottom:1px solid #e2e8f0; font-size:13px; vertical-align:middle; white-space:nowrap;">
                    ${prog.programme}
                    ${(prog.pwd_count || 0) > 0 ? `<span style="font-size:10px; background:#fef3c7; color:#92400e; padding:1px 5px; border-radius:4px; margin-left:4px; border:1px solid #fde68a; font-weight:700;">♿ ${prog.pwd_count} PWD</span>` : ''}
                </td>
                <td style="text-align:center; padding:8px 10px; font-weight:700; color:#1e40af; border-bottom:1px solid #e2e8f0; font-size:14px; vertical-align:middle;">
                    ${prog.applicant_count}
                </td>
                ${centre_cells}
                <td style="text-align:center; padding:8px 10px; font-weight:700; color:#0f766e; border-bottom:1px solid #e2e8f0; font-size:13px; vertical-align:middle;">
                    ${prog.total_available}
                </td>
                <td style="text-align:center; padding:6px 10px; border-bottom:1px solid #e2e8f0; vertical-align:middle;">
                    <span style="display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px; font-weight:700; background:${status_bg}; color:${status_color};">
                        ${status_text}
                    </span>
                </td>
            </tr>
        `;
    });

    // Centre column headers
    let centre_headers = "";
    centres.forEach(cd => {
        const pwd_badge = cd.pwd_accessible ? `<span style="font-size:9px; background:#dbeafe; color:#1e40af; padding:1px 4px; border-radius:3px; margin-left:3px;">♿</span>` : "";
        const name = cd.center_name.length > 18 ? cd.center_name.substring(0, 18) + "…" : cd.center_name;
        centre_headers += `
            <th class="centre-cell-click" data-center-id="${cd.provider}" style="text-align:center; padding:10px 8px; font-weight:600; color:#475569; font-size:11px; border-bottom:2px solid #cbd5e1; white-space:nowrap; vertical-align:middle; cursor:pointer;" title="Click to view ${cd.center_name} details">
                ${name}${pwd_badge}
                <div style="font-size:10px; color:#94a3b8; font-weight:400; margin-top:2px;">
                    Avail / Total
                </div>
            </th>
        `;
    });

    let table_html = `
        <div style="margin-bottom:12px;">
            <div style="font-weight:700; font-size:14px; color:#1e293b; margin-bottom:10px; display:flex; align-items:center; gap:6px;">
                Programme-wise Allocation Breakdown
            </div>
            <div style="border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                <div style="overflow-x:auto;">
                    <table style="width:100%; border-collapse:collapse; font-size:13px; min-width:600px;">
                        <thead>
                            <tr style="background:linear-gradient(135deg, #f8fafc, #f1f5f9);">
                                <th style="text-align:left; padding:10px 12px; font-weight:700; color:#1e293b; font-size:12px; border-bottom:2px solid #cbd5e1; vertical-align:middle;">
                                    Programme
                                </th>
                                <th style="text-align:center; padding:10px 8px; font-weight:700; color:#1e40af; font-size:12px; border-bottom:2px solid #cbd5e1; white-space:nowrap; vertical-align:middle;">
                                    Applicants
                                </th>
                                ${centre_headers}
                                <th style="text-align:center; padding:10px 8px; font-weight:700; color:#0f766e; font-size:12px; border-bottom:2px solid #cbd5e1; white-space:nowrap; vertical-align:middle;">
                                    Total Avail
                                </th>
                                <th style="text-align:center; padding:10px 8px; font-weight:700; color:#475569; font-size:12px; border-bottom:2px solid #cbd5e1; vertical-align:middle;">
                                    Status
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            ${programme_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;

    let centre_summary_html = `
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 14px; margin-top:4px;">
            <div style="font-weight:600; font-size:12px; color:#475569; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                <span>Centre Summary</span>
                <span class="show-all-centres" style="display:none; color:#2563eb; cursor:pointer; font-size:11px; font-weight:700; text-decoration:underline;">Show All Centres</span>
            </div>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
    `;
    centres.forEach(cd => {
        const avail_pct = cd.total_capacity > 0 ? Math.round((cd.available_capacity / cd.total_capacity) * 100) : 0;
        const bar_color = avail_pct > 50 ? "#22c55e" : avail_pct > 20 ? "#eab308" : "#ef4444";
        
        let prog_details_html = '';
        if (cd.programme_capacities && Object.keys(cd.programme_capacities).length > 0) {
            prog_details_html = `<div style="margin-top:8px; border-top:1px dashed #e2e8f0; padding-top:6px;">`;
            for (const [prog_name, caps] of Object.entries(cd.programme_capacities)) {
                prog_details_html += `
                    <div style="display:flex; justify-content:space-between; font-size:10px; color:#475569; margin-bottom:3px;">
                        <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:75%;" title="${prog_name}">${prog_name}</span>
                        <span style="font-weight:600;"><span style="color:${caps.available > 0 ? '#16a34a' : '#dc2626'};">${caps.available}</span> <span style="color:#94a3b8; font-weight:400;">/ ${caps.capacity}</span></span>
                    </div>
                `;
            }
            prog_details_html += `</div>`;
        }

        centre_summary_html += `
            <div class="centre-summary-card" data-center-id="${cd.provider}" style="background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; min-width:180px; flex:1;">
                <div style="font-weight:600; font-size:12px; color:#1e293b; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${cd.center_name}">
                    ${cd.center_name}
                    ${cd.pwd_accessible ? '<span style="font-size:9px; background:#dbeafe; color:#1e40af; padding:1px 4px; border-radius:3px; margin-left:3px;">♿ PWD</span>' : '<span style="font-size:9px; background:#fee2e2; color:#991b1b; padding:1px 4px; border-radius:3px; margin-left:3px;">No PWD</span>'}
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; margin-bottom:3px;">
                    <span>Overall Avail: <b style="color:${bar_color};">${cd.available_capacity}</b></span>
                    <span>Total: <b>${cd.total_capacity}</b></span>
                </div>
                <div style="height:5px; background:#e2e8f0; border-radius:3px; overflow:hidden;">
                    <div style="height:100%; width:${avail_pct}%; background:${bar_color}; border-radius:3px; transition:width 0.3s;"></div>
                </div>
                ${prog_details_html}
            </div>
        `;
    });
    centre_summary_html += `</div></div>`;

    // Warning notes
    let warning_html = "";
    if (has_shortage) {
        const shortage_msg = is_direct
            ? 'Some programmes have more applicants than available seats. These applicants <b>will not be allocated</b> and will appear in the unallocated list.'
            : 'Some programmes have more applicants than available seats. Applicants will still be assigned preferences, but they may not find available seats when they choose their preferred centre.';
        warning_html += `
            <div style="background:#fef3c7; border:1px solid #fde68a; border-radius:8px; padding:10px 14px; margin-top:10px; font-size:12px; color:#92400e;">
                <b>Seat Shortage:</b> ${shortage_msg}
            </div>
        `;
    }
    if (pwd_conflict) {
        let pwd_list_html = pwd_applicants.map(p => `<li><b>${p.name}</b> (${p.applicant_id}) — ${p.programme}</li>`).join('');
        warning_html += `
            <div style="background:#fee2e2; border:1px solid #fecaca; border-radius:8px; padding:10px 14px; margin-top:10px; font-size:12px; color:#991b1b;">
                <b>♿ PWD Conflict:</b> The following <b>${total_pwd}</b> PWD applicant(s) are selected but <b>none of the chosen centres</b> have PWD accessibility:
                <ul style="margin:6px 0 0 16px; padding:0; list-style-type:disc;">${pwd_list_html}</ul>
                ${is_direct ? '<div style="margin-top:6px; font-weight:700;">These applicants will NOT be allocated and will appear as unallocated.</div>' : '<div style="margin-top:6px; font-weight:700;">These applicants will still receive preferences but may face accessibility issues.</div>'}
            </div>
        `;
    } else if (total_pwd > 0 && has_pwd_centre) {
        warning_html += `
            <div style="background:#dcfce7; border:1px solid #bbf7d0; border-radius:8px; padding:10px 14px; margin-top:10px; font-size:12px; color:#166534;">
                <b>♿ PWD Status:</b> ${total_pwd} PWD applicant(s) found. PWD-accessible centre(s) are available among the selected centres.
            </div>
        `;
    }

    const dialog_title = is_direct ? __("Confirm Allocation — Allocate Directly") : __("Confirm Allocation — Allow Applicant Selection");
    const btn_label = is_direct ? __("Confirm & Allocate Directly") : __("Allocate Centre");

    const confirm_dialog = new frappe.ui.Dialog({
        title: dialog_title,
        size: "extra-large",
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "confirmation_content",
                options: `
                    <div style="font-family:inherit;">
                        ${summary_html}
                        ${table_html}
                        ${centre_summary_html}
                        ${warning_html}
                    </div>
                `
            }
        ],
        primary_action_label: btn_label,
        primary_action: function () {
            confirm_dialog.hide();
            _execute_allocation(frm, parent_dialog, selected_providers, selected_applicants, allocation_type);
        },
        secondary_action_label: __("Cancel"),
        secondary_action: function () {
            confirm_dialog.hide();
        }
    });

    confirm_dialog.$wrapper.find(".modal-dialog").css("max-width", "900px");
    confirm_dialog.show();

    // Attach click events for filtering centre summary
    setTimeout(() => {
        const $wrapper = confirm_dialog.$wrapper;
        
        $wrapper.find(".centre-cell-click").on("click", function() {
            const provider = $(this).attr("data-center-id");
            if (!provider) return;
            
            // Highlight row temporarily
            $wrapper.find(".centre-cell-click").css("background", "transparent");
            $(this).css("background", "#fef9c3").delay(500).queue(function(next) {
                $(this).css("background", "transparent");
                next();
            });

            // Filter cards
            $wrapper.find(".centre-summary-card").hide();
            $wrapper.find(`.centre-summary-card[data-center-id="${provider}"]`).show();
            
            // Show reset button
            $wrapper.find(".show-all-centres").show();
        });

        $wrapper.find(".show-all-centres").on("click", function() {
            $wrapper.find(".centre-summary-card").show();
            $(this).hide();
        });
        
        // Add hover effect via JS since inline hover is messy
        $wrapper.find(".centre-cell-click").hover(
            function() { $(this).css("background-color", "#f1f5f9"); },
            function() { $(this).css("background-color", "transparent"); }
        );
    }, 100);
}

function _execute_allocation(frm, parent_dialog, selected_providers, selected_applicants, allocation_type) {
    frappe.call({
        method: "allocate_seats",
        doc: frm.doc,
        args: {
            providers: selected_providers,
            selected_applicants: selected_applicants,
            allocation_type: allocation_type
        },
        freeze: true,
        freeze_message: __("Allocating Seats..."),
        callback: function (r) {
            if (!r.exc) {
                let res = r.message;
                let count = 0;
                let unallocated = [];

                if (typeof res === "object" && res !== null) {
                    count = res.allocated_count || 0;
                    unallocated = res.unallocated || [];
                } else {
                    count = res || 0;
                }

                if (!document.getElementById("etg-toast-style")) {
                    const style = document.createElement("style");
                    style.id = "etg-toast-style";
                    style.innerHTML = `
                        @keyframes etgSlideDown {
                            from { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                            to   { opacity: 1; transform: translateX(-50%) translateY(0); }
                        }
                        @keyframes etgSlideUp {
                            from { opacity: 1; transform: translateX(-50%) translateY(0); }
                            to   { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                        }
                    `;
                    document.head.appendChild(style);
                }

                const existingToast = document.getElementById("etl-success-toast");
                if (existingToast) existingToast.remove();

                const border_color = unallocated.length > 0 ? "#eab308" : "#2da44e";
                const icon_bg = unallocated.length > 0 ? "#fef9c3" : "#eafbee";
                const icon_text = unallocated.length > 0 ? "⚠️" : "✅";
                const header_color = unallocated.length > 0 ? "#854d0e" : "#1a7f37";

                let unallocated_html = "";
                if (unallocated.length > 0) {
                    unallocated_html = `
                        <div style="margin-top:10px; padding-top:8px; border-top:1px solid #fef08a; font-size:12px; color:#713f12;">
                            <div style="font-weight:700; margin-bottom:4px;">
                                The following applicant(s) could not be allocated:
                            </div>
                            <ul style="margin:0 0 0 16px; padding:0; list-style-type:disc;">
                                ${unallocated.map(u => `<li style="margin-bottom:3px;"><b>${u.name}</b> (${u.applicant_id}): ${u.reason}</li>`).join("")}
                            </ul>
                        </div>
                    `;
                }

                const toast = document.createElement("div");
                toast.id = "etl-success-toast";
                toast.style.cssText = `
                    position: fixed;
                    top: 20px;
                    left: 50%;
                    z-index: 999999;
                    background: #ffffff;
                    border: 1.5px solid ${border_color};
                    border-left: 5px solid ${border_color};
                    border-radius: 10px;
                    padding: 14px 20px;
                    min-width: 400px;
                    max-width: 600px;
                    box-shadow: 0 8px 30px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.10);
                    display: flex;
                    align-items: flex-start;
                    gap: 12px;
                    font-family: inherit;
                    animation: etgSlideDown 0.35s cubic-bezier(.4,0,.2,1) forwards;
                `;
                toast.innerHTML = `
                    <div style="flex-shrink:0; width:36px; height:36px; background:${icon_bg};
                                border-radius:50%; display:flex; align-items:center;
                                justify-content:center; font-size:18px;">${icon_text}</div>
                    <div style="flex:1;">
                        <div style="font-weight:700; font-size:14px; color:${header_color}; margin-bottom:3px;">
                            Allocation Process Summary
                        </div>
                        <div style="font-size:13px; color:#333;">
                            Successfully allocated seats for <b>${count}</b> applicant(s).
                        </div>
                        ${unallocated_html}
                    </div>
                    <span id="etl-success-toast-close"
                          style="cursor:pointer; color:#aaa; font-size:18px; line-height:1;
                                 padding:0 4px; align-self:flex-start; flex-shrink:0;"
                          title="Dismiss">✕</span>
                `;
                document.body.appendChild(toast);

                const dismissSuccessToast = () => {
                    toast.style.animation = "etgSlideUp 0.35s cubic-bezier(.4,0,.2,1) forwards";
                    setTimeout(() => toast.remove(), 350);
                };
                document.getElementById("etl-success-toast-close").addEventListener("click", dismissSuccessToast);
                setTimeout(dismissSuccessToast, unallocated.length > 0 ? 12000 : 6000);

                parent_dialog.hide();
                frm.reload_doc();
            }
        }
    });
}

function open_generate_preference_dialog(frm) {
    frappe.call({
        method: "get_next_preference_applicants",
        doc: frm.doc,
        callback: function (r) {
            const applicants = r.message || [];
            if (!applicants.length) {
                frappe.msgprint({
                    title: __("No Applicants Found"),
                    message: __("There are no 'Not Allocated' applicants with a next preference city."),
                    indicator: "orange"
                });
                return;
            }

            let applicant_filters = { applicant_id: "", candidate_name: "", next_preference: "" };
            let selected_applicant_names = new Set();
            applicants.filter(a => a.has_next).forEach(app => selected_applicant_names.add(app.name));

            function get_filtered_applicants() {
                return applicants.filter(a => {
                    const id_match = !applicant_filters.applicant_id || (a.applicant_id || "").toLowerCase().includes(applicant_filters.applicant_id);
                    const name_match = !applicant_filters.candidate_name || (a.candidate_name || "").toLowerCase().includes(applicant_filters.candidate_name);
                    const pref_match = !applicant_filters.next_preference || (a.next_preference || "").toLowerCase().includes(applicant_filters.next_preference);
                    return id_match && name_match && pref_match;
                });
            }

            function render_applicant_table() {
                const filtered = get_filtered_applicants();
                let rows_html = "";
                
                if (!filtered.length) {
                    rows_html = `
                        <tr>
                            <td colspan="6" style="text-align:center; padding:25px; color:#94a3b8; font-size:13px;">
                                No applicants match the filter criteria.
                            </td>
                        </tr>
                    `;
                } else {
                    rows_html = filtered.map(app => {
                        const is_checked = selected_applicant_names.has(app.name);
                        const has_next = app.has_next;
                        const is_not_exists = app.preference_step === "Not Exists";

                        // Badge styling
                        let badge_style = "";
                        let badge_text = app.preference_step;
                        if (is_not_exists) {
                            badge_style = 'background:#fee2e2; color:#dc2626; border:1px solid #fecaca; font-size:11px; padding:2px 8px; border-radius:4px; font-weight:600;';
                        } else {
                            badge_style = 'background:#dbeafe; color:#2563eb; border:1px solid #bfdbfe; font-size:11px; padding:2px 8px; border-radius:4px; font-weight:600;';
                        }

                        // Next preference display
                        const next_pref_html = has_next
                            ? `<span style="color:#2da44e; font-weight:600;">${app.next_preference}</span>`
                            : `<span style="color:#94a3b8; font-style:italic;">N/A</span>`;

                        // Status indicator for Converted applicants
                        const status_badge = app.allocation_status === "Converted"
                            ? ` <span style="font-size:10px; background:#f0fdf4; color:#16a34a; padding:1px 5px; border-radius:4px; border:1px solid #bbf7d0; font-weight:600;">Converted</span>`
                            : "";

                        return `
                            <tr style="${is_not_exists ? 'opacity:0.7;' : ''}">
                                <td style="text-align:center; vertical-align:middle; width:40px;">
                                    <input type="checkbox" class="pref2-chk" data-name="${app.name}" ${is_checked ? 'checked' : ''} ${!has_next ? 'disabled' : ''}>
                                </td>
                                <td style="vertical-align:middle;">${app.applicant_id}</td>
                                <td style="vertical-align:middle;"><b>${app.candidate_name}</b>${status_badge}</td>
                                <td style="vertical-align:middle;">${app.previous_preference || "-"}</td>
                                <td style="vertical-align:middle;">${next_pref_html}</td>
                                <td style="vertical-align:middle;"><span style="${badge_style}">${badge_text}</span></td>
                            </tr>
                        `;
                    }).join("");
                }
                
                d.$wrapper.find("#generate-applicant-table-body").html(rows_html);
                
                const sel_count = selected_applicant_names.size;
                const selectable_count = applicants.filter(a => a.has_next).length;
                const total_count = applicants.length;
                const filtered_selectable = filtered.filter(a => a.has_next).length;
                if (filtered.length !== total_count) {
                    d.$wrapper.find("#sel-count").text(`${sel_count} of ${selectable_count} selectable selected (Filtered: ${filtered.length} of ${total_count})`);
                } else {
                    d.$wrapper.find("#sel-count").text(`${sel_count} of ${selectable_count} selectable selected`);
                }
                d.$wrapper.find("#pref2-select-all").prop("checked", selectable_count > 0 && sel_count === selectable_count);
            }

            let d = new frappe.ui.Dialog({
                title: __("Generate Preference"),
                size: "large",
                fields: [
                    {
                        fieldtype: "HTML",
                        fieldname: "applicants_html"
                    }
                ],
                primary_action_label: __("Generate"),
                primary_action(values) {
                    d.get_primary_btn().prop("disabled", true);
                    const selected = Array.from(selected_applicant_names);
                    
                    if (!selected.length) {
                        frappe.msgprint(__("Please select at least one applicant."));
                        d.get_primary_btn().prop("disabled", false);
                        return;
                    }

                    frappe.call({
                        method: "generate_next_preference_lists",
                        doc: frm.doc,
                        args: {
                            selected_applicants: selected
                        },
                        callback: function (res) {
                            d.hide();
                            
                            // Success toast logic
                            if (!document.getElementById("etg-toast-style")) {
                                const style = document.createElement("style");
                                style.id = "etg-toast-style";
                                style.innerHTML = `
                                    @keyframes etgSlideDown {
                                        from { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                                        to   { opacity: 1; transform: translateX(-50%) translateY(0); }
                                    }
                                    @keyframes etgSlideUp {
                                        from { opacity: 1; transform: translateX(-50%) translateY(0); }
                                        to   { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                                    }
                                `;
                                document.head.appendChild(style);
                            }

                            const existingToast = document.getElementById("etl-success-toast");
                            if (existingToast) existingToast.remove();

                            const toast = document.createElement("div");
                            toast.id = "etl-success-toast";
                            toast.style.cssText = `
                                position: fixed; top: 20px; left: 50%; z-index: 999999;
                                background: #ffffff; border: 1.5px solid #2da44e; border-left: 5px solid #2da44e;
                                border-radius: 10px; padding: 14px 20px; min-width: 400px;
                                box-shadow: 0 8px 30px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.10);
                                display: flex; align-items: flex-start; gap: 12px;
                                font-family: inherit; animation: etgSlideDown 0.35s cubic-bezier(.4,0,.2,1) forwards;
                            `;
                            toast.innerHTML = `
                                <div style="flex-shrink:0; width:36px; height:36px; background:#eafbee;
                                            border-radius:50%; display:flex; align-items:center;
                                            justify-content:center; font-size:18px;">✅</div>
                                <div style="flex:1;">
                                    <div style="font-weight:700; font-size:14px; color:#1a7f37; margin-bottom:3px;">
                                        Preference Generation Summary
                                    </div>
                                    <div style="font-size:13px; color:#333;">
                                        Successfully generated Entrance Test Lists for <b>${selected.length}</b> applicant(s) for their next preference.
                                    </div>
                                </div>
                                <span id="etl-success-toast-close"
                                      style="cursor:pointer; color:#aaa; font-size:18px; line-height:1;
                                             padding:0 4px; align-self:flex-start; flex-shrink:0;"
                                      title="Dismiss">✕</span>
                            `;
                            document.body.appendChild(toast);

                            const dismissSuccessToast = () => {
                                toast.style.animation = "etgSlideUp 0.35s cubic-bezier(.4,0,.2,1) forwards";
                                setTimeout(() => toast.remove(), 350);
                            };
                            document.getElementById("etl-success-toast-close").addEventListener("click", dismissSuccessToast);
                            setTimeout(dismissSuccessToast, 6000);

                            frm.reload_doc();
                        }
                    });
                }
            });

            let html = `
                <div style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; gap:12px;">
                    <div style="display:flex; gap:12px; align-items:center;">
                        <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center; font-size:13px;">
                            <input type="checkbox" id="pref2-select-all" style="width:15px; height:15px; cursor:pointer; margin-right:6px;" checked>
                            Select All
                        </label>
                        <span id="sel-count" style="color:#6c757d; font-size:12px; font-weight:500;">
                            ${applicants.length} of ${applicants.length} selected
                        </span>
                    </div>
                </div>
                <div style="border:1px solid #d1d8dd; border-radius:8px; overflow:hidden; background:#ffffff;">
                    <table class="table table-bordered table-hover" style="margin:0; font-size:13px; width:100%;">
                        <thead style="background:#f8fafc;">
                            <tr>
                                <th style="width:40px; text-align:center; vertical-align:middle; padding:8px 4px;"></th>
                                <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Applicant ID</th>
                                <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Candidate Name</th>
                                <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Previous Preference</th>
                                <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Next Preference (City)</th>
                                <th style="color:#3b82f6; vertical-align:middle; padding:8px 10px; font-weight:600;">Preference Step</th>
                            </tr>
                            <tr style="background:#f1f5f9;">
                                <th style="padding:4px 6px; text-align:center;"></th>
                                <th style="padding:4px 6px;">
                                    <input type="text" id="filter-gen-applicant-id" placeholder="${__("Filter ID...")}"
                                           style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                </th>
                                <th style="padding:4px 6px;">
                                    <input type="text" id="filter-gen-candidate-name" placeholder="${__("Filter Name...")}"
                                           style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                </th>
                                <th style="padding:4px 6px; text-align:center;"></th>
                                <th style="padding:4px 6px;">
                                    <input type="text" id="filter-gen-next-pref" placeholder="${__("Filter Next City...")}"
                                           style="width:100%; border:1px solid #cbd5e1; border-radius:14px; padding:3px 10px; font-size:11px; outline:none; background:#ffffff; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                                </th>
                                <th style="padding:4px 6px; text-align:center;"></th>
                            </tr>
                        </thead>
                        <tbody id="generate-applicant-table-body"></tbody>
                    </table>
                </div>
            `;
            d.fields_dict.applicants_html.$wrapper.html(html);

            d.$wrapper.on("input", "#filter-gen-applicant-id", function () {
                applicant_filters.applicant_id = $(this).val().toLowerCase().trim();
                render_applicant_table();
            });
            d.$wrapper.on("input", "#filter-gen-candidate-name", function () {
                applicant_filters.candidate_name = $(this).val().toLowerCase().trim();
                render_applicant_table();
            });
            d.$wrapper.on("input", "#filter-gen-next-pref", function () {
                applicant_filters.next_preference = $(this).val().toLowerCase().trim();
                render_applicant_table();
            });

            d.$wrapper.on("change", ".pref2-chk", function () {
                const name = $(this).data("name");
                if (this.checked) selected_applicant_names.add(name);
                else selected_applicant_names.delete(name);
                
                const filtered = get_filtered_applicants();
                const sel_count = selected_applicant_names.size;
                const selectable_count = applicants.filter(a => a.has_next).length;
                const total_count = applicants.length;
                
                if (filtered.length !== total_count) {
                    d.$wrapper.find("#sel-count").text(`${sel_count} of ${selectable_count} selectable selected (Filtered: ${filtered.length} of ${total_count})`);
                } else {
                    d.$wrapper.find("#sel-count").text(`${sel_count} of ${selectable_count} selectable selected`);
                }
                d.$wrapper.find("#pref2-select-all").prop("checked", selectable_count > 0 && sel_count === selectable_count);
            });

            d.$wrapper.on("change", "#pref2-select-all", function () {
                const filtered = get_filtered_applicants();
                if (this.checked) {
                    filtered.filter(a => a.has_next).forEach(a => selected_applicant_names.add(a.name));
                } else {
                    filtered.forEach(a => selected_applicant_names.delete(a.name));
                }
                render_applicant_table();
            });

            render_applicant_table();
            d.show();
        }
    });
}