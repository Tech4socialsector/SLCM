frappe.listview_settings['Applicant'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__("Generate Offer Letters"), function () {
            new frappe.ui.form.MultiSelectDialog({
                doctype: "Applicant",
                target: listview,
                setters: {
                    application_status: "Approved",
                    academic_year: null,
                    campus: null,
                    admission_cycle: null
                },
                add_filters_group: 1,
                get_query() {
                    return {
                        filters: {
                            application_status: "Approved",
                            docstatus: 0
                        }
                    };
                },
                action(selections) {
                    if (!selections || selections.length === 0) {
                        frappe.msgprint(__("Please select at least one applicant."));
                        return;
                    }

                    // Hide the dialog
                    this.dialog.hide();

                    // Show Progress
                    const total = selections.length;
                    frappe.show_progress(__("Generating Offer Letters"), 0, total, __("Initializing...e"));

                    let processed = 0;
                    let success_count = 0;
                    let error_count = 0;
                    let summary_log = [];

                    /**
                     * We process selections in chunks or one by one to show real progress.
                     * Calling the bulk API in a loop for granular progress tracking.
                     */
                    const processNextBatch = () => {
                        if (processed >= total) {
                            // Completion logic
                            frappe.show_progress(__("Generating Offer Letters"), total, total, __("Process Completed."));

                            setTimeout(() => {
                                frappe.hide_progress();

                                let message = __("Successfully generated {0} offers.").format(success_count);
                                if (error_count > 0) {
                                    message += "<br><br>" + __("{0} errors encountered:").format(error_count);
                                    message += '<div style="max-height: 200px; overflow-y: auto; font-size: 12px; margin-top: 10px;">';
                                    message += summary_log.join("<br>");
                                    message += '</div>';
                                }

                                frappe.msgprint({
                                    title: __("Bulk Offer Generation Report"),
                                    message: message,
                                    indicator: error_count > 0 ? 'orange' : 'green',
                                    primary_action: {
                                        label: __("Refresh List"),
                                        action: () => listview.refresh()
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
                            __(`Generating for ${current_applicant}...`)
                        );

                        frappe.call({
                            method: "slcm.api.service.bulk_generate_offers", // From __init__.py mapping
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
            });
        }, __("Actions"));
    }
};
