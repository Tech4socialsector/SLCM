frappe.ui.form.on("Application Form Response", {
    refresh: function(frm) {
        if (!frm.doc.is_draft) {
            frm.disable_save();
            frm.dashboard.set_headline_alert(__("Application Submitted — Read Only"), "green");
        } else {
            frm.dashboard.set_headline_alert(__("Draft — Not yet submitted"), "orange");
        }
    }
});
