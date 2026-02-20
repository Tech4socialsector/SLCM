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

    total_seats(frm) {
        check_seat_counts(frm);
    },

    open_seats(frm) {
        check_seat_counts(frm);
    }
});

function check_seat_counts(frm) {
    if (frm.doc.open_seats && frm.doc.total_seats && frm.doc.open_seats > frm.doc.total_seats) {
        frappe.msgprint({
            title: __("Seat Count Error"),
            message: __("Open Category Seats ({0}) cannot exceed Total Seats ({1}).", [frm.doc.open_seats, frm.doc.total_seats]),
            indicator: "red"
        });
    }
}
