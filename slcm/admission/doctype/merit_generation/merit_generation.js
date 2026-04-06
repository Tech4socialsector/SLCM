// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Merit Generation", {
    refresh(frm) {
        if (frm.doc.status === "Draft" || frm.doc.status === "Failed") {
            frm.add_custom_button(__("Generate Merit List"), () => {
                frm.call({
                    method: "trigger_generation",
                    doc: frm.doc,
                    callback: (r) => {
                        if (!r.exc) {
                            frm.reload_doc();
                        }
                    }
                });
            });
        }

        if (frm.doc.status === "Completed") {
            frm.add_custom_button(__("View Merit List"), () => {
                frappe.db.get_value("Merit List", {
                    admission_cycle: frm.doc.admission_cycle,
                    campus: frm.doc.campus,
                    program_level: frm.doc.generation_type
                }, "name", (r) => {
                    if (r && r.name) {
                        frappe.set_route("Form", "Merit List", r.name);
                    } else {
                        frappe.msgprint(__("Associated Merit List not found."));
                    }
                });
            },);
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
