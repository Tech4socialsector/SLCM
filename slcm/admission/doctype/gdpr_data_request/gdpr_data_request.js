frappe.ui.form.on("GDPR Data Request", {
    refresh: function(frm) {
        const status_colors = {
            "Pending": "orange",
            "In Review": "blue",
            "Completed": "green",
            "Rejected": "red"
        };
        const color = status_colors[frm.doc.status] || "grey";
        frm.dashboard.set_headline(
            `<span style="color:${color};font-weight:bold;">Status: ${frm.doc.status || "Pending"}</span>`
        );
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button("Preview Data Export", function() {
                frappe.call({
                    method: "slcm.admission.utils.compliance.gdpr_export_preview",
                    args: { applicant: frm.doc.applicant },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: "Data Export Preview",
                                message: `<pre>${JSON.stringify(r.message, null, 2)}</pre>`,
                                wide: true
                            });
                        }
                    }
                });
            });
        }
    }
});
