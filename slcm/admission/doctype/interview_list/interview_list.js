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
    const all_applicants = frm.doc.interview_applicant || [];
    const applicants = all_applicants.filter(a => a.interview_status !== "Scheduled");

    if (!applicants.length) {
        const total = all_applicants.length;
        if (total === 0) {
            frappe.msgprint({
                title: __("No Applicants Found"),
                message: __("This Interview List is empty. Please ensure applicants are added before attempting to allocate slots."),
                indicator: "orange"
            });
        } else {
            frappe.msgprint({
                title: __("Scheduling Already Completed"),
                message: __("All <b>{0}</b> applicants in this list have already been scheduled for an interview. <br><br>The system has verified that there are no pending students left for interview slot allocation in this list.", [total]),
                indicator: "blue"
            });
        }
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
                reqd: 1,
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
                        // Inject keyframe styles once
                        if (!document.getElementById("ivl-toast-style")) {
                            const style = document.createElement("style");
                            style.id = "ivl-toast-style";
                            style.innerHTML = `
                                @keyframes ivlSlideDown {
                                    from { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                                    to   { opacity: 1; transform: translateX(-50%) translateY(0); }
                                }
                                @keyframes ivlSlideUp {
                                    from { opacity: 1; transform: translateX(-50%) translateY(0); }
                                    to   { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                                }
                            `;
                            document.head.appendChild(style);
                        }

                        // Remove existing toast if any
                        const existingToast = document.getElementById("ivl-success-toast");
                        if (existingToast) existingToast.remove();

                        const count = r.message || 0;
                        const toast = document.createElement("div");
                        toast.id = "ivl-success-toast";
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
                            min-width: 380px;
                            max-width: 550px;
                            box-shadow: 0 10px 40px rgba(45,164,78,0.22), 0 2px 10px rgba(0,0,0,0.12);
                            display: flex;
                            align-items: flex-start;
                            gap: 15px;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            animation: ivlSlideDown 0.4s cubic-bezier(.4,0,.2,1) forwards;
                        `;
                        toast.innerHTML = `
                            <div style="flex-shrink:0; width:38px; height:38px; background:#eafbee;
                                        border-radius:50%; display:flex; align-items:center;
                                        justify-content:center; font-size:20px;">✅</div>
                            <div style="flex:1;">
                                <div style="font-weight:800; font-size:15px; color:#1a7f37; margin-bottom:4px; letter-spacing:-0.2px;">
                                    Interview Scheduled Successfully Updated
                                </div>
                                <div style="font-size:13.5px; color:#4a4a4a; line-height:1.4;">
                                    The interview allocation process has been completed successfully for <span style="font-weight:700; color:#1a7f37;">${count} applicants</span>.
                                </div>
                            </div>
                            <span id="ivl-success-toast-close"
                                  style="cursor:pointer; color:#adb5bd; font-size:20px; line-height:1;
                                         padding:4px; align-self:flex-start; flex-shrink:0; transition: color 0.2s;"
                                  onmouseover="this.style.color='#495057'" onmouseout="this.style.color='#adb5bd'"
                                  title="Dismiss">✕</span>
                        `;
                        document.body.appendChild(toast);

                        const dismissToast = () => {
                            toast.style.animation = "ivlSlideUp 0.4s cubic-bezier(.4,0,.2,1) forwards";
                            setTimeout(() => toast.remove(), 400);
                        };
                        document.getElementById("ivl-success-toast-close").onclick = dismissToast;
                        setTimeout(dismissToast, 6500);

                        d.hide();
                        frm.reload_doc();
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

    // ── Past-date validation on Interview Date ──────────────────────────
    d.fields_dict.interview_date.$input.on("change blur", function () {
        const entered = d.get_value("interview_date");
        if (!entered) return;

        // Compare based on date only (today or future)
        const today = frappe.datetime.get_today();
        if (entered < today) {
            // Clear the field
            d.set_value("interview_date", "");

            // Inject keyframe styles once (shared with ivl success toast)
            if (!document.getElementById("ivl-toast-style")) {
                const style = document.createElement("style");
                style.id = "ivl-toast-style";
                style.innerHTML = `
                    @keyframes ivlSlideDown {
                        from { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                        to   { opacity: 1; transform: translateX(-50%) translateY(0); }
                    }
                    @keyframes ivlSlideUp {
                        from { opacity: 1; transform: translateX(-50%) translateY(0); }
                        to   { opacity: 0; transform: translateX(-50%) translateY(-30px); }
                    }
                `;
                document.head.appendChild(style);
            }

            // Remove any existing warning toast
            const existingToast = document.getElementById("ivl-date-toast");
            if (existingToast) existingToast.remove();

            // Build warning toast
            const toast = document.createElement("div");
            toast.id = "ivl-date-toast";
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
                animation: ivlSlideDown 0.35s cubic-bezier(.4,0,.2,1) forwards;
            `;
            toast.innerHTML = `
                <div style="flex-shrink:0; width:36px; height:36px; background:#fff3cd;
                            border-radius:50%; display:flex; align-items:center;
                            justify-content:center; font-size:18px;">⚠️</div>
                <div style="flex:1;">
                    <div style="font-weight:700; font-size:14px; color:#856404; margin-bottom:3px;">
                        Invalid Interview Date
                    </div>
                    <div style="font-size:12.5px; color:#555;">
                        choose the Interview Should not Be past date choose future date
                    </div>
                </div>
                <span id="ivl-date-toast-close"
                      style="cursor:pointer; color:#aaa; font-size:18px; line-height:1;
                             padding:0 4px; align-self:flex-start; flex-shrink:0;"
                      title="Dismiss">✕</span>
            `;
            document.body.appendChild(toast);

            const dismissDateToast = () => {
                toast.style.animation = "ivlSlideUp 0.35s cubic-bezier(.4,0,.2,1) forwards";
                setTimeout(() => toast.remove(), 350);
            };
            document.getElementById("ivl-date-toast-close").addEventListener("click", dismissDateToast);
            setTimeout(dismissDateToast, 6000);
        }
    });
}


function _update_count(d, total) {
    const count = d.$wrapper.find(".applicant-checkbox:checked").length;
    d.$wrapper.find("#sel-count").text(`${count} of ${total} selected`);
}
