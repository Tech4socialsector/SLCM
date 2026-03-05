frappe.ui.form.on("Merit List", {
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            // Create Seat Allocation button
            frm.add_custom_button(__("Create Seat Allocation"), function () {
                open_allocation_dialog(frm);
            });

            // Publish button — shown when status is Generated
            if (frm.doc.status !== "Published") {
                frm.add_custom_button(__("Publish Merit List"), function () {
                    frappe.confirm(
                        __("Publishing will make merit scores visible to all students on their portal. Continue?"),
                        function () {
                            frappe.call({
                                method: "slcm.admission.doctype.merit_list.merit_list.publish_merit_list",
                                args: { merit_list_name: frm.doc.name },
                                freeze: true,
                                freeze_message: __("Publishing merit list..."),
                                callback(r) {
                                    if (!r.exc) {
                                        frappe.show_alert({
                                            message: __("Merit list published. Students can now view their scores."),
                                            indicator: "green"
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }
                    );
                }, __("Actions"));
            }

            // Unpublish button — shown only when already Published
            if (frm.doc.status === "Published") {
                frm.add_custom_button(__("Unpublish"), function () {
                    frappe.confirm(
                        __("This will hide merit scores from students. Continue?"),
                        function () {
                            frappe.call({
                                method: "slcm.admission.doctype.merit_list.merit_list.unpublish_merit_list",
                                args: { merit_list_name: frm.doc.name },
                                callback(r) {
                                    if (!r.exc) {
                                        frappe.show_alert({
                                            message: __("Merit list unpublished."),
                                            indicator: "orange"
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }
                    );
                }, __("Actions"));
            }

            // Status indicator
            if (frm.doc.status === "Published") {
                frm.set_indicator_formatter && frm.toolbar
                    && frm.toolbar.set_indicator
                    && frm.toolbar.set_indicator(["Published", "green"]);
                frm.page.set_indicator(__("Published"), "green");
            } else if (frm.doc.status === "Generated") {
                frm.page.set_indicator(__("Generated"), "blue");
            }
        }
    }
});


function open_allocation_dialog(frm) {
    const applicants = frm.doc.merit_applicants || [];

    if (!applicants.length) {
        frappe.msgprint({
            title: __("No Applicants"),
            message: __("This Merit List has no applicants to allocate."),
            indicator: "orange"
        });
        return;
    }

    // Build table rows — all checked by default
    const rows_html = applicants.map((row, idx) => `
        <tr>
            <td style="text-align:center; width:40px;">
                <input type="checkbox" class="applicant-checkbox" data-idx="${idx}" checked>
            </td>
            <td>${row.overall_rank || "-"}</td>
            <td><b>${row.candidate_name || "-"}</b></td>
            <td>${row.applicant_id || "-"}</td>
            <td>${row.program || "-"}</td>
            <td>${row.reservation_category || "-"}</td>
            <td>${(row.total_score !== undefined && row.total_score !== null) ? parseFloat(row.total_score).toFixed(3) : "-"}</td>
        </tr>
    `).join("");

    const dialog = new frappe.ui.Dialog({
        title: __("Allocate Seats"),
        size: "extra-large",
        fields: [
            {
                fieldtype: "Link",
                fieldname: "admission_cycle",
                label: __("Admission Cycle"),
                options: "Admission Cycle",
                read_only: 1,
                default: frm.doc.admission_cycle
            },
            {
                fieldtype: "Column Break"
            },
            {
                fieldtype: "Link",
                fieldname: "campus",
                label: __("Campus"),
                options: "Campus",
                read_only: 1,
                default: frm.doc.campus
            },
            {
                fieldtype: "Column Break"
            },
            {
                fieldtype: "Select",
                fieldname: "program_level",
                label: __("Program Level"),
                options: "UG\nPG\nResearch Cource",
                read_only: 1,
                default: frm.doc.program_level
            },
            {
                fieldtype: "Section Break"
            },
            {
                fieldtype: "HTML",
                fieldname: "applicant_table",
                options: `
                    <div style="margin-bottom:10px; display:flex; gap:12px; align-items:center;">
                        <label style="font-weight:600; cursor:pointer;">
                            <input type="checkbox" id="select-all-chk" checked>
                            &nbsp;Select All
                        </label>
                        <span id="sel-count" style="color:#6c757d; font-size:12px;">
                            ${applicants.length} of ${applicants.length} selected
                        </span>
                    </div>
                    <div style="max-height:340px; overflow-y:auto; border:1px solid #d1d8dd; border-radius:4px;">
                        <table class="table table-bordered table-hover" style="margin:0;">
                            <thead style="position:sticky; top:0; background:#f4f5f6; z-index:1;">
                                <tr>
                                    <th style="width:40px;"></th>
                                    <th>Rank</th>
                                    <th>Candidate Name</th>
                                    <th>Applicant ID</th>
                                    <th>Program</th>
                                    <th>Reservation Category</th>
                                    <th>Total Score</th>
                                </tr>
                            </thead>
                            <tbody>${rows_html}</tbody>
                        </table>
                    </div>
                `
            }
        ],
        primary_action_label: __("Allocate Seats"),
        primary_action() {
            const checked = [...dialog.$wrapper.find(".applicant-checkbox:checked")];
            if (!checked.length) {
                frappe.msgprint(__("Please select at least one applicant."));
                return;
            }

            const selected = checked.map(el => applicants[parseInt(el.dataset.idx)]);
            dialog.hide();

            frappe.call({
                method: "slcm.admission.doctype.merit_list.merit_list.create_seat_allocation",
                args: {
                    merit_list_name: frm.doc.name,
                    selected_applicants: selected.map(r => r.applicant_id || r.applicant)
                },
                freeze: true,
                freeze_message: __("Creating Seat Allocation..."),
                callback(r) {
                    if (!r.exc && r.message) {
                        frappe.show_alert({
                            message: __(`Seat Allocation <b>${r.message}</b> created successfully.`),
                            indicator: "green"
                        });
                        frappe.set_route("Form", "Seat Allocation", r.message);
                    }
                }
            });
        }
    });

    dialog.show();

    // Select All toggle
    dialog.$wrapper.find("#select-all-chk").on("change", function () {
        dialog.$wrapper.find(".applicant-checkbox").prop("checked", this.checked);
        update_count(dialog, applicants.length);
    });

    // Individual checkbox
    dialog.$wrapper.on("change", ".applicant-checkbox", function () {
        const total = dialog.$wrapper.find(".applicant-checkbox").length;
        const n = dialog.$wrapper.find(".applicant-checkbox:checked").length;
        dialog.$wrapper.find("#select-all-chk").prop("checked", n === total);
        update_count(dialog, applicants.length);
    });
}


function update_count(dialog, total) {
    const n = dialog.$wrapper.find(".applicant-checkbox:checked").length;
    dialog.$wrapper.find("#sel-count").text(`${n} of ${total} selected`);
}
