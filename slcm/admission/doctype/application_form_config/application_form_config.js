frappe.ui.form.on("Application Form Config", {
    refresh: function(frm) {
        if (frm.doc.is_active) {
            frm.dashboard.set_headline(
                `<span style="color: green; font-weight: bold;">
                ✓ Active Form - Version ${frm.doc.version}
                </span>`
            );
        }
        if (!frm.is_new()) {
            frm.add_custom_button("View Condition Rules", function() {
                frappe.set_route("List", "Form Condition Rule", {
                    form_config: frm.doc.name
                });
            });
        }
    }
});