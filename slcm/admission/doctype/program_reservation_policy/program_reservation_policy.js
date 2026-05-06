frappe.ui.form.on("Program Reservation Policy", {
    setup: function (frm) {
        frm.set_query("category_name", "categories", function () {
            return { filters: { reservation_type: "Vertical" } };
        });
        frm.set_query("category_name", "horizontal_reservations", function () {
            return { filters: { reservation_type: "Horizontal" } };
        });
        frm.set_query("category_name", "compartmental_reservations", function () {
            return { filters: { reservation_type: "Compartmentalised Horizontal" } };
        });
    },
    refresh: function (frm) {
        if (frm.doc.matrix_html) {
            let html_field = frm.get_field("matrix_preview");
            if (html_field && html_field.$wrapper) {
                html_field.$wrapper.html(frm.doc.matrix_html);
            }
        }
        
        frm.set_df_property("campus", "hidden", 1);
        frm.set_df_property("campus", "reqd", 0);

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
    },

    btn_generate_matrices: function(frm) {
        if (frm.is_new() || frm.is_dirty()) {
            frappe.msgprint(__("Please save the document before generating matrices."));
            return;
        }
        if (!frm.doc.total_seats || !frm.doc.categories || frm.doc.categories.length === 0) {
            frappe.msgprint(__("Please enter Total Seats and configure Main Categories first."));
            return;
        }
        frappe.call({
            method: "slcm.admission.doctype.program_reservation_policy.program_reservation_policy.generate_matrices",
            args: { name: frm.doc.name },
            callback: function(r) {
                if (!r.exc) {
                    frappe.show_alert({message: __("Matrices Generated Successfully"), indicator: "green"});
                    frm.reload_doc().then(() => {
                        if (frm.doc.matrix_html) {
                            let html_field = frm.get_field("matrix_preview");
                            if (html_field && html_field.$wrapper) {
                                html_field.$wrapper.html(frm.doc.matrix_html);
                            }
                        }
                    });
                }
            }
        });
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

frappe.ui.form.on("Program Reservation Sub Quota", {
    priority: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.priority) {
            let table = frm.doc[row.parentfield] || [];
            let duplicate = table.find(r => r.name !== row.name && r.priority === row.priority);
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
    }
});

function cal_percentage_seats(frm) {
    const total = frm.doc.total_seats || 0;
    ["categories", "horizontal_reservations", "compartmental_reservations"].forEach(table => {
        if (frm.doc[table]) {
            frm.doc[table].forEach(r => {
                if (r.percentage) {
                    frappe.model.set_value(r.doctype, r.name, "seats", Math.floor((total * r.percentage) / 100));
                }
            });
            frm.refresh_field(table);
        }
    });
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
