frappe.ui.form.on("Institution Settings", {
    refresh: function(frm) {
        if (!frm.doc.onboarding_complete) {
            frm.dashboard.set_headline(
                '<span style="color:orange;font-weight:bold;">⚠ Onboarding not complete. Run Setup Wizard to activate.</span>'
            );
        } else {
            frm.dashboard.set_headline(
                '<span style="color:green;font-weight:bold;">✓ Institution is active and configured.</span>'
            );
        }
        // frm.add_custom_button("Open Setup Wizard", function() {
        //     frappe.set_route("admission-setup-wizard");
        // });
    },
    enable_multi_campus: function(frm) {
        frappe.show_alert({
            message: frm.doc.enable_multi_campus
                ? "Multi-campus mode enabled. Campus fields will appear throughout the system."
                : "Single campus mode. Campus fields will be hidden.",
            indicator: frm.doc.enable_multi_campus ? "green" : "blue"
        }, 5);
    }
});
