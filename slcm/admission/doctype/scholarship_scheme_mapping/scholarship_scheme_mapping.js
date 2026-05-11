// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Scheme Mapping", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Sync Count"), () => {
                frm.call({
                    doc: frm.doc,
                    method: "sync_count",
                    callback: (r) => {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __("Count synced successfully. Current Count: {0}", [r.message]),
                                indicator: "green"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, __("Actions"));
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
