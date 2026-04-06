frappe.ui.form.on("Program Reservation Policy", {
    refresh(frm) {
        frappe.db.get_single_value("Institution Settings", "enable_multi_campus")
            .then((val) => {
                const enabled = parseInt(val || 0, 10) === 1;
                frm.set_df_property("campus", "hidden", enabled ? 0 : 1);
                frm.set_df_property("campus", "reqd", enabled ? 1 : 0);
                if (!enabled && frm.doc.campus) {
                    frm.set_value("campus", "");
                }
            });
    },
});

frappe.ui.form.on("Program Reservation Policy", {

    refresh: function (frm) {
        const status_colors = {
            "Draft": "gray", "Active": "green", "Locked": "red"
        };
        frm.dashboard.set_headline_alert(
            __(frm.doc.status),
            status_colors[frm.doc.status] || "gray"
        );

        if (!frm.is_new()) {
            _show_seat_alert(frm);

            if (frm.doc.status === "Draft") {
                frm.add_custom_button(__("Activate"), function () {
                    frappe.confirm(
                        __("Activate this reservation policy? It will be linked to the admission cycle."),
                        function () {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Program Reservation Policy",
                                    name: frm.doc.name,
                                    fieldname: "status",
                                    value: "Active"
                                },
                                callback: function () { frm.reload_doc(); }
                            });
                        }
                    );
                }, __("Actions"));
            }

            if (frm.doc.status === "Active") {
                frm.add_custom_button(__("Lock"), function () {
                    frappe.confirm(
                        __("Lock this policy? No further changes will be allowed."),
                        function () {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Program Reservation Policy",
                                    name: frm.doc.name,
                                    fieldname: "status",
                                    value: "Locked"
                                },
                                callback: function () { frm.reload_doc(); }
                            });
                        }
                    );
                }, __("Actions"));
            }

            frm.add_custom_button(__("View on Admission Cycle"), function () {
                frappe.set_route("Form", "Admission Cycle", frm.doc.admission_cycle);
            }, __("Actions"));
        }
    },

    total_seats: function (frm) {
        _recalc(frm);
        cal_percentage_seats(frm);
    }
});

frappe.ui.form.on("Program Reservation Category", {
    priority: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.priority) {
            let duplicate = (frm.doc.categories || []).find(r => r.name !== row.name && r.priority === row.priority);
            if (duplicate) {
                frappe.msgprint({
                    title: __("Duplicate Priority"),
                    message: __("Priority {0} is already used for {1}. Please use a unique priority.", [row.priority, duplicate.category_name]),
                    indicator: "orange"
                });
                frappe.model.set_value(cdt, cdn, "priority", "");
            }
        }
    },
    percentage: function (frm, cdt, cdn) {
        cal_percentage_seats(frm);
    },
    seats: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "available_seats",
            Math.max(0, (row.seats || 0) - (row.filled_seats || 0)));
        _recalc(frm);
    },
    categories_remove: function (frm) {
        _recalc(frm);
    }
});

function cal_percentage_seats(frm) {
    const total = frm.doc.total_seats || 0;
    if (frm.doc.categories) {
        frm.doc.categories.forEach(r => {
            if (r.percentage) {
                r.seats = Math.floor((total * r.percentage) / 100);
            }
        });
        frm.refresh_field("categories");
    }
}

function _recalc(frm) {
    const total = frm.doc.total_seats || 0;
    let allocated = 0;
    (frm.doc.categories || []).forEach(r => {
        allocated += (r.seats || 0);
    });
    frm.set_value("total_allocated", allocated);
    frm.set_value("total_available", Math.max(0, total - allocated));
    frm.refresh_field("total_allocated");
    frm.refresh_field("total_available");
    _show_seat_alert(frm);
}

function _show_seat_alert(frm) {
    const total = frm.doc.total_seats || 0;
    const allocated = frm.doc.total_allocated || 0;
    const diff = total - allocated;

    if (diff < 0) {
        frm.dashboard.set_headline_alert(
            __("Category seats exceed total seats by {0}. Please fix.", [Math.abs(diff)]),
            "red"
        );
    } else if (diff > 0) {
        frm.dashboard.set_headline_alert(
            __("{0} of {1} seats assigned. {2} seats unassigned (will go to General pool).",
                [allocated, total, diff]),
            "orange"
        );
    } else {
        frm.dashboard.set_headline_alert(
            __("All {0} seats fully assigned across categories.", [total]),
            "green"
        );
    }
}
