frappe.ui.form.on("Entrance Test Provider", {
    refresh(frm) {
        // Calculate totals on refresh to ensure accuracy
        calculate_totals(frm);
    }
});

frappe.ui.form.on("Provider Room", {
    room_capacity: function (frm, cdt, cdn) {
        calculate_room_available(frm, cdt, cdn);
    },
    room_reserved_seats: function (frm, cdt, cdn) {
        calculate_room_available(frm, cdt, cdn);
    },
    provider_room_remove: function (frm) {
        calculate_totals(frm);
    }
});

/**
 * Calculates available capacity for a single room
 */
var calculate_room_available = function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let available = (row.room_capacity || 0) - (row.room_reserved_seats || 0);
    frappe.model.set_value(cdt, cdn, "room_available_capacity", available);

    // Update parent totals
    calculate_totals(frm);
};

/**
 * Calculates global totals for the provider based on all rooms
 */
var calculate_totals = function (frm) {
    let total_cap = 0;
    let total_reserved = 0;
    let total_available = 0;

    (frm.doc.provider_room || []).forEach(row => {
        total_cap += (row.room_capacity || 0);
        total_reserved += (row.room_reserved_seats || 0);
        total_available += (row.room_available_capacity || 0);
    });

    frm.set_value("total_capacity", total_cap);
    frm.set_value("reserved_seats", total_reserved);
    frm.set_value("available_capacity", total_available);
};
