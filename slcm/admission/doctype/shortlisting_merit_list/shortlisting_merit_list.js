frappe.ui.form.on("Shortlisting Merit List", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Run Shortlisting Merit List Logic"), function() {
                frappe.call({
                    method: "execute_shortlisting_logic",
                    doc: frm.doc,
                    freeze: true,
                    callback: function() {
                        frm.reload_doc();
                        frappe.show_alert(__("Shortlisting Merit List logic executed successfully."));
                    }
                });
            }, __("Actions"));

            frm.add_custom_button(__("Generate Final Admission Merit"), function() {
                frappe.confirm(__("This will generate the final Merit List (Entrance + Interview). Continue?"), function() {
                    frappe.call({
                        method: "generate_final_merit_list",
                        doc: frm.doc,
                        freeze: true,
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert(__("Final Merit List generated: " + r.message));
                                frappe.set_route("Form", "Merit List", r.message);
                            }
                        }
                    });
                });
            }, __("Actions"));
        }
    }
});
