frappe.ui.form.on("Quota Policy Entry", {
    mandated_percentage: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.mandated_percentage > 0 && frm.doc.total_seats) {
            const seats = Math.floor((row.mandated_percentage / 100) * frm.doc.total_seats);
            frappe.model.set_value(cdt, cdn, "mandated_seats", seats);
        }
    }
});
