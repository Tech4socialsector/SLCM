// Copyright (c) 2026, TFSS and contributors
// Campus Seat Matrix Client Script

frappe.ui.form.on("Campus Seat Matrix", {

    refresh(frm) {
        // Always make filled_seats and available_seats read-only
        frm.set_df_property("filled_seats", "read_only", 1);
        frm.set_df_property("available_seats", "read_only", 1);

        // Filter: Reservation Category — only active
        frm.set_query("reservation_category", function () {
            return { filters: { is_active: 1 } };
        });

        // Filter: Program Offering filtered by admission cycle of selected round
        if (frm.doc.admission_round) {
            set_program_offering_filter(frm);
        }
    },

    admission_round(frm) {
        if (!frm.doc.admission_round) return;
        // Show cycle dates as helper text and filter program_offering
        frappe.db.get_value(
            "Admission Round",
            frm.doc.admission_round,
            ["admission_cycle", "start_date", "end_date"],
            function (r) {
                if (r) {
                    frm.set_intro(
                        __("Round Dates: {0} to {1} | Cycle: {2}", [r.start_date, r.end_date, r.admission_cycle]),
                        "blue"
                    );
                    frm.doc._admission_cycle = r.admission_cycle;
                    set_program_offering_filter(frm);
                }
            }
        );
    },

    program_offering(frm) {
        if (!frm.doc.program_offering) return;
        // Show total_seats of selected Program Offering as helper text
        frappe.db.get_value("Program Offering", frm.doc.program_offering, "total_seats", function (r) {
            if (r && r.total_seats) {
                frappe.show_alert({
                    message: __("Program Offering total seats: {0} — all category rows must sum to {0}", [r.total_seats]),
                    indicator: "blue"
                });
            }
        });
    },

    total_seats(frm) {
        // Re-check sum on change
        if (!frm.doc.program_offering || !frm.doc.admission_round) return;
        frappe.call({
            method: "frappe.client.get_value",
            args: {
                doctype: "Program Offering",
                fieldname: "total_seats",
                filters: { name: frm.doc.program_offering }
            },
            callback(r) {
                if (!r.message) return;
                const po_total = r.message.total_seats;
                const my_seats = frm.doc.total_seats || 0;
                if (my_seats > po_total) {
                    frappe.msgprint({
                        title: __("Seat Mismatch Warning"),
                        message: __("Your total seats ({0}) exceed the Program Offering total seats ({1}). All rows must sum to {1}.", [my_seats, po_total]),
                        indicator: "red"
                    });
                }
            }
        });
    }
});

function set_program_offering_filter(frm) {
    const cycle = frm.doc._admission_cycle;
    frm.set_query("program_offering", function () {
        if (cycle) {
            return { filters: { admission_cycle: cycle } };
        }
        return {};
    });
}
