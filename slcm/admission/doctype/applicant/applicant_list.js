frappe.listview_settings['Applicant'] = {
    refresh: function (listview) {
        listview.page.add_inner_button(__("Bulk Download Forms"), function () {
            // Safer way to get filter values
            const get_val = (fieldname) => {
                if (listview.filter_area && listview.filter_area.get_filter_value) {
                    return listview.filter_area.get_filter_value(fieldname);
                }
                return null;
            };

            let d = new frappe.ui.Dialog({
                title: __("Bulk Download Application Forms"),
                fields: [
                    { label: __("Campus"), fieldname: "campus", fieldtype: "Link", options: "Campus", default: get_val("campus") },
                    { label: __("Program"), fieldname: "program", fieldtype: "Link", options: "Program", default: get_val("program") },
                    { label: __("Admission Cycle"), fieldname: "admission_cycle", fieldtype: "Link", options: "Admission Cycle", default: get_val("admission_cycle") },
                    { label: __("Academic Year"), fieldname: "academic_year", fieldtype: "Link", options: "Academic Year", default: get_val("academic_year") },
                    { label: __("Admission Year"), fieldname: "admission_year", fieldtype: "Link", options: "Admission Year", default: get_val("admission_year") },
                    { label: __("Status"), fieldname: "application_status", fieldtype: "Link", options: "Applicant Status", default: get_val("application_status") },
                    { fieldtype: "Section Break" },
                    { 
                        label: __("Print Format"), 
                        fieldname: "print_format", 
                        fieldtype: "Link", 
                        options: "Print Format", 
                        default: "Applicant Application Form",
                        get_query: () => {
                            return { filters: { doc_type: "Applicant" } };
                        }
                    }
                ],
                primary_action_label: __("Generate ZIP"),
                primary_action(values) {
                    d.hide();
                    
                    frappe.dom.freeze(__("Preparing Bulk Download..."));
                    
                    frappe.call({
                        method: "slcm.admission.doctype.applicant.applicant.get_bulk_applications_zip",
                        args: values,
                        callback: function (r) {
                            frappe.dom.unfreeze();
                            if (r.message && r.message.queued) {
                                frappe.show_progress(__("Starting Download"), 0, 100, __("Preparing background task..."));
                            } else if (r.message && r.message.file_url) {
                                // Sync success
                                window.open(r.message.file_url);
                                frappe.show_alert({ message: __("Generated {0} forms.", [r.message.success]), indicator: 'green' });
                            }
                        }
                    });
                }
            });
            d.show();
        });

        // LISTEN FOR PROGRESS
        frappe.realtime.on("bulk_download_progress", (data) => {
            frappe.show_progress(__("Generating ZIP"), data.progress, data.total, data.message);
        });

        // AUTO-DOWNLOAD ON COMPLETION
        frappe.realtime.on("bulk_download_complete", (data) => {
            if (data.doctype === "Applicant") {
                frappe.hide_progress();
                if (data.file_url) {
                    window.open(data.file_url);
                }
            }
        });
    }
};