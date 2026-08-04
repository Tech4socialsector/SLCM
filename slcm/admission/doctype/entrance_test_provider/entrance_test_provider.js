frappe.ui.form.on("Entrance Test Provider", {
    setup(frm) {
        set_program_query(frm);
    },
    refresh(frm) {
        calculate_totals(frm);

        frm.set_query("user", function() {
            return {
                query: "slcm.admission.doctype.entrance_test_provider.entrance_test_provider.get_user_query"
            };
        });

        set_program_query(frm);
    }
});

function set_program_query(frm) {
    frm.set_query("program", "programme_capacity", function() {
        return {
            query: "slcm.admission.doctype.entrance_test_provider.entrance_test_provider.get_active_cycle_programs"
        };
    });
}

frappe.ui.form.on("Programme Capacity", {
    program: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.program) return;

        let duplicate = (frm.doc.programme_capacity || []).some(
            r => r.name !== row.name && r.program === row.program
        );

        if (duplicate) {
            frappe.show_alert({
                message: __("Programme '{0}' is already added.", [row.program]),
                indicator: "orange"
            }, 5);

            frappe.msgprint({
                title: __("Duplicate Programme"),
                message: __("Programme <b>{0}</b> has already been selected.", [row.program]),
                indicator: "orange"
            });

            frappe.model.set_value(cdt, cdn, "program", "");
        }
    },
    capacity: function (frm, cdt, cdn) {
        update_row_available(cdt, cdn);
        calculate_totals(frm);
    },
    reserved_seats: function (frm, cdt, cdn) {
        update_row_available(cdt, cdn);
        calculate_totals(frm);
    },
    programme_capacity_remove: function (frm) {
        calculate_totals(frm);
    }
});

function update_row_available(cdt, cdn) {
    let row = locals[cdt][cdn];
    let cap = row.capacity || 0;
    let res = row.reserved_seats || 0;
    frappe.model.set_value(cdt, cdn, "available_capacity", Math.max(0, cap - res));
}

var calculate_totals = function (frm) {
    let total_cap = 0;
    let total_res = 0;
    (frm.doc.programme_capacity || []).forEach(row => {
        let cap = row.capacity || 0;
        let res = row.reserved_seats || 0;
        total_cap += cap;
        total_res += res;
    });

    if (total_cap > 0 || (frm.doc.programme_capacity || []).length > 0) {
        frm.set_value("total_capacity", total_cap);
        frm.set_value("reserved_seats", total_res);
        frm.set_value("available_capacity", Math.max(0, total_cap - total_res));
    }
};
