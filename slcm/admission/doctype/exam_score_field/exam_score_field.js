frappe.ui.form.on("Exam Score Field", {
    is_primary_score: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.is_primary_score) {
            const table = frm.doc.score_fields || [];
            table.forEach(function(r) {
                if (r.name !== cdn && r.is_primary_score) {
                    frappe.model.set_value(r.doctype, r.name, "is_primary_score", 0);
                }
            });
            frappe.show_alert({
                message: row.field_name + " set as primary score for merit calculation.",
                indicator: "green"
            }, 3);
        }
    }
});
