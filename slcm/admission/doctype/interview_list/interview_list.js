frappe.ui.form.on("Interview List", {
    refresh: function (frm) {

        // ── Status intro message ───────────────────────────────────────────────
        if (frm.doc.status === "Generated") {
            frm.set_intro(
                __("Interview List generated. Use the Actions menu to allocate interview slots."),
                "blue"
            );
        } else if (frm.doc.status === "In Progress") {
            frm.set_intro(__("Interview slot allocation is in progress."), "orange");
        } else if (frm.doc.status === "Completed") {
            frm.set_intro(__("Interview process completed."), "green");
        }

        // ── Source breakdown dashboard ────────────────────────────────────────
        if (frm.doc.interview_applicant && frm.doc.interview_applicant.length) {
            const rows = frm.doc.interview_applicant;
            const total = rows.length;
            const cnt = {};
            rows.forEach(r => {
                const src = r.source_type || "Unknown";
                cnt[src] = (cnt[src] || 0) + 1;
            });
            let breakdown = Object.entries(cnt)
                .map(([src, n]) => `<b>${src}:</b> ${n}`)
                .join("&nbsp;&nbsp;|&nbsp;&nbsp;");
            frm.dashboard.add_comment(
                `<span style="font-size:12px;">
                    Total Applicants: <b>${total}</b>
                    &nbsp;&nbsp;—&nbsp;&nbsp;${breakdown}
                </span>`,
                "blue",
                true
            );
        }

        // ── "Allocate Interview Slots" button ─────────────────────────────────
        frm.remove_custom_button("Allocate Interview Slots");
        if (frm.doc.status === "Generated") {
            frm.add_custom_button(__("Allocate Interview Slots"), function () {
                open_slot_dialog(frm);
            }, __("Actions"))
                .addClass("btn-primary")
                .css({ "font-weight": "bold" });
        }
    }
});


// ─────────────────────────────────────────────────────────────────────────────
// Dialog helpers
// ─────────────────────────────────────────────────────────────────────────────

function open_slot_dialog(frm) {
    // Filter applicants not yet scheduled
    const applicants = (frm.doc.interview_applicant || []).filter(
        a => a.interview_status !== "Scheduled"
    );

    if (!applicants.length) {
        frappe.msgprint({
            title: __("No Pending Applicants"),
            message: __("All applicants in this list have already been scheduled for an interview."),
            indicator: "orange"
        });
        return;
    }

    // Fetch active Interview Staff Members for this campus
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Interview Staff Member",
            filters: {
                is_active: 1,
                campus: frm.doc.campus,
                academic_year: frm.doc.academic_year,
                admission_cycle: frm.doc.admission_cycle
            },
            fields: ["name", "staff_name", "designation", "email", "contact_number"],
            limit_page_length: 100
        },
        callback: function (r) {
            const staff_list = r.message || [];
            if (!staff_list.length) {
                frappe.msgprint({
                    title: __("No Staff Members Found"),
                    message: __(
                        "No active Interview Staff Members found for this campus, "
                        + "academic year and admission cycle. "
                        + "Please create staff members first."
                    ),
                    indicator: "orange"
                });
                return;
            }
            _show_slot_dialog(frm, applicants, staff_list);
        }
    });
}


function _show_slot_dialog(frm, applicants, staff_list) {

    // Build staff radio buttons — admin picks EXACTLY ONE
    const staff_html = staff_list.map((s, idx) => `
        <label style="display:flex; align-items:flex-start; gap:10px; padding:10px 14px;
                       border:1px solid #d1d8dd; border-radius:4px; cursor:pointer;
                       margin-bottom:6px; background:#fff; transition: background 0.15s;"
               class="staff-label">
            <input type="radio" name="staff_radio" class="staff-radio"
                   value="${s.name}" style="margin-top:3px; cursor:pointer;"
                   ${idx === 0 ? "checked" : ""}>
            <span>
                <b>${s.staff_name}</b>
                ${s.designation ? `<span style="color:#888; font-size:11px; margin-left:6px;">(${s.designation})</span>` : ""}
                <br>
                <small style="color:#6c757d;">
                    ${s.email || ""}${s.contact_number ? " &nbsp;|&nbsp; " + s.contact_number : ""}
                </small>
            </span>
        </label>
    `).join("");

    // Build applicant table rows
    const rows_html = applicants.map((row, idx) => `
        <tr>
            <td style="text-align:center; width:40px;">
                <input type="checkbox" class="applicant-checkbox"
                       data-name="${row.name}" data-idx="${idx}">
            </td>
            <td><b>${row.candidate_name || "Unknown"}</b></td>
            <td>${row.applicant_id || "-"}</td>
            <td>${row.program || "-"}</td>
            <td>
                <span style="font-size:11px; padding:2px 7px; border-radius:10px;
                             background:${row.source_type === "Entrance Test" ? "#e3f2fd" : "#e8f5e9"};
                             color:${row.source_type === "Entrance Test" ? "#1565c0" : "#2e7d32"};">
                    ${row.source_type || "-"}
                </span>
            </td>
            <td style="text-align:right; color:#555;">${row.entrance_test_score || "-"}</td>
        </tr>
    `).join("");

    let d = new frappe.ui.Dialog({
        title: __("Allocate Interview Slots"),
        size: "extra-large",
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "staff_section_label",
                options: `<div style="font-weight:600; font-size:13px; margin-bottom:8px; color:#333;">
                            ${__("Select Interview Staff Member")}
                            <span style="font-weight:400; font-size:11px; color:#888; margin-left:8px;">
                                — Select exactly one interviewer
                            </span>
                          </div>`
            },
            {
                fieldtype: "HTML",
                fieldname: "staff_radios",
                options: `<div id="staff-list" style="margin-bottom:4px;">${staff_html}</div>`
            },
            {
                label: __("Interview Date"),
                fieldname: "interview_date",
                fieldtype: "Date",
                reqd: 1,
                description: __("Date on which the interview will be conducted")
            },
            {
                label: __("Interview Time"),
                fieldname: "interview_time",
                fieldtype: "Time",
                description: __("Time slot for the interview (optional)")
            },
            {
                label: __("Select Applicants"),
                fieldtype: "Section Break"
            },
            {
                label: __("Auto-select (Enter Number)"),
                fieldname: "auto_select_count",
                fieldtype: "Int",
                description: __("Enter count to automatically select first N pending applicants")
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
                                    <th>Source</th>
                                    <th style="text-align:right;">ET Score</th>
                                </tr>
                            </thead>
                            <tbody>${rows_html}</tbody>
                        </table>
                    </div>
                `
            }
        ],
        primary_action_label: __("Allocate Slots"),
        primary_action(values) {

            // Get selected staff (radio)
            const selected_staff = d.$wrapper.find(".staff-radio:checked").val();
            if (!selected_staff) {
                frappe.msgprint(__("Please select an Interview Staff Member."));
                return;
            }

            // Get selected applicants
            const checked = [...d.$wrapper.find(".applicant-checkbox:checked")];
            if (!checked.length) {
                frappe.msgprint(__("Please select at least one applicant."));
                return;
            }

            const selected_applicants = checked.map(el => $(el).attr("data-name"));

            frappe.call({
                method: "allocate_interview_slots",
                doc: frm.doc,
                args: {
                    staff_member: selected_staff,
                    selected_applicants: selected_applicants,
                    interview_date: values.interview_date,
                    interview_time: values.interview_time || null
                },
                freeze: true,
                freeze_message: __("Allocating Interview Slots… Please wait"),
                callback: function (r) {
                    if (!r.exc) {
                        d.hide();
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __(
                                "Successfully allocated interview slots for {0} applicant(s).",
                                [r.message]
                            ),
                            indicator: "green"
                        });
                    }
                }
            });
        }
    });

    d.show();

    const $wrapper = d.$wrapper;

    // Select-all checkbox
    $wrapper.find("#select-all-chk").on("change", function () {
        $wrapper.find(".applicant-checkbox").prop("checked", this.checked);
        _update_count(d, applicants.length);
    });

    // Individual applicant checkbox
    $wrapper.on("change", ".applicant-checkbox", function () {
        const total = $wrapper.find(".applicant-checkbox").length;
        const n = $wrapper.find(".applicant-checkbox:checked").length;
        $wrapper.find("#select-all-chk").prop("checked", total === n && total > 0);
        _update_count(d, applicants.length);
    });

    // Auto-select N
    d.fields_dict.auto_select_count.$input.on("input", function () {
        let val = parseInt($(this).val()) || 0;
        $wrapper.find(".applicant-checkbox").prop("checked", false);
        $wrapper.find(".applicant-checkbox").slice(0, val).prop("checked", true);
        const total = $wrapper.find(".applicant-checkbox").length;
        const n = $wrapper.find(".applicant-checkbox:checked").length;
        $wrapper.find("#select-all-chk").prop("checked", total === n && total > 0);
        _update_count(d, applicants.length);
    });

    // Radio hover highlight
    $wrapper.on("change", ".staff-radio", function () {
        $wrapper.find(".staff-label").css("background", "#fff");
        $(this).closest(".staff-label").css("background", "#e3f2fd");
    });
    // Highlight default-checked one
    $wrapper.find(".staff-radio:checked").closest(".staff-label").css("background", "#e3f2fd");
}


function _update_count(d, total) {
    const count = d.$wrapper.find(".applicant-checkbox:checked").length;
    d.$wrapper.find("#sel-count").text(`${count} of ${total} selected`);
}
