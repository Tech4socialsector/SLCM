frappe.ui.form.on("Evaluation Config", {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button("Check Weightage", function() {
                const components = frm.doc.scoring_components || [];
                const total = components.reduce((sum, c) => sum + (c.weightage || 0), 0);
                const color = Math.abs(total - 100) < 0.01 ? "green" : "red";
                frappe.show_alert({
                    message: `Total weightage: ${total}% (${color === "green" ? "✓ Valid" : "✗ Must be 100%"})`,
                    indicator: color
                }, 5);
            });
        }
    }
});

frappe.ui.form.on("Score Component", {
    weightage: function(frm) {
        const components = frm.doc.scoring_components || [];
        const total = components.reduce((sum, c) => sum + (c.weightage || 0), 0);
        if (total > 100) {
            frappe.show_alert({message: `Total weightage is ${total}% — exceeds 100%.`, indicator: "red"}, 4);
        }
    }
});
