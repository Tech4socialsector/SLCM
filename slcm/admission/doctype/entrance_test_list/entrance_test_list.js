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

    // Fetch all active Entrance Test Providers with available capacity for this campus
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Entrance Test Provider",
            filters: { 
                active: 1, 
                campus: frm.doc.campus,
                available_capacity: [">", 0]
            },
            fields: ["name", "center_name", "center_address", "provider_type"],
            limit_page_length: 100
        },
        callback: function (r) {
            const providers = r.message || [];
            if (!providers.length) {
                frappe.msgprint({
                    title: __("No Available Providers"),
                    message: __("No active Entrance Test Providers with available seats found for this campus."),
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
        <label style="display:flex; align-items:flex-start; gap:10px; padding:10px 14px;
                       border:1px solid #d1d8dd; border-radius:6px; cursor:pointer;
                       margin-bottom:8px; background:#fafbfc; transition: background 0.15s;
                       hover:background:#f0f9f3;">
            <input type="checkbox" class="provider-checkbox"
                   data-name="${p.name}"
                   data-center="${p.center_name || ''}"
                   style="width:16px; height:16px; cursor:pointer; margin-top:3px; flex-shrink:0;">
            <span style="line-height:1.5;">
                <span style="display:block; font-weight:700; font-size:13.5px; color:#1a1a1a;">
                    ${p.center_name || p.name}
                </span>
                ${p.center_address
            ? `<span style="display:block; font-size:11.5px; color:#6c757d; margin-top:2px;">
                           📍 ${p.center_address}
                       </span>`
            : `<span style="display:block; font-size:11px; color:#aaa; margin-top:2px; font-style:italic;">No address provided</span>`
        }
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
                            ${__("Select Entrance Test Centers")}
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
                label: __("Entrance Test Date"),
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

            // Final date validation before call
            if (!allocation_date) {
                frappe.msgprint(__("Please select a valid Entrance Test Date."));
                return;
            }
            if (new Date(allocation_date).getTime() <= new Date().getTime()) {
                // Trigger the toast warning again if they somehow bypassed the change listener
                d.fields_dict.allocation_date.$input.trigger("change");
                return;
            }

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
                        // Inject keyframe styles once
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

                        // Remove any existing success toast
                        const existingToast = document.getElementById("etl-success-toast");
                        if (existingToast) existingToast.remove();

                        const count = r.message || 0;
                        const toast = document.createElement("div");
                        toast.id = "etl-success-toast";
                        toast.style.cssText = `
                            position: fixed;
                            top: 20px;
                            left: 50%;
                            z-index: 999999;
                            background: #ffffff;
                            border: 1.5px solid #2da44e;
                            border-left: 5px solid #2da44e;
                            border-radius: 10px;
                            padding: 14px 20px;
                            min-width: 360px;
                            max-width: 500px;
                            box-shadow: 0 8px 30px rgba(45,164,78,0.18), 0 2px 8px rgba(0,0,0,0.10);
                            display: flex;
                            align-items: flex-start;
                            gap: 12px;
                            font-family: inherit;
                            animation: etgSlideDown 0.35s cubic-bezier(.4,0,.2,1) forwards;
                        `;
                        toast.innerHTML = `
                            <div style="flex-shrink:0; width:36px; height:36px; background:#eafbee;
                                        border-radius:50%; display:flex; align-items:center;
                                        justify-content:center; font-size:18px;">✅</div>
                            <div style="flex:1;">
                                <div style="font-weight:700; font-size:14px; color:#1a7f37; margin-bottom:3px;">
                                    Allocation Successfully Completed.
                                </div>
                                <div style="font-size:13px; color:#333;">
                                    The entrance test allocation process has been completed successfully for ${count} applicants.
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

                        d.hide();
                        frm.reload_doc();
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
                ["Entrance Test", "is_active", "=", 1]
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

    // ── Past-date validation on Entrance Test Date ──────────────────────────
    d.fields_dict.allocation_date.$input.on("change blur", function () {
        const entered = d.get_value("allocation_date");
        if (!entered) return;

        const enteredMs = new Date(entered).getTime();
        const nowMs = new Date().getTime();

        if (enteredMs <= nowMs) {
            // Clear the field
            d.set_value("allocation_date", "");

            // Inject keyframe styles once (shared with etg toast)
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

            // Remove any existing toast
            const existingToast = document.getElementById("etl-date-toast");
            if (existingToast) existingToast.remove();

            // Build warning toast
            const toast = document.createElement("div");
            toast.id = "etl-date-toast";
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                left: 50%;
                z-index: 999999;
                background: #fff8e1;
                border: 1.5px solid #f0a500;
                border-left: 5px solid #f0a500;
                border-radius: 10px;
                padding: 14px 20px;
                min-width: 360px;
                max-width: 500px;
                box-shadow: 0 8px 30px rgba(240,165,0,0.18), 0 2px 8px rgba(0,0,0,0.10);
                display: flex;
                align-items: flex-start;
                gap: 12px;
                font-family: inherit;
                animation: etgSlideDown 0.35s cubic-bezier(.4,0,.2,1) forwards;
            `;
            toast.innerHTML = `
                <div style="flex-shrink:0; width:36px; height:36px; background:#fff3cd;
                            border-radius:50%; display:flex; align-items:center;
                            justify-content:center; font-size:18px;">⚠️</div>
                <div style="flex:1;">
                    <div style="font-weight:700; font-size:14px; color:#856404; margin-bottom:3px;">
                        Invalid Entrance Test Date
                    </div>
                    <div style="font-size:12.5px; color:#555;">
                        choose the Entrance Test Should not Be past date choose future date
                    </div>
                </div>
                <span id="etl-date-toast-close"
                      style="cursor:pointer; color:#aaa; font-size:18px; line-height:1;
                             padding:0 4px; align-self:flex-start; flex-shrink:0;"
                      title="Dismiss">✕</span>
            `;
            document.body.appendChild(toast);

            const dismissDateToast = () => {
                toast.style.animation = "etgSlideUp 0.35s cubic-bezier(.4,0,.2,1) forwards";
                setTimeout(() => toast.remove(), 350);
            };
            document.getElementById("etl-date-toast-close").addEventListener("click", dismissDateToast);
            setTimeout(dismissDateToast, 5000);
        }
    });
}

function update_sel_count(d, total) {
    const count = d.$wrapper.find(".applicant-checkbox:checked").length;
    d.$wrapper.find("#sel-count").text(`${count} of ${total} selected`);
}