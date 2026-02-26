frappe.ui.form.on("Program Media", {
    refresh: function (frm) {
        if (frm.doc.is_featured) {
            frm.dashboard.set_headline_alert(__("Shown in Hero Banner"), "blue");
        }
        frm.add_custom_button(__("Preview on Portal"), function () {
            window.open("/desk/applicant-portal", "_blank");
        });
    },

    media_type: function (frm) {
        frm.toggle_display("image", frm.doc.media_type === "Image");
        frm.toggle_display("video_url", frm.doc.media_type === "Video");
        frm.toggle_display("brochure_pdf", frm.doc.media_type === "Brochure");
    }
});
