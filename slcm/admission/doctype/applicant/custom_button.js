/**
 * Bulk Offer Letter Generation Button
 * Path: slcm/admission/doctype/applicant/custom_button.js
 * 
 * Note: For this to work automatically in the List View, 
 * it should typically be named 'applicant_list.js'.
 */

frappe.listview_settings['Applicant'] = {
    onload: function (listview) {
        // Add Generate Offer Letters button under 'Actions' group
        listview.page.add_inner_button(__("Generate Offer Letters"), function () {

            // Initialize MultiSelectDialog to selection Applicants
            new frappe.ui.form.MultiSelectDialog({
                doctype: "Applicant",
                target: listview,
                setters: {
                    application_status: "Approved", // Default setter for filter
                    academic_year: null,
                    campus: null,
                    admission_cycle: null
                },
                add_filters_group: 1, // Allows users to add more filters in dialog
                // get_query() {
                //     return {
                //         filters: {
                //             application_status: "Approved", // Only offers for approved applicants
                //             docstatus: 0
                //         }
                //     };
                // },
                action(selections) {
                    if (!selections || selections.length === 0) {
                        frappe.msgprint(__("Please select at least one applicant."));
                        return;
                    }

                    // Hide the selection dialog
                    this.dialog.hide();

                    // Initialize Progress Bar
                    const total = selections.length;
                    frappe.show_progress(__("Generating Offer Letters"), 0, total, __("Initializing..."));

                    let processed = 0;
                    let success_count = 0;
                    let error_count = 0;
                    let summary_log = [];
                    console.log("Generating Offer Letters initialized");
                    console.log("Total applicants: " + total);
                    console.log("Selections: " + selections);
                    /**
                     * Recursive function to process selections one by one.
                     * This approach provides a smooth real-time progress bar experience.
                     */
                    const process_next = () => {
                        console.log("Processing next applicant");
                        if (processed >= total) {
                            // Final completion update
                            console.log("Process Completed");
                            frappe.show_progress(__("Generating Offer Letters"), total, total, __("Process Completed."));

                            setTimeout(() => {
                                console.log("Process Completed");
                                frappe.hide_progress();

                                let message = __("Successfully generated {0} offers.").format(success_count);
                                if (error_count > 0) {
                                    message += "<br><br>" + __("<b>{0} errors encountered:</b>").format(error_count);
                                    message += '<div style="max-height: 200px; overflow-y: auto; font-size: 11px; margin-top: 10px; background: #fff5f5; border: 1px solid #ffcccc; padding: 10px; border-radius: 4px;">';
                                    message += summary_log.join("<br>");
                                    message += '</div>';
                                }

                                frappe.msgprint({
                                    title: __("Bulk Generation Summary"),
                                    message: message,
                                    indicator: error_count > 0 ? 'orange' : 'green',
                                    primary_action: {
                                        label: __("Refresh View"),
                                        action: () => listview.refresh()
                                    }
                                });
                            }, 800);
                            return;
                        }

                        const current_applicant = selections[processed];

                        // Update progress label
                        frappe.show_progress(
                            __("Generating Offer Letters"),
                            processed + 1,
                            total,
                            __("Processing {0}...").format(current_applicant)
                        );

                        // Server call for single applicant generation
                        console.log("Server call for single applicant generation");
                        frappe.call({
                            method: "slcm.api.service.bulk_generate_offers",
                            args: {
                                applicants: [current_applicant]
                            },
                            callback: function (r) {
                                console.log("Server call for single applicant generation callback");
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
                                process_next();
                            },
                            error: function (err) {
                                console.log("Server call for single applicant generation error");
                                error_count++;
                                summary_log.push(`<b>${current_applicant}:</b> ${err.message || __("Internal Server Error")}`);
                                processed++;
                                process_next();
                            }
                        });
                    };

                    // Start processing
                    process_next();
                }
            });
        }, __("Actions"));
    }
};
