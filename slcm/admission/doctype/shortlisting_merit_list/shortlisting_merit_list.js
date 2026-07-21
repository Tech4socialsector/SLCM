frappe.ui.form.on("Shortlisting Merit List", {
    refresh(frm) {
        if (!frm.is_new()) {
            if (frm.doc.status === "In Progress") {
                start_shortlist_progress_polling(frm);
            }

            frm.add_custom_button(__("Run Shortlisting Merit List Logic"), function () {
                frappe.call({
                    method: "execute_shortlisting_logic",
                    doc: frm.doc,
                    freeze: true,
                    callback: function () {
                        frm.reload_doc();
                        frappe.show_alert(__("Shortlisting Merit List logic executed successfully."));
                    }
                });
            }, __("Actions"));

            frm.add_custom_button(__("Generate Final Admission Merit"), function () {
                frappe.confirm(__("This will generate the final Merit List (Part A + Part B). Continue?"), function () {
                    frappe.show_progress(__("Generating Final Merit List"), 0, 100, __("Starting Final Merit List generation..."));
                    start_shortlist_progress_polling(frm);

                    frappe.call({
                        method: "generate_final_merit_list",
                        doc: frm.doc,
                        callback: function (r) {
                            if (frm._progress_interval) {
                                clearInterval(frm._progress_interval);
                                frm._progress_interval = null;
                            }
                            frappe.hide_progress();

                            if (r.message) {
                                frappe.show_alert({
                                    message: __("Final Merit List generated: " + r.message),
                                    indicator: "green"
                                });
                                frappe.set_route("Form", "Merit List", r.message);
                            }
                        },
                        error: function() {
                            if (frm._progress_interval) {
                                clearInterval(frm._progress_interval);
                                frm._progress_interval = null;
                            }
                            frappe.hide_progress();
                        }
                    });
                });
            }, __("Actions"));

            frm.add_custom_button(__("Download Merit List"), function () {
                let d = new frappe.ui.Dialog({
                    title: __('Download Shortlisting Merit List'),
                    fields: [
                        {
                            label: __('Download Type'),
                            fieldname: 'download_type',
                            fieldtype: 'Select',
                            options: [
                                { label: __('Overall Master List'), value: 'Overall' },
                                { label: __('Category Wise'), value: 'Category Wise' }
                            ],
                            default: 'Overall',
                            reqd: 1
                        },
                        {
                            label: __('Specific Category'),
                            fieldname: 'category',
                            fieldtype: 'Select',
                            options: [
                                { label: __('All Categories'), value: 'All' },
                                { label: __('General List'), value: 'General' },
                                { label: __('SC List'), value: 'SC' },
                                { label: __('ST List'), value: 'ST' },
                                { label: __('OBC List'), value: 'OBC' },
                                { label: __('EWS List'), value: 'EWS' },
                                { label: __('Karnataka Students'), value: 'Karnataka' },
                                { label: __('Women Merit List'), value: 'Women' },
                                { label: __('PWD Merit List'), value: 'PWD' }
                            ],
                            depends_on: "eval:doc.download_type == 'Category Wise'",
                            default: 'All'
                        }
                    ],
                    primary_action_label: __('Download'),
                    primary_action(values) {
                        let url = frappe.urllib.get_full_url(
                            "/api/method/slcm.admission.doctype.shortlisting_merit_list.shortlisting_merit_list.download_merit_list?" +
                            "name=" + encodeURIComponent(frm.doc.name) +
                            "&download_type=" + encodeURIComponent(values.download_type) +
                            "&category=" + encodeURIComponent(values.category || "")
                        );
                        window.open(url, '_blank');
                        d.hide();
                    }
                });
                d.show();
            }, __("Actions"));
        }
    },
    onload(frm) {
        frm.set_query("program", function () {
            let filters = {};
            if (frm.doc.program_level) {
                filters["level_of_study"] = frm.doc.program_level;
            }
            return { filters: filters };
        });
    },
    program_level(frm) {
        frm.set_query("program", function () {
            let filters = {};
            if (frm.doc.program_level) {
                filters["level_of_study"] = frm.doc.program_level;
            }
            return { filters: filters };
        });
        if (frm.doc.program && frm.doc.program_level) {
            frappe.db.get_value("Programme", frm.doc.program, "level_of_study", (r) => {
                if (r && r.level_of_study && r.level_of_study !== frm.doc.program_level) {
                    frm.set_value("program", "");
                }
            });
        }
    }
});

function start_shortlist_progress_polling(frm) {
    if (frm._progress_interval) {
        clearInterval(frm._progress_interval);
    }

    let progress_dialog = null;

    frm._progress_interval = setInterval(() => {
        frappe.call({
            method: "slcm.admission.doctype.shortlisting_merit_list.shortlisting_merit_list.get_generation_progress",
            args: {
                docname: frm.doc.name
            },
            callback: (res) => {
                let data = res.message;
                if (data) {
                    let percent = Math.round(data.percent || 0);
                    let desc = data.description || __("Processing applicants...");
                    if (data.status === "In Progress") {
                        if (!progress_dialog) {
                            progress_dialog = frappe.show_progress(__("Generating Final Merit List"), percent, 100, desc);
                        } else {
                            frappe.show_progress(__("Generating Final Merit List"), percent, 100, desc);
                        }
                    } else if (data.status === "Completed" || data.status === "Failed") {
                        clearInterval(frm._progress_interval);
                        frm._progress_interval = null;
                        frm.dirty(false);
                        frm.reload_doc().then(() => {
                            frappe.hide_progress();
                        });
                    }
                }
            }
        });
    }, 500);
}
