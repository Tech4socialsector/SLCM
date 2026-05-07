// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Seat Allocation", {

    setup(frm) {
        frm.set_query("merit_list", () => {
            let filters = {
                "docstatus": 1 // Only submitted merit lists
            };
            if (frm.doc.admission_cycle) filters.admission_cycle = frm.doc.admission_cycle;
            if (frm.doc.campus) filters.campus = frm.doc.campus;
            if (frm.doc.program_level) filters.program_level = frm.doc.program_level;
            return { filters: filters };
        });
    },

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
        // Prevent selecting past dates for published_on
        frm.set_df_property("published_on", "options", {
            minDate: new Date()
        });

        if (frm.doc.status === "Draft") {
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

        if (frm.doc.status === "Draft") {
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
                    primary_action_label: __("Generate Offers"),
                    primary_action(values) {
                        const selections = d.fields_dict.applicants_grid.grid.get_selected_children()
                            .map(row => ({
                                applicant: row.applicant_id,
                                campus: frm.doc.campus,
                                cycle: frm.doc.admission_cycle,
                                program: row.program,
                                admission_year: values.dialog_admission_year
                            }));

                        if (!values.dialog_admission_year) {
                            frappe.msgprint({
                                title: __("Missing Configuration"),
                                message: __("Admission Year is required to generate offer letters. Please ensure the Admission Cycle is correctly configured."),
                                indicator: "red"
                            });
                            return;
                        }

                        if (selections.length === 0) {
                            frappe.msgprint(__('Please select at least one applicant.'));
                            return;
                        }

                        d.hide();

                        if (selections.length > 120) {
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
                                            indicator: 'blue',
                                            primary_action: {
                                                label: __('View Offer Letters'),
                                                action: () => frappe.set_route('List', 'Offer Letter')
                                            }
                                        });
                                    }
                                }
                            });
                            return;
                        }

                        // SMALL BATCH PROCESSING
                        const total = selections.length;
                        frappe.show_progress(__("Generating Offer Letters"), 0, total, __("Preparing..."));

                        let processed = 0, success_count = 0, error_count = 0, summary_log = [];

                        const process_next = () => {
                            if (processed >= total) {
                                frappe.show_progress(__("Generating Offer Letters"), total, total, __("Completed."));
                                setTimeout(() => {
                                    frappe.hide_progress();
                                    
                                    let message = `
                                        <div style="padding: 10px;">
                                            <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                                                <div style="flex: 1; padding: 12px; background: #f0fff4; border: 1px solid #c6f6d5; border-radius: 8px; text-align: center;">
                                                    <h3 style="margin: 0; color: #2f855a;">${success_count}</h3>
                                                    <div style="font-size: 11px; color: #38a169; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Successful')}</div>
                                                </div>
                                                <div style="flex: 1; padding: 12px; background: ${error_count > 0 ? '#fff5f5' : '#f7fafc'}; border: 1px solid ${error_count > 0 ? '#fed7d7' : '#edf2f7'}; border-radius: 8px; text-align: center;">
                                                    <h3 style="margin: 0; color: ${error_count > 0 ? '#c53030' : '#718096'};">${error_count}</h3>
                                                    <div style="font-size: 11px; color: ${error_count > 0 ? '#e53e3e' : '#a0aec0'}; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Failed')}</div>
                                                </div>
                                            </div>
                                    `;

                                    if (error_count > 0) {
                                        message += `
                                            <div style="margin-bottom: 8px; font-weight: 600; color: #4a5568;">${__('Generation Failures:')}</div>
                                            <div style="max-height: 250px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px;">
                                                <table class="table table-bordered table-condensed" style="margin:0; font-size: 12px; background: #fff;">
                                                    <thead style="background: #f8fafc;">
                                                        <tr>
                                                            <th style="width: 35%;">${__('Applicant')}</th>
                                                            <th>${__('Reason for Failure')}</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        ${summary_log.map(item => `
                                                            <tr>
                                                                <td style="font-weight: 600;">${item.applicant}</td>
                                                                <td style="color: #e53e3e; word-break: break-word;">${item.error}</td>
                                                            </tr>
                                                        `).join('')}
                                                    </tbody>
                                                </table>
                                            </div>
                                        `;
                                    }
                                    message += `</div>`;

                                    frappe.msgprint({
                                        title: __('Offer Generation Report'),
                                        message: message,
                                        wide: true,
                                        indicator: error_count === 0 ? 'green' : (success_count > 0 ? 'orange' : 'red'),
                                        primary_action: {
                                            label: __('View Offer Letters'),
                                            action: () => frappe.set_route('List', 'Offer Letter')
                                        }
                                    });
                                }, 1000);
                                return;
                            }

                            const payload = selections[processed];
                            frappe.show_progress(__("Generating Offer Letters"), processed + 1, total, __("Processing {0}", [payload.applicant]));

                            frappe.call({
                                method: "slcm.api.service.offer_service.bulk_generate_offers",
                                args: { applicants: [payload] },
                                callback: (r) => {
                                    if (r.message) {
                                        if (r.message.success?.length) success_count++;
                                        if (r.message.errors?.length) {
                                            error_count++;
                                            summary_log.push(r.message.errors[0]);
                                        }
                                    }
                                    processed++;
                                    process_next();
                                },
                                error: (err) => {
                                    error_count++;
                                    summary_log.push({
                                        applicant: payload.applicant,
                                        error: __("Unexpected Server Error")
                                    });
                                    processed++;
                                    process_next();
                                }
                            });
                        };
                        process_next();
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

        if (frm.doc.status === "Published") {
            frm.add_custom_button(__("Unpublish"), () => {
                frappe.confirm(
                    __("This will hide results from students. Continue?"),
                    () => {
                        frm.call({
                            method: "unpublish_allocation",
                            doc: frm.doc,
                            callback(r) {
                                if (!r.exc) {
                                    frm.reload_doc();
                                    frappe.show_alert({
                                        message: __("Allocation unpublished."),
                                        indicator: "orange"
                                    });
                                }
                            }
                        });
                    }
                );
            }, __("Actions"));
        }
    }
});
