frappe.ui.form.on("Program Reservation Category", {
    seats: function(frm, cdt, cdn) {
        _calc_available(cdt, cdn);
    },
    filled_seats: function(frm, cdt, cdn) {
        _calc_available(cdt, cdn);
    }
});

function _calc_available(cdt, cdn) {
    const row = locals[cdt][cdn];
    frappe.model.set_value(
        cdt, cdn, "available_seats",
        Math.max(0, (row.seats || 0) - (row.filled_seats || 0))
    );
}
