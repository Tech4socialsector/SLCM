// Copyright (c) 2026, TFSS and contributors
// Program Offering Client Script

frappe.ui.form.on("Program Offering", {

    refresh(frm) {
        // Filter campus to active only
        frm.set_query("campus", function () {
            return { filters: { is_active: 1 } };
        });
        // Filter admission_cycle to active/draft only
        frm.set_query("admission_cycle", function () {
            return { filters: { status: ["in", ["Active", "Draft"]], docstatus: ["!=", 2] } };
        });
    },

    admission_cycle(frm) {
        if (!frm.doc.admission_cycle) return;
        // Auto-fetch programme_level from cycle
        frappe.db.get_value(
            "Admission Cycle",
            frm.doc.admission_cycle,
            "programme_level",
            function (r) {
                if (r && r.programme_level) {
                    frm.set_value("programme_level", r.programme_level);
                }
            }
        );
    },

    campus(frm) {
        if (!frm.doc.campus) return;
        frappe.db.get_value("Campus", frm.doc.campus, "is_active", function (r) {
            if (r && !r.is_active) {
                frappe.msgprint({
                    title: __("Inactive Campus"),
                    message: __("Campus '{0}' is currently inactive and cannot be used for a Program Offering.", [frm.doc.campus]),
                    indicator: "orange"
                });
                frm.set_value("campus", "");
            }
        });
    },

    is_reservation_applicable(frm) {
        if (!frm.doc.is_reservation_applicable) {
            frm.clear_table("reservations");
            frm.refresh_field("reservations");
        }
    },
    total_available_seats(frm) {
        calculate_total_seats(frm);
    }
});

frappe.ui.form.on("Program Offering Reservation", {
    reservation_percentage(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.reservation_percentage && frm.doc.total_available_seats) {
            row.seats = Math.floor((frm.doc.total_available_seats * row.reservation_percentage) / 100);
            frm.refresh_field("reservations");
        }
    }
});

function calculate_total_seats(frm) {
    let total = (frm.doc.total_available_seats || 0);

    // Recalculate all reservation seats if total available seats changes
    if (frm.doc.reservations) {
        frm.doc.reservations.forEach(row => {
            if (row.reservation_percentage) {
                row.seats = Math.floor((total * row.reservation_percentage) / 100);
            }
        });
        frm.refresh_field("reservations");
    }
}
