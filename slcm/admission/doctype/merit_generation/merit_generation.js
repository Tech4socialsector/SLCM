// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Merit Generation", {
    refresh(frm) {
        if (!frm.is_new() && (frm.doc.status === "Draft" || frm.doc.status === "Failed")) {
            frm.add_custom_button(__("Generate Shortlist"), () => {
                frm.call({
                    method: "trigger_generation",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Starting Shortlisting..."),
                    callback: (r) => {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __("Shortlist generated successfully."),
                                indicator: "green"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            });
        }

        if (frm.doc.status === "Completed") {
            frm.add_custom_button(__("View Shortlisting Process"), () => {
                frappe.db.get_value("Shortlisting Process", {
                    admission_cycle: frm.doc.admission_cycle,
                    campus: frm.doc.campus,
                    program_level: frm.doc.generation_type
                }, "name", (r) => {
                    if (r && r.name) {
                        frappe.set_route("Form", "Shortlisting Process", r.name);
                    } else {
                        frappe.msgprint(__("Associated Shortlisting Process not found."));
                    }
                });
            });
        }
    },
    onload: function(frm) {
        frm.set_query("admission_cycle", function() {
            return {
                filters: {
                    status: "Active"
                }
            };
        });
    },
});
