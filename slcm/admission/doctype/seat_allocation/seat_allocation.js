// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Seat Allocation", {

    merit_list(frm) {
        // Auto-fill Admission Cycle, Campus, Program Level from the selected Merit List
        if (frm.doc.merit_list) {
            frappe.db.get_value(
                "Merit List",
                frm.doc.merit_list,
                ["admission_cycle", "campus", "program_level"]
            ).then(r => {
                if (r.message) {
                    frm.set_value("admission_cycle", r.message.admission_cycle);
                    frm.set_value("campus", r.message.campus);
                    frm.set_value("program_level", r.message.program_level);
                }
            });
        } else {
            frm.set_value("admission_cycle", null);
            frm.set_value("campus", null);
            frm.set_value("program_level", null);
        }
    },

    refresh(frm) {
        if (frm.doc.status === "Draft" || frm.doc.status === "Allocated") {
            frm.add_custom_button(__("Get Merit List"), () => {
                if (!frm.doc.merit_list) {
                    frappe.msgprint({
                        title: __("Missing Merit List"),
                        message: __("Please select a Merit List before pulling data."),
                        indicator: "orange"
                    });
                    return;
                }

                frappe.confirm(
                    __("This will replace all existing rows in the Selection Applicant table. Continue?"),
                    () => {
                        frm.call({
                            method: "pull_from_merit_list",
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __("Pulling applicants from Merit List..."),
                            callback(r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __("Applicants pulled successfully from Merit List."),
                                        indicator: "green"
                                    });
                                }
                            }
                        });
                    }
                );
            });
        }

        if (frm.doc.status === "Draft" || frm.doc.status === "Allocated") {
            frm.add_custom_button(__("Allocate Seats"), () => {
                frm.call({
                    method: "allocate_seats",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Allocating seats based on merit and capacity..."),
                    callback(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                        }
                    }
                });
            }, __("Actions"));
        }

        if (frm.doc.status === "Allocated") {
            frm.add_custom_button(__("Publish Allocation"), () => {
                frappe.confirm(
                    __("Are you sure you want to publish this allocation? This action is irreversible."),
                    () => {
                        frm.call({
                            method: "publish_allocation",
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __("Publishing allocation..."),
                            callback(r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __("Actions"));
        }

        if (frm.doc.status === "Published") {
            frm.add_custom_button(__("Generate Offer Letters"), () => {
                const applicants = frm.doc.selection_applicant
                    .filter(row => row.selection_status === "Selected")
                    .map(row => ({
                        applicant_id: row.applicant_id,
                        program: row.program,
                        selection_status: row.selection_status,
                        name: row.name // childcare record name for internal reference
                    }));

                if (applicants.length === 0) {
                    frappe.msgprint(__("No applicants with 'Selected' status found to generate offers."));
                    return;
                }

                let d = new frappe.ui.Dialog({
                    title: __("Generate Offer Letters"),
                    size: "extra-large",
                    fields: [
                        {
                            label: __("Admission Cycle"),
                            fieldname: "dialog_admission_cycle",
                            fieldtype: "Link",
                            options: "Admission Cycle",
                            read_only: 1,
                            default: frm.doc.admission_cycle,
                            columns: 4
                        },
                        {
                            fieldtype: "Column Break",
                        },
                        {
                            label: __("Campus"),
                            fieldname: "dialog_campus",
                            fieldtype: "Link",
                            options: "Campus",
                            read_only: 1,
                            default: frm.doc.campus,
                            columns: 4
                        },
                        {
                            fieldtype: "Column Break",
                        },
                        {
                            label: __("Admission Year"),
                            fieldname: "dialog_admission_year",
                            fieldtype: "Link",
                            options: "Admission Year",
                            read_only: 1,
                            columns: 4
                        },
                        {
                            fieldtype: "Section Break",
                        },
                        {
                            label: __("Selected Applicants"),
                            fieldname: "applicants_grid",
                            fieldtype: "Table",
                            cannot_add_rows: true,
                            cannot_delete_rows: true,
                            page_length: 20,
                            fields: [
                                {
                                    fieldname: "applicant_id",
                                    fieldtype: "Data",
                                    label: __("Applicant ID"),
                                    in_list_view: 1,
                                    read_only: 1
                                },
                                {
                                    fieldname: "program",
                                    fieldtype: "Link",
                                    options: "Program",
                                    label: __("Program"),
                                    in_list_view: 1,
                                    read_only: 1
                                },
                                {
                                    fieldname: "selection_status",
                                    fieldtype: "Select",
                                    label: __("Status"),
                                    in_list_view: 1,
                                    read_only: 1
                                }
                            ],
                            data: applicants
                        }
                    ],
                    primary_action_label: __("Generate {0} Offers", [applicants.length]),
                    primary_action(values) {
                        const selections = d.fields_dict.applicants_grid.grid.get_selected_children()
                            .map(row => ({
                                applicant: row.applicant_id,
                                campus: frm.doc.campus,
                                cycle: frm.doc.admission_cycle,
                                program: row.program
                            }));

                        if (selections.length === 0) {
                            frappe.msgprint(__("Please select at least one applicant."));
                            return;
                        }

                        d.hide();

                        // --- LARGE BATCH HANDLING (> 10) ---
                        if (selections.length > 10) {
                            frappe.dom.freeze(__("Submitting batch to background queue..."));
                            frappe.call({
                                method: "slcm.api.service.offer_service.bulk_generate_offers",
                                args: { applicants: selections },
                                callback: function (r) {
                                    frappe.dom.unfreeze();
                                    if (r.message && r.message.queued) {
                                        frappe.msgprint({
                                            title: __("Processing Started"),
                                            message: r.message.message,
                                            indicator: 'blue'
                                        });
                                    }
                                }
                            });
                            return;
                        }

                        // --- SMALL BATCH SEQUENTIAL HANDLING (<= 10) ---
                        const total = selections.length;
                        frappe.show_progress(__("Generating Offer Letters"), 0, total, __("Initializing..."));

                        let processed = 0;
                        let success_count = 0;
                        let error_count = 0;
                        let summary_log = [];

                        const processNextBatch = () => {
                            if (processed >= total) {
                                frappe.show_progress(__("Generating Offer Letters"), total, total, __("Process Completed."));
                                setTimeout(() => {
                                    frappe.hide_progress();
                                    let message = __("Successfully generated {0} offers.", [success_count]);
                                    if (error_count > 0) {
                                        message += "<br><br>" + __("<b>{0} errors encountered:</b>", [error_count]);
                                        message += '<div style="max-height: 200px; overflow-y: auto; font-size: 11px; margin-top: 10px; background: #fff5f5; border: 1px solid #ffcccc; padding: 10px; border-radius: 4px;">';
                                        message += summary_log.join("<br>");
                                        message += '</div>';
                                    }
                                    frappe.msgprint({
                                        title: __("Bulk Offer Generation Report"),
                                        message: message,
                                        indicator: error_count > 0 ? 'orange' : 'green'
                                    });
                                }, 800);
                                return;
                            }

                            const payload = selections[processed];
                            const current_applicant = payload.applicant;
                            frappe.show_progress(
                                __("Generating Offer Letters"),
                                processed + 1,
                                total,
                                __("Generating for {0}...", [current_applicant])
                            );

                            frappe.call({
                                method: "slcm.api.service.offer_service.bulk_generate_offers",
                                args: {
                                    applicants: [payload] // Passing the full dict
                                },
                                callback: function (r) {
                                    if (r.message) {
                                        const result = r.message;
                                        if (result.success && result.success.length > 0) {
                                            success_count++;
                                        }
                                        if (result.errors && result.errors.length > 0) {
                                            error_count++;
                                            summary_log.push(`<b>${current_applicant}:</b> ${result.errors[0].error}`);
                                        }
                                    }
                                    processed++;
                                    processNextBatch();
                                },
                                error: function (err) {
                                    error_count++;
                                    let server_error = "";
                                    if (err._server_messages) {
                                        try {
                                            const messages = JSON.parse(err._server_messages);
                                            server_error = messages.map(m => JSON.parse(m).message).join(", ");
                                        } catch (e) {
                                            server_error = "Server Error (Check Logs)";
                                        }
                                    } else if (err.message) {
                                        server_error = err.message;
                                    } else {
                                        server_error = "Connection or Server Error";
                                    }
                                    summary_log.push(`<b>${current_applicant}:</b> ${server_error}`);
                                    processed++;
                                    processNextBatch();
                                }
                            });
                        };
                        processNextBatch();
                    }
                });

                d.show();

                // Fetch and set Admission Year from Admission Cycle
                if (frm.doc.admission_cycle) {
                    frappe.db.get_value("Admission Cycle", frm.doc.admission_cycle, "admission_year")
                        .then(r => {
                            if (r.message && r.message.admission_year) {
                                d.set_value("dialog_admission_year", r.message.admission_year);
                            }
                        });
                }

                // Select all by default and hide grid action buttons
                setTimeout(() => {
                    const grid = d.fields_dict.applicants_grid.grid;
                    if (grid) {
                        grid.wrapper.find('.grid-add-row').hide();
                        grid.wrapper.find('.grid-remove-rows').hide();
                        grid.data.forEach(row => row.__checked = 1);
                        grid.refresh();
                    }
                }, 300);
            });
        }
    }
});
