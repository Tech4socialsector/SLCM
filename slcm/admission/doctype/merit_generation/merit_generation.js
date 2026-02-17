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
    },
});
