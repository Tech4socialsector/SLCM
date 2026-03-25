frappe.ui.form.on("CLAT Rank Import", {
    refresh: function(frm) {
        const status_colors = {
            "Pending": "gray",
            "Processing": "blue",
            "Completed": "green",
            "Failed": "red"
        };
        const color = status_colors[frm.doc.status] || "gray";
        frm.dashboard.set_headline(
            `<span style="color: ${color}; font-weight: bold;">
            Import Status: ${frm.doc.status}
            </span>`
        );
        if (frm.doc.status === "Completed") {
            frm.dashboard.add_comment(
                `✓ ${frm.doc.total_records} records imported successfully`,
                "green"
            );
        }
        if (frm.doc.status === "Failed") {
            frm.dashboard.add_comment(
                "✗ Import failed. Check Error Log below.",
                "red"
            );
        }
    }
});