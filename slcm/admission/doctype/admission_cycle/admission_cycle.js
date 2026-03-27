frappe.ui.form.on("Admission Cycle", {

    refresh: function (frm) {

        frm.set_query("academic_year", function () {
            return {
                filters: {
                    status: "Active"
                }
            };
        });
        frm.set_query("admission_year", function () {
            return {
                filters: {
                    is_active: 1
                }
            };
        });

        // Status indicator
        const colors = { "Draft": "gray", "Active": "green", "Closed": "red" };
        frm.dashboard.set_headline_alert(
            __(frm.doc.status),
            colors[frm.doc.status] || "gray"
        );

        // Program count warning
        if (!frm.is_new()) {
            const active_programs = (frm.doc.programs || [])
                .filter(p => p.is_active).length;
            if (frm.doc.status === "Active" && active_programs === 0) {
                frm.dashboard.set_headline_alert(
                    __("No programs added. Portal will show empty."),
                    "orange"
                );
            } else if (active_programs > 0) {
                frm.dashboard.set_headline_alert(
                    __("{0} program(s) visible on portal", [active_programs]),
                    "green"
                );
            }
        }

        // Set date constraints
        frm.set_df_property("cycle_start_date", "options", {
            minDate: frappe.datetime.get_today()
        });
        frm.set_df_property("cycle_end_date", "options", {
            minDate: frm.doc.cycle_start_date || frappe.datetime.get_today()
        });

        // Set queries for Admission Cycle Stage child table
        const stage_status_fields = ["activate_status", "completed_status", "closed_status"];
        stage_status_fields.forEach(field => {
            frm.set_query(field, "stages", function (doc, cdt, cdn) {
                let row = locals[cdt][cdn];
                if (!row.stage_type) {
                    return {};
                }
                return {
                    filters: {
                        "stage_type": row.stage_type
                    }
                };
            });
        });

        // Quick actions
        if (!frm.is_new()) {
            if (frm.doc.status === "Draft") {
                frm.add_custom_button(__("Activate"), function () {
                    frappe.confirm(
                        __("Activate this cycle? Only one cycle can be Active at a time."),
                        function () {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Admission Cycle",
                                    name: frm.doc.name,
                                    fieldname: "status",
                                    value: "Active"
                                },
                                callback: function () { frm.reload_doc(); }
                            });
                        }
                    );
                }, __("Actions"));
            }

            if (frm.doc.status === "Active") {
                frm.add_custom_button(__("Close Cycle"), function () {
                    frappe.confirm(
                        __("Close this cycle? No more applications will be accepted."),
                        function () {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Admission Cycle",
                                    name: frm.doc.name,
                                    fieldname: "status",
                                    value: "Closed"
                                },
                                callback: function () { frm.reload_doc(); }
                            });
                        }
                    );
                }, __("Actions"));
            }
        }
    },

    status: function (frm) {
        if (frm.doc.status === "Active") {
            frappe.show_alert({
                message: __("Cycle activated. Programs will appear on the portal."),
                indicator: "green"
            }, 5);
        }
    },

    cycle_start_date: function (frm) {
        if (frm.doc.cycle_start_date) {
            if (frm.doc.cycle_start_date < frappe.datetime.get_today()) {
                frappe.msgprint(__("Cycle Start Date cannot be in the past."));
                frm.set_value("cycle_start_date", null);
            } else {
                if (frm.doc.cycle_end_date && frm.doc.cycle_start_date > frm.doc.cycle_end_date) {
                    frappe.msgprint(__("Cycle Start Date cannot be after Cycle End Date."));
                    frm.set_value("cycle_start_date", null);
                }
                // Update minDate for end date picker
                frm.set_df_property("cycle_end_date", "options", {
                    minDate: frm.doc.cycle_start_date
                });
            }
        } else {
            frm.set_df_property("cycle_end_date", "options", {
                minDate: frappe.datetime.get_today()
            });
        }
    },

    cycle_end_date: function (frm) {
        if (frm.doc.cycle_end_date) {
            const min_date = frm.doc.cycle_start_date || frappe.datetime.get_today();
            if (frm.doc.cycle_end_date < min_date) {
                if (frm.doc.cycle_end_date < frappe.datetime.get_today()) {
                    frappe.msgprint(__("Cycle End Date cannot be in the past."));
                } else {
                    frappe.msgprint(__("Cycle End Date cannot be before Cycle Start Date."));
                }
                frm.set_value("cycle_end_date", null);
            }
        }
    }
});

frappe.ui.form.on("Admission Cycle Program", {
    add_reservation_policy: function (frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.reservation_policy) {
            frm.save().then(() => {
                open_reservation_policy(frm, row);
            });
        } else {
            frappe.msgprint(__("Reservation policy already exists"));
        }
    },

    add_program_media: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.program_media) {
            open_program_media(frm, row);
        } else {
            frappe.msgprint(__("Program media already exists"));
        }


    }
});

frappe.ui.form.on("Admission Cycle Stage", {
    stage_type: function (frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "activate_status", null);
        frappe.model.set_value(cdt, cdn, "completed_status", null);
        frappe.model.set_value(cdt, cdn, "closed_status", null);
    },
    stage_name: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.stage_name) {
            let duplicate = (frm.doc.stages || []).find(
                d => d.name !== row.name && d.stage_name === row.stage_name
            );

            if (duplicate) {
                frappe.msgprint({
                    title: __("Duplicate Entry"),
                    indicator: "red",
                    message: __("Stage <b>{0}</b> is already added at row {1}.", [row.stage_name, duplicate.idx])
                });

                frappe.model.set_value(cdt, cdn, "stage_name", null);
            }
        }
    }
});
function open_reservation_policy(frm, row) {

    let table_rows = [];

    function sync_table_rows() {
        dialog.$wrapper.find("tbody tr").each(function () {
            const idx = parseInt($(this).find(".category").data("idx"));
            if (isNaN(idx)) return;
            table_rows[idx] = {
                category: $(this).find(".category").val(),
                category_name: table_rows[idx] ? table_rows[idx].category_name : "",
                priority: parseInt($(this).find(".priority").val()) || (idx + 1),
                percentage: parseFloat($(this).find(".percentage").val()) || 0,
                allocated_seats: parseInt($(this).find(".allocated_seats").val()) || 0,
                application_fee: parseFloat($(this).find(".application_fee").val()) || 0
            };
        });
    }

    function calculate_row_seats(idx) {
        const total = dialog.get_value("total_seats") || 0;
        const percentage = parseFloat(
            dialog.$wrapper.find(`.percentage[data-idx="${idx}"]`).val()
        ) || 0;
        const seats = Math.floor((total * percentage) / 100);
        dialog.$wrapper.find(`.allocated_seats[data-idx="${idx}"]`).val(seats);
        if (table_rows[idx]) table_rows[idx].allocated_seats = seats;
    }

    function open_category_picker(idx) {
        frappe.prompt(
            [
                {
                    fieldtype: "Link",
                    fieldname: "category_name",
                    label: __("Category Name"),
                    options: "Admission Category",
                    reqd: 1,
                    default: table_rows[idx] ? table_rows[idx].category_name : ""
                }
            ],
            function (values) {
                if (values.category_name) {
                    table_rows[idx].category_name = values.category_name;
                    dialog.$wrapper
                        .find(`.category-name-btn[data-idx="${idx}"]`)
                        .text(values.category_name);
                }
            },
            __("Select Category"),
            __("Select")
        );
    }

    function render_table() {
        const rows_html = table_rows.map((r, idx) => `
    <tr>
        <td>
            <select class="form-control category" data-idx="${idx}">
                <option value="">Select</option>
                <option value="General" ${r.category === "General" ? "selected" : ""}>General</option>
                <option value="Government" ${r.category === "Government" ? "selected" : ""}>Government</option>
                <option value="Management" ${r.category === "Management" ? "selected" : ""}>Management</option>
            </select>
        </td>
        <td>
            <button class="btn btn-default btn-sm category-name-btn" data-idx="${idx}" style="width:100%;">
                ${r.category_name ? frappe.utils.escape_html(r.category_name) : __("Pick Category")}
            </button>
        </td>
        <td>
            <input type="number" class="form-control priority" data-idx="${idx}"
                value="${r.priority || (idx + 1)}">
        </td>
        <td>
            <input type="number" class="form-control percentage" data-idx="${idx}"
                value="${r.percentage || ""}">
        </td>
        <td>
            <input type="number" class="form-control allocated_seats" data-idx="${idx}"
                value="${r.allocated_seats || ""}" readonly>
        </td>
        <td>
            <input type="number" class="form-control application_fee" data-idx="${idx}"
                value="${r.application_fee || ""}">
        </td>
        <td style="text-align:center;">
            <button class="btn btn-danger btn-xs remove-row" data-idx="${idx}">Remove</button>
        </td>
    </tr>
    `).join("");

        dialog.fields_dict.policy_table.$wrapper.html(`
        <div style="overflow-x:auto; margin-bottom:10px;">
            <table class="table table-bordered" style="table-layout:fixed; width:100%;">
                <thead>
                    <tr>
                        <th style="width:20%;">Quota</th>
                        <th style="width:20%;">Category Name</th>
                        <th style="width:12%;">Priority</th>
                        <th style="width:12%;">Percentage</th>
                        <th style="width:12%;">Seats</th>
                        <th style="width:12%;">Fee</th>
                        <th style="width:12%; text-align:center;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows_html}
                </tbody>
            </table>
        </div>
        <button class="btn btn-primary btn-sm" id="add-row-btn">+ Add Row</button>
    `);
    }

    // Tracks whether an existing policy was found
    let existing_policy_name = null;

    function validate_and_save() {
        sync_table_rows();

        if (!table_rows.length) {
            frappe.msgprint(__("Please add at least one category."));
            return;
        }

        for (let i = 0; i < table_rows.length; i++) {
            const r = table_rows[i];
            const rowNum = i + 1;
            if (!r.priority || r.priority <= 0) {
                frappe.msgprint(__(`Row ${rowNum}: Priority must be greater than 0.`));
                return;
            }
            if (!r.percentage || r.percentage <= 0) {
                frappe.msgprint(__(`Row ${rowNum}: Percentage must be greater than 0.`));
                return;
            }
        }

        const total_percent = table_rows.reduce((sum, r) => sum + (parseFloat(r.percentage) || 0), 0);
        if (total_percent !== 100) {
            frappe.msgprint(__("Total percentage must be exactly 100%. Current total: " + total_percent + "%"));
            return;
        }

        // If existing record found, confirm update before saving
        if (existing_policy_name) {
            frappe.confirm(
                __(`A Reservation Policy (<strong>${existing_policy_name}</strong>) already exists for this program. Do you want to update it?`),
                () => do_save(),
                () => { /* user cancelled — do nothing */ }
            );
        } else {
            do_save();
        }
    }

    function do_save() {
        frappe.call({
            method: "slcm.admission.doctype.admission_cycle_program.admission_cycle_program.save_categories",
            args: {
                admission_cycle: dialog.get_value("admission_cycle"),
                program: dialog.get_value("program"),
                total_seats: dialog.get_value("total_seats"),
                status: dialog.get_value("status"),
                policy_document: dialog.get_value("policy_document"),
                payment_gateway: dialog.get_value("payment_gateway"),
                payment_receipt_template: dialog.get_value("payment_receipt_template"),
                reservation_rows: table_rows,
                existing_policy: existing_policy_name || ""   // empty string, not null — null may not pass cleanly
            },
            freeze: true,
            freeze_message: __("Saving Categories..."),
            callback(r) {
                if (!r.exc && r.message) {
                    const res = r.message;
                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "reservation_policy",
                        res.policy_name
                    );

                    // Update current form timestamp to prevent "modified after opened" error
                    if (res.new_modified) {
                        frm.doc.modified = res.new_modified;
                    }

                    frm.refresh_field("programs");
                    frappe.show_alert({
                        message: existing_policy_name
                            ? __("Reservation Policy Updated: ") + res.policy_name
                            : __("Reservation Policy Created: ") + res.policy_name,
                        indicator: "green"
                    });
                    dialog.hide();
                }
            }
        });
    }

    function link_existing_policy() {
        if (!existing_policy_name) return;

        frappe.confirm(
            __(`Do you want to link the existing policy (<strong>${existing_policy_name}</strong>) without making any changes?`),
            () => {
                frappe.model.set_value(
                    row.doctype,
                    row.name,
                    "reservation_policy",
                    existing_policy_name
                );
                frm.refresh_field("programs");
                frappe.show_alert({
                    message: __("Linked existing Reservation Policy: ") + existing_policy_name,
                    indicator: "blue"
                });
                dialog.hide();
            }
        );
    }

    function update_dialog_buttons() {
        if (existing_policy_name) {
            // Change primary label to 'Update Reservation Policy'
            dialog.set_primary_action(__("Update Reservation Policy"), validate_and_save);

            // Add 'Link Existing' secondary button only if not already added
            if (!dialog.$wrapper.find(".btn-link-existing").length) {
                dialog.add_custom_action(__("Link Existing"), link_existing_policy, "btn-link-existing");
            }
        } else {
            dialog.set_primary_action(__("Save Reservation Policy"), validate_and_save);
        }
    }

    const dialog = new frappe.ui.Dialog({
        title: __("Reservation Policy"),
        size: "large",
        fields: [
            {
                fieldtype: "Link",
                fieldname: "admission_cycle",
                label: __("Admission Cycle"),
                options: "Admission Cycle",
                read_only: 1,
                default: frm.doc.name
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Link",
                fieldname: "program",
                label: __("Program"),
                options: "Program",
                read_only: 1,
                default: row.program
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Select",
                fieldname: "status",
                label: __("Status"),
                options: "Active\nClosed",
                default: "Active",
                read_only: 1
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Attach",
                fieldname: "policy_document",
                label: __("Policy Document"),
            },
            { fieldtype: "Section Break" },
            {
                fieldtype: "Link",
                fieldname: "payment_gateway",
                label: __("Payment Gateway"),
                options: "Payment Gateway",
                reqd: 1
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Link",
                fieldname: "payment_receipt_template",
                label: __("Payment Receipt Template"),
                options: "Print Format",
                reqd: 1
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Int",
                fieldname: "total_seats",
                label: __("Total Seats"),
                read_only: 1,
                default: row.seats
            },
            { fieldtype: "Section Break" },
            {
                fieldtype: "HTML",
                fieldname: "policy_table"
            }
        ],
        primary_action_label: __("Save Reservation Policy"),
        primary_action: validate_and_save
    });

    dialog.show();
    dialog.$wrapper.find('.modal-dialog').css("max-width", "75%");
    render_table();

    // Load existing policy if any
    frappe.call({
        method: "frappe.client.get_value",
        args: {
            doctype: "Program Reservation Policy",
            filters: { admission_cycle: frm.doc.name, program: row.program },
            fieldname: ["name", "admission_cycle", "status", "total_seats", "policy_document", "payment_gateway", "payment_receipt_template"]
        },
        callback(res) {
            if (res.message && res.message.name) {
                frappe.call({
                    method: "frappe.client.get",
                    args: {
                        doctype: "Program Reservation Policy",
                        name: res.message.name
                    },
                    callback(r) {
                        if (r.message) {
                            const doc = r.message;

                            frappe.model.set_value(
                                row.doctype,
                                row.name,
                                "seats",
                                doc.total_seats
                            );
                            frm.refresh_field("programs");

                            // Store the existing policy name globally
                            existing_policy_name = doc.name;

                            dialog.set_value("admission_cycle", doc.admission_cycle);
                            dialog.set_value("program", doc.program);
                            dialog.set_value("total_seats", doc.total_seats);
                            dialog.set_value("status", doc.status);
                            dialog.set_value("policy_document", doc.policy_document);
                            dialog.set_value("payment_gateway", doc.payment_gateway);
                            dialog.set_value("payment_receipt_template", doc.payment_receipt_template);

                            table_rows = (doc.categories || []).map(item => ({
                                category: item.reservation_quota || "",
                                category_name: item.category_name || "",
                                priority: item.priority || 0,
                                percentage: item.percentage || "",
                                allocated_seats: item.seats || 0,
                                application_fee: item.application_fee || ""
                            }));

                            render_table();

                            // Update buttons to show Update + Link Existing
                            update_dialog_buttons();

                            frappe.show_alert({
                                message: __("Loaded existing Reservation Policy for: ") + row.program,
                                indicator: "blue"
                            });
                        }
                    }
                });
            }
            // No existing record — dialog stays as new entry mode
        }
    });

    // Event: Open category picker
    dialog.$wrapper.on("click", ".category-name-btn", function () {
        sync_table_rows();
        const idx = parseInt($(this).data("idx"));
        open_category_picker(idx);
    });

    // Event: Auto calculate seats on percentage input
    dialog.$wrapper.on("input", ".percentage", function () {
        const idx = parseInt($(this).data("idx"));
        calculate_row_seats(idx);
    });

    // Event: Add row
    dialog.$wrapper.on("click", "#add-row-btn", function () {
        sync_table_rows();
        table_rows.push({
            category: "",
            category_name: "",
            percentage: "",
            allocated_seats: 0,
            application_fee: ""
        });
        render_table();
    });

    // Event: Remove row
    dialog.$wrapper.on("click", ".remove-row", function () {
        sync_table_rows();
        const idx = parseInt($(this).data("idx"));
        table_rows.splice(idx, 1);
        render_table();
    });
}

function open_program_media(frm, row) {
    let table_rows = [];
    let existing_media_name = null;

    function sync_table_rows() {
        dialog.$wrapper.find("tbody tr").each(function () {
            const idx = parseInt($(this).find(".media_type").data("idx"));
            if (isNaN(idx)) return;
            table_rows[idx] = {
                media_type: $(this).find(".media_type").val(),
                file_url: table_rows[idx] ? table_rows[idx].file_url : "",
                sequence: parseInt($(this).find(".sequence").val()) || 0,
                caption: $(this).find(".caption").val()
            };
        });
    }

    function open_file_picker(idx) {
        frappe.prompt(
            [
                {
                    fieldtype: "Attach",
                    fieldname: "file_url",
                    label: __("Upload File"),
                    reqd: 1,
                    default: table_rows[idx] ? table_rows[idx].file_url : ""
                }
            ],
            function (values) {
                if (values.file_url) {
                    table_rows[idx].file_url = values.file_url;
                    dialog.$wrapper
                        .find(`.file-btn[data-idx="${idx}"]`)
                        .text(values.file_url.split("/").pop());
                }
            },
            __("Upload File"),
            __("Attach")
        );
    }

    function render_table() {
        const rows_html = table_rows.map((r, idx) => `
        <tr>
            <td>
                <select class="form-control media_type" data-idx="${idx}">
                    <option value="">Select</option>
                    <option value="Image" ${r.media_type === "Image" ? "selected" : ""}>Image</option>
                    <option value="Video" ${r.media_type === "Video" ? "selected" : ""}>Video</option>
                </select>
            </td>
            <td>
                <button class="btn btn-default btn-sm file-btn" data-idx="${idx}"
                    style="width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    ${r.file_url ? frappe.utils.escape_html(r.file_url.split("/").pop()) : __("Upload File")}
                </button>
            </td>
            <td>
                <input type="number" class="form-control sequence" data-idx="${idx}"
                    value="${r.sequence || ""}">
            </td>
            <td>
                <input type="text" class="form-control caption" data-idx="${idx}"
                    value="${frappe.utils.escape_html(r.caption || "")}">
            </td>
            <td style="text-align:center; vertical-align:middle;">
                <button class="btn btn-danger btn-xs remove-row" data-idx="${idx}">Remove</button>
            </td>
        </tr>
        `).join("");

        dialog.fields_dict.media_table.$wrapper.html(`
            <div style="overflow-x:auto; margin-bottom:10px;">
                <table class="table table-bordered" style="table-layout:fixed; width:100%;">
                    <thead>
                        <tr>
                            <th style="width:20%;">Media Type</th>
                            <th style="width:20%;">File</th>
                            <th style="width:15%;">Sequence</th>
                            <th style="width:25%;">Caption</th>
                            <th style="width:20%; text-align:center;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows_html}
                    </tbody>
                </table>
            </div>
            <button class="btn btn-primary btn-sm" id="add-media-row-btn">+ Add Row</button>
        `);
    }

    function validate_and_save() {
        sync_table_rows();

        if (!table_rows.length) {
            frappe.msgprint(__("Please add at least one media item."));
            return;
        }

        for (let i = 0; i < table_rows.length; i++) {
            const r = table_rows[i];
            const rowNum = i + 1;

            if (!r.media_type) {
                frappe.msgprint(__(`Row ${rowNum}: Media Type is mandatory.`));
                return;
            }

            if (!r.file_url || r.file_url.trim() === "") {
                frappe.msgprint(__(`Row ${rowNum}: File is mandatory.`));
                return;
            }
        }

        // If existing record, confirm before updating
        if (existing_media_name) {
            frappe.confirm(
                __(`A Program Media record (<strong>${existing_media_name}</strong>) already exists for this program. Do you want to update it?`),
                () => do_save(),
                () => { /* user cancelled — do nothing */ }
            );
        } else {
            do_save();
        }
    }

    function do_save() {
        frappe.call({
            method: "slcm.admission.doctype.admission_cycle_program.admission_cycle_program.save_program_media",
            args: {
                program: dialog.get_value("program"),
                active: dialog.get_value("active"),
                brochure_pdf: dialog.get_value("brochure_pdf"),
                media_rows: table_rows,
                parent_doctype: row.doctype,
                parent_name: row.name,
                existing_media: existing_media_name || null  // backend uses this to update vs insert
            },
            freeze: true,
            freeze_message: __("Saving Program Media..."),
            callback(r) {
                if (!r.exc && r.message) {
                    frappe.model.set_value(
                        row.doctype,
                        row.name,
                        "program_media",
                        r.message
                    );
                    frm.refresh_field("programs");
                    frappe.show_alert({
                        message: existing_media_name
                            ? __("Program Media Updated: ") + r.message
                            : __("Program Media Saved: ") + r.message,
                        indicator: "green"
                    });
                    dialog.hide();
                }
            }
        });
    }

    function link_existing_media() {
        if (!existing_media_name) return;

        frappe.confirm(
            __(`Do you want to link the existing Program Media (<strong>${existing_media_name}</strong>) without making any changes?`),
            () => {
                frappe.model.set_value(
                    row.doctype,
                    row.name,
                    "program_media",
                    existing_media_name
                );
                frm.refresh_field("programs");
                frappe.show_alert({
                    message: __("Linked existing Program Media: ") + existing_media_name,
                    indicator: "blue"
                });
                dialog.hide();
            }
        );
    }

    function update_dialog_buttons() {
        if (existing_media_name) {
            dialog.set_primary_action(__("Update Program Media"), validate_and_save);

            if (!dialog.$wrapper.find(".btn-link-existing-media").length) {
                dialog.add_custom_action(__("Link Existing"), link_existing_media, "btn-link-existing-media");
            }
        } else {
            dialog.set_primary_action(__("Save Program Media"), validate_and_save);
        }
    }

    const dialog = new frappe.ui.Dialog({
        title: __("Program Media"),
        size: "large",
        fields: [
            {
                fieldtype: "Link",
                fieldname: "program",
                label: __("Program"),
                options: "Program",
                read_only: 1,
                default: row.program
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Check",
                fieldname: "active",
                label: __("Active"),
                default: 1
            },
            { fieldtype: "Column Break" },
            {
                fieldtype: "Attach",
                fieldname: "brochure_pdf",
                label: __("Brochure PDF"),
                default: ""
            },
            { fieldtype: "Section Break" },
            {
                fieldtype: "HTML",
                fieldname: "media_table"
            }
        ],
        primary_action_label: __("Save Program Media"),
        primary_action: validate_and_save
    });

    dialog.show();
    render_table();

    // On dialog open — check if Program Media already exists for this program
    frappe.call({
        method: "frappe.client.get_value",
        args: {
            doctype: "Program Media",
            filters: { name: row.program },
            fieldname: ["name", "is_active", "brochure_pdf"]
        },
        callback(res) {
            if (res.message && res.message.name) {
                frappe.call({
                    method: "frappe.client.get",
                    args: {
                        doctype: "Program Media",
                        name: res.message.name
                    },
                    callback(r) {
                        if (r.message) {
                            const doc = r.message;

                            // Store existing record name
                            existing_media_name = doc.name;

                            dialog.set_value("active", doc.is_active);
                            dialog.set_value("brochure_pdf", doc.brochure_pdf || "");

                            table_rows = (doc.media_gallery || []).map(item => ({
                                media_type: item.media_type || "",
                                file_url: item.file || "",
                                sequence: item.sequence || 0,
                                caption: item.caption || ""
                            }));

                            render_table();

                            // Swap buttons to Update + Link Existing
                            update_dialog_buttons();

                            frappe.show_alert({
                                message: __("Loaded existing Program Media for: ") + row.program,
                                indicator: "blue"
                            });
                        }
                    }
                });
            }
            // No existing record — stays as new entry mode
        }
    });

    // Open file picker on button click
    dialog.$wrapper.on("click", ".file-btn", function () {
        sync_table_rows();
        const idx = parseInt($(this).data("idx"));
        open_file_picker(idx);
    });

    // Add row
    dialog.$wrapper.on("click", "#add-media-row-btn", function () {
        sync_table_rows();
        table_rows.push({
            media_type: "",
            file_url: "",
            sequence: "",
            caption: ""
        });
        render_table();
    });

    // Remove row
    dialog.$wrapper.on("click", ".remove-row", function () {
        sync_table_rows();
        const idx = parseInt($(this).data("idx"));
        table_rows.splice(idx, 1);
        render_table();
    });
}