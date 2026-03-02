frappe.ui.form.on("Applicant Portal Config", {
    refresh: function (frm) {
        if (!frm.doc.portal_active) {
            frm.dashboard.set_headline_alert(
                __("Portal is currently INACTIVE — applicants see maintenance page"),
                "orange"
            );
        } else {
            frm.dashboard.set_headline_alert(__("Portal is LIVE"), "green");
        }
        frm.add_custom_button(__("Preview Portal"), function () {
            window.open("/desk/applicant-portal", "_blank");
        }, __("Actions"));
        if (frm.doc.skip_fee_check_for_testing) {
            frm.dashboard.set_headline_alert(
                __("WARNING: Fee check is disabled. Enable only for testing."),
                "red"
            );
        }
    }
});
