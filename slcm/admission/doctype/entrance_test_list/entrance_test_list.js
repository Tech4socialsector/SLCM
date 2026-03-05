frappe.ui.form.on("Entrance Test List", {
    refresh: function (frm) {
        if (frm.doc.status === "Generated") {
            frm.add_custom_button(__("Allocate Seats"), function () {
                open_allocation_dialog(frm);
            }, __("Actions"));
        }
    }
});

function open_allocation_dialog(frm) {
    // Filter unallocated applicants
    const applicants = (frm.doc.entrance_test_applicant || []).filter(
        a => a.allocation_status !== "Allocated"
    );

    if (!applicants.length) {
        frappe.msgprint({
            title: __("No Applicants"),
            message: __("All applicants in this list have already been allocated seats."),
            indicator: "orange"
        });
        return;
    }

    // Fetch all active Entrance Test Providers for this campus
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Entrance Test Provider",
            filters: { active: 1, campus: frm.doc.campus },
            fields: ["name", "center_name", "center_address", "provider_type"],
            limit_page_length: 100
        },
        callback: function (r) {
            const providers = r.message || [];
            if (!providers.length) {
                frappe.msgprint({
                    title: __("No Providers Found"),
                    message: __("No active Entrance Test Providers found for this campus."),
                    indicator: "orange"
                });
                return;
            }
            _show_allocation_dialog(frm, applicants, providers);
        }
    });
}

function _show_allocation_dialog(frm, applicants, providers) {
    // Build provider options for multiselect checkboxes
    const provider_options_html = providers.map(p => `
        <label style="display:flex; align-items:center; gap:8px; padding:8px 12px; 
                       border:1px solid #d1d8dd; border-radius:4px; cursor:pointer;
                       margin-bottom:6px; background:#fff; transition: background 0.15s;">
            <input type="checkbox" class="provider-checkbox" 
                   data-name="${p.name}" 
                   data-center="${p.center_name || ''}"
                   style="width:16px; height:16px; cursor:pointer;">
            <span>
                <b>${p.center_name || p.name}</b>
                <span style="color:#6c757d; font-size:11px; margin-left:6px;">(${p.name})</span>
                ${p.center_address ? `<br><small style="color:#888;">${p.center_address}</small>` : ""}
            </span>
        </label>
    `).join("");

    // Build applicant table rows
    const rows_html = applicants.map((row, idx) => `
        <tr data-idx="${idx}">
            <td style="text-align:center; width:40px;">
                <input type="checkbox" class="applicant-checkbox" 
                       data-name="${row.name}" data-idx="${idx}">
            </td>
            <td><b>${row.candidate_name || "Unknown"}</b></td>
            <td>${row.applicant_id || "-"}</td>
            <td>${row.program || "-"}</td>
        </tr>
    `).join("");

    let d = new frappe.ui.Dialog({
        title: __("Allocate Seats"),
        size: "extra-large",
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "provider_section_label",
                options: `<div style="font-weight:600; font-size:13px; margin-bottom:8px; color:#333;">
                            ${__("Select Entrance Test Providers (Preferences)")}
                            <span style="font-weight:400; font-size:11px; color:#888; margin-left:8px;">
                                — Select one or more centers as preferences for applicants
                            </span>
                          </div>`
            },
            {
                fieldtype: "HTML",
                fieldname: "provider_checkboxes",
                options: `
                    <div id="provider-list" style="margin-bottom:4px;">
                        ${provider_options_html}
                    </div>
                    <div id="provider-sel-count" style="font-size:12px; color:#6c757d; margin-top:4px;">
                        0 provider(s) selected
                    </div>
                `
            },
            {
                label: __("Select Applicants"),
                fieldtype: "Section Break"
            },
            {
                label: __("Entrance Test Name"),
                fieldname: "entrance_test_name",
                fieldtype: "Link",
                options: "Entrance Test",
                reqd: 1
            },
            {
                label: __("Allocation Date"),
                fieldname: "allocation_date",
                fieldtype: "Datetime",
                description: __("Enter the date and time to be recorded as Allocation Date for created records"),
                reqd: 1
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
                    <div style="margin-bottom:10px; display:flex; gap:12px; align-items:center;">
                        <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center;">
                            <input type="checkbox" id="select-all-chk">
                            <span style="margin-left:8px;">Select All</span>
                        </label>
                        <span id="sel-count" style="color:#6c757d; font-size:12px;">
                            0 of ${applicants.length} selected
                        </span>
                    </div>
                    <div style="max-height:380px; overflow-y:auto; border:1px solid #d1d8dd; border-radius:4px;">
                        <table class="table table-bordered table-hover" 
                               style="margin:0; font-size:13px;">
                            <thead style="position:sticky; top:0; background:#f4f5f6; z-index:1;">
                                <tr>
                                    <th style="width:40px;"></th>
                                    <th>Candidate Name</th>
                                    <th>Applicant ID</th>
                                    <th>Program</th>
                                </tr>
                            </thead>
                            <tbody>${rows_html}</tbody>
                        </table>
                    </div>
                `
            }
        ],
        primary_action_label: __("Allocate Seats"),
        primary_action(values) {
            // Validate providers selected
            const selected_provider_els = [...d.$wrapper.find(".provider-checkbox:checked")];
            if (!selected_provider_els.length) {
                frappe.msgprint(__("Please select at least one Entrance Test Provider."));
                return;
            }

            // Validate applicants selected
            const checked_applicant_els = [...d.$wrapper.find(".applicant-checkbox:checked")];
            if (!checked_applicant_els.length) {
                frappe.msgprint(__("Please select at least one applicant."));
                return;
            }

            const selected_providers = selected_provider_els.map(el => $(el).attr("data-name"));
            const selected_applicants = checked_applicant_els.map(el => $(el).attr("data-name"));
            const allocation_date = d.get_value("allocation_date");

            frappe.call({
                method: "allocate_seats",
                doc: frm.doc,
                args: {
                    providers: selected_providers,
                    selected_applicants: selected_applicants,
                    allocation_date: allocation_date,
                    entrance_test_name: d.get_value("entrance_test_name")
                },
                freeze: true,
                freeze_message: __("Allocating Seats..."),
                callback: function (r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __(
                                "Successfully created seat allocation records for {0} applicants across {1} provider(s).",
                                [r.message, selected_providers.length]
                            ),
                            indicator: "green"
                        });
                    }
                }
            });
        }
    });

    d.show();

    // Set query for entrance_test_name with correct filtering
    d.set_query("entrance_test_name", () => {
        return {
            filters: [
                ["Entrance Test", "campus", "=", frm.doc.campus],
                ["Entrance Test", "academic_year", "=", frm.doc.academic_year],
                ["Entrance Test", "admission_cycle", "=", frm.doc.admission_cycle],
                ["Entrance Test", "is_active", "=", 1],
                ["Entrance Test", "valid_from", "<=", frappe.datetime.get_today()],
                ["Entrance Test", "valid_to", ">=", frappe.datetime.get_today()]
            ]
        };
    });

    const $wrapper = d.$wrapper;

    // Provider checkbox count update
    $wrapper.on("change", ".provider-checkbox", function () {
        const n = $wrapper.find(".provider-checkbox:checked").length;
        $wrapper.find("#provider-sel-count").text(`${n} provider(s) selected`);
    });

    // Select All applicants
    $wrapper.find("#select-all-chk").on("change", function () {
        $wrapper.find(".applicant-checkbox").prop("checked", this.checked);
        update_sel_count(d, applicants.length);
    });

    // Individual applicant checkbox
    $wrapper.on("change", ".applicant-checkbox", function () {
        const total = $wrapper.find(".applicant-checkbox").length;
        const n = $wrapper.find(".applicant-checkbox:checked").length;
        $wrapper.find("#select-all-chk").prop("checked", total === n && total > 0);
        update_sel_count(d, applicants.length);
    });

    // Auto-select logic
    d.fields_dict.auto_select_count.$input.on("input", function () {
        let val = parseInt($(this).val()) || 0;
        $wrapper.find(".applicant-checkbox").prop("checked", false);
        $wrapper.find(".applicant-checkbox").slice(0, val).prop("checked", true);

        const total = $wrapper.find(".applicant-checkbox").length;
        const n = $wrapper.find(".applicant-checkbox:checked").length;
        $wrapper.find("#select-all-chk").prop("checked", total === n && total > 0);
        update_sel_count(d, applicants.length);
    });
}

function update_sel_count(d, total) {
    const count = d.$wrapper.find(".applicant-checkbox:checked").length;
    d.$wrapper.find("#sel-count").text(`${count} of ${total} selected`);
}