frappe.ui.form.on("Program Media", {
    refresh: function (frm) {
        if (frm.doc.is_featured) {
            frm.dashboard.set_headline_alert(__("Shown in Hero Banner"), "blue");
        }
        frm.add_custom_button(__("Preview on Portal"), function () {
            window.open("/desk/applicant-portal", "_blank");
        });
    },
});
