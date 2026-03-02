frappe.ui.form.on("Applicant Notification", {
    refresh: function(frm) {
        const colors = {
            "Stage Update": "blue",
            "Document Request": "orange",
            "Offer": "green",
            "Fee": "red",
            "General": "grey"
        };
        const color = colors[frm.doc.notification_type] || "grey";
        frm.dashboard.set_headline_alert(
            __(frm.doc.notification_type),
            color
        );
    }
});
