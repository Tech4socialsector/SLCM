// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Merit Generation", {
    refresh(frm) {
        if (!frm.is_new()) {
            if (frm.doc.status === "In Progress") {
                start_merit_progress_polling(frm);
            } else if (frm.doc.status === "Draft" || frm.doc.status === "Failed") {
                frm.add_custom_button(__("Generate Shortlist"), () => {
                    start_merit_progress_polling(frm);
                    frm.call({
                        method: "trigger_generation",
                        doc: frm.doc,
                        callback: (r) => {
                            if (!r.exc && r.message && r.message.success) {
                                if (!r.message.async) {
                                    frappe.show_alert({
                                        message: __("Shortlist generated successfully."),
                                        indicator: "green"
                                    });
                                }
                            } else if (r.message && r.message.error) {
                                frappe.msgprint({
                                    title: __("Generation Failed"),
                                    indicator: "red",
                                    message: r.message.error
                                });
                            }
                            frm.dirty(false);
                            frm.reload_doc();
                        }
                    });
                });
            }

            if (frm.doc.status === "Completed") {
                frm.add_custom_button(__("View Shortlisting Merit List"), () => {
                    let sp_filters = {
                        admission_cycle: frm.doc.admission_cycle,
                        campus: frm.doc.campus,
                        program_level: frm.doc.generation_type
                    };
                    if (frm.doc.program) {
                        sp_filters["program"] = frm.doc.program;
                    }

                    frappe.db.get_value("Shortlisting Merit List", sp_filters, "name", (r) => {
                        if (r && r.name) {
                            frappe.set_route("Form", "Shortlisting Merit List", r.name);
                        } else {
                            frappe.msgprint(__("Associated Shortlisting Merit List not found."));
                        }
                    });
                });
            }
        }
    },
    onload: function (frm) {
        frm.set_query("admission_cycle", function () {
            return {
                filters: {
                    status: "Active"
                }
            };
        });
        frm.set_query("program", function () {
            let filters = {};
            if (frm.doc.generation_type) {
                filters["level_of_study"] = frm.doc.generation_type;
            }
            return { filters: filters };
        });
    },
    generation_type: function (frm) {
        frm.set_query("program", function () {
            let filters = {};
            if (frm.doc.generation_type) {
                filters["level_of_study"] = frm.doc.generation_type;
            }
            return { filters: filters };
        });
        if (frm.doc.program && frm.doc.generation_type) {
            frappe.db.get_value("Programme", frm.doc.program, "level_of_study", (r) => {
                if (r && r.level_of_study && r.level_of_study !== frm.doc.generation_type) {
                    frm.set_value("program", "");
                }
            });
        }
    }
});

function start_merit_progress_polling(frm) {
    if (frm._progress_interval) {
        clearInterval(frm._progress_interval);
    }

    let progress_dialog = null;

    frm._progress_interval = setInterval(() => {
        frappe.call({
            method: "slcm.admission.doctype.merit_generation.merit_generation.get_generation_progress",
            args: {
                docname: frm.doc.name
            },
            callback: (res) => {
                let data = res.message;
                if (data) {
                    let percent = Math.round(data.percent || 0);
                    let desc = data.description || `Processing applicants...`;

                    if (data.status === "In Progress") {
                        if (!progress_dialog) {
                            progress_dialog = frappe.show_progress(__("Generating Merit List"), percent, 100, desc);
                        } else {
                            frappe.show_progress(__("Generating Merit List"), percent, 100, desc);
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
    }, 800);
}
