frappe.ui.form.on("Program Media", {
    refresh: function (frm) {
        if (frm.doc.is_featured) {
            frm.dashboard.set_headline_alert(__("Shown in Hero Banner"), "blue");
        }
    },
});
