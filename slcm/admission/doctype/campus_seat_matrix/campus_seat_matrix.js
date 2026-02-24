frappe.ui.form.on("Campus Seat Matrix", {
    refresh: function(frm) {
        if (frm.doc.is_locked) {
            frm.dashboard.set_headline(
                `<span style="color: red; font-weight: bold;">
                🔒 Seat Matrix Locked
                </span>`
            );
            frm.disable_save();
        }
        if (frm.doc.total_seats) {
            const filled = frm.doc.filled_seats || 0;
            const pct = Math.round((filled / frm.doc.total_seats) * 100);
            const color = pct >= 90 ? "red" : pct >= 70 ? "orange" : "green";
            frm.dashboard.add_comment(
                `Seats Filled: ${filled}/${frm.doc.total_seats} (${pct}%)`,
                color
            );
        }
    },
    total_seats: function(frm) {
        frm.set_value(
            "available_seats",
            frm.doc.total_seats - (frm.doc.filled_seats || 0)
        );
    }
});