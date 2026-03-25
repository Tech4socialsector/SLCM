frappe.ui.form.on("Exam Type Config", {
    refresh: function(frm) {
        const colors = {
            "National": "#1F4E79",
            "State": "#E65100",
            "Institution-Own": "#2E7D32",
            "Merit-Based": "#666666",
            "International": "#6A1B9A"
        };
        if (frm.doc.exam_category) {
            const color = colors[frm.doc.exam_category] || "#666666";
            frm.dashboard.set_headline(
                `<span style="background:${color};color:white;padding:3px 12px;
                border-radius:12px;font-size:12px;">${frm.doc.exam_category}</span>`
            );
        }
    },
    score_import_method: function(frm) {
        if (frm.doc.score_import_method === "CSV Upload" && !frm.doc.csv_field_mapping) {
            frm.set_value("csv_field_mapping", JSON.stringify({
                "example_csv_column": "system_field_name"
            }, null, 2));
        }
    }
});
