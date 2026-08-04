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
        }
    }
});

function open_allocation_dialog(frm) {
    const all_applicants = frm.doc.entrance_test_applicant || [];
    const applicants = all_applicants.filter(a => a.allocation_status !== "Allocated");

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
                message: __("All <b>{0}</b> applicants in this list have already been successfully allocated seats. <br><br>The system has verified that there are no pending students left for seat allocation in this list. If you need to allocate new students, please add them to this list or generate a new one.", [total]),
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
        method: "frappe.client.get_list",
        args: {
            doctype: "Entrance Test Provider",
            filters: provider_filters,
            fields: ["name", "center_name", "center_address", "provider_type", "city", "pwd_accessible"],
            limit_page_length: 100
        },
        callback: function (r) {
            const providers = r.message || [];
            if (!providers.length) {
                const target_label = frm.doc.entrance_test_city ? __("city '{0}'", [frm.doc.entrance_test_city]) : __("campus '{0}'", [frm.doc.campus]);
                frappe.msgprint({
                    title: __("No Available Providers"),
                    message: __("No active Entrance Test Providers with available seats found for {0}.", [target_label]),
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
                    const selected_city = d.get_value("entrance_test_city");
                    fetch_and_render_providers(selected_city);
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

                        d.hide();
                        frm.reload_doc();
                    }
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
        programme: ""
    };

    function get_filtered_applicants() {
        return applicants.filter(a => {
            const id_match = !applicant_filters.applicant_id || (a.applicant_id || "").toLowerCase().includes(applicant_filters.applicant_id);
            const name_match = !applicant_filters.candidate_name || (a.candidate_name || "").toLowerCase().includes(applicant_filters.candidate_name);
            const prog_match = !applicant_filters.programme || (a.program || "").toLowerCase().includes(applicant_filters.programme);
            return id_match && name_match && prog_match;
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

    function fetch_and_render_providers(city_name) {
        const provider_filters = { 
            active: 1, 
            available_capacity: [">", 0]
        };
        if (city_name) {
            provider_filters.city = city_name;
        } else if (frm.doc.campus) {
            provider_filters.campus = frm.doc.campus;
        }

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Entrance Test Provider",
                filters: provider_filters,
                fields: ["name", "center_name", "center_address", "provider_type", "city", "pwd_accessible"],
                limit_page_length: 100
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

    $wrapper.on("input keyup search", "#filter-applicant-id, #filter-candidate-name, #filter-programme", function () {
        applicant_filters.applicant_id = $wrapper.find("#filter-applicant-id").val().toLowerCase().trim();
        applicant_filters.candidate_name = $wrapper.find("#filter-candidate-name").val().toLowerCase().trim();
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