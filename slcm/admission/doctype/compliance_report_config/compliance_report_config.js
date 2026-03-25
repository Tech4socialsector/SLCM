frappe.ui.form.on("Compliance Report Config", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Generate Report", function() {
                frappe.call({
                    method: "slcm.admission.doctype.compliance_report_config.compliance_report_config.generate_report",
                    args: { report_config: frm.doc.name },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: "Report generated successfully.",
                                indicator: "green"
                            }, 5);
                        }
                    }
                });
            }, "Actions");
        }
        // Show mode badge
        const colors = {
            "India": "#FF6F00",
            "International": "#1565C0",
            "Both": "#2E7D32"
        };
        if (frm.doc.compliance_mode) {
            const color = colors[frm.doc.compliance_mode] || "#666";
            frm.dashboard.set_headline(
                `<span style="background:${color};color:white;padding:3px 12px;
                border-radius:12px;font-size:12px;">${frm.doc.compliance_mode} Mode</span>`
            );
        }
    }
});
