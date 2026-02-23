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
                const selections = frm.doc.selection_applicant
                    .filter(row => row.selection_status === "Selected")
                    .map(row => row.applicant_id);

                if (!selections || selections.length === 0) {
                    frappe.msgprint(__("No applicants with 'Selected' status found to generate offers."));
                    return;
                }

                frappe.confirm(
                    __("Generate offer letters for {0} selected applicants?").format(selections.length),
                    () => {
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
                                        indicator: error_count > 0 ? 'orange' : 'green',
                                        primary_action: {
                                            label: __("Refresh"),
                                            action: () => frm.reload_doc()
                                        }
                                    });
                                }, 800);
                                return;
                            }

                            const current_applicant = selections[processed];
                            frappe.show_progress(
                                __("Generating Offer Letters"),
                                processed + 1,
                                total,
                                __("Generating for {0}...", [current_applicant])
                            );

                            frappe.call({
                                method: "slcm.api.service.offer_service.bulk_generate_offers",
                                args: {
                                    applicants: [current_applicant]
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
                                    summary_log.push(`<b>${current_applicant}:</b> Connection or Server Error`);
                                    processed++;
                                    processNextBatch();
                                }
                            });
                        };
                        processNextBatch();
                    }
                );
            });
        }
    }
});
