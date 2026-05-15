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
        } else {
            let html_field = frm.get_field("matrix_preview");
            if (html_field && html_field.$wrapper) {
                html_field.$wrapper.empty();
            }
        }
        
        frm.set_df_property("campus", "hidden", 1);
        frm.set_df_property("campus", "reqd", 0);

        // Update Labels for Horizontal table
        frm.get_field("horizontal_reservations").grid.update_docfield_property("seats", "label", __("Target"));
        frm.get_field("horizontal_reservations").grid.update_docfield_property("filled_seats", "label", __("Current Coverage"));
        frm.get_field("horizontal_reservations").grid.update_docfield_property("available_seats", "hidden", 1);

        // Update Labels for Compartmentalised table
        frm.get_field("compartmental_reservations").grid.update_docfield_property("seats", "label", __("Reserved Seats"));
        frm.get_field("compartmental_reservations").grid.update_docfield_property("filled_seats", "label", __("Filled Seats"));

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

            frm.add_custom_button(__("Refresh Availability"), function () {
                frm.call("refresh_availability").then((r) => {
                    if (r.message) {
                        frappe.show_alert({message: __("Availability Refreshed"), indicator: "green"});
                        frm.reload_doc();
                    } else {
                        frappe.show_alert({message: __("No allocations found yet or no changes."), indicator: "orange"});
                    }
                });
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
        frm.set_value("matrix_html", "");
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
    },
    seats: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "available_seats",
            Math.max(0, (row.seats || 0) - (row.filled_seats || 0)));
    }
});

function cal_percentage_seats(frm) {
    const total = frm.doc.total_seats || 0;
    
    // Check Vertical total percentage
    let total_v_percent = 0;
    (frm.doc.categories || []).forEach(r => {
        total_v_percent += (r.percentage || 0);
    });

    if (total_v_percent > 100.001) {
        frappe.show_alert({
            message: __("Total vertical percentage {0}% exceeds 100%!", [total_v_percent.toFixed(2)]),
            indicator: "red"
        });
    }

    ["categories", "horizontal_reservations", "compartmental_reservations"].forEach(table => {
        if (frm.doc[table]) {
            frm.doc[table].forEach(r => {
                if (r.percentage) {
                    frappe.model.set_value(r.doctype, r.name, "seats", Math.round((total * r.percentage) / 100));
                }
            });
            frm.refresh_field(table);
        }
    });
    _show_seat_alert(frm);
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

    // Check percentage first
    let total_v_percent = 0;
    (frm.doc.categories || []).forEach(r => {
        total_v_percent += (r.percentage || 0);
    });

    // Custom Center-Top Alert for Percentage
    if (total_v_percent > 100.001) {
        let msg = __("Total vertical percentage {0}% exceeds 100%!", [total_v_percent.toFixed(2)]);
        if (!$("#v-percent-alert").length) {
            $('<div id="v-percent-alert" style="position: fixed; top: 80px; left: 50%; transform: translateX(-50%); z-index: 9999; background: #fff5f5; color: #c53030; padding: 12px 24px; border-radius: 8px; border: 2px solid #feb2b2; font-weight: 800; font-size: 1.1em; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); display: flex; align-items: center; gap: 10px;">' +
              '<span style="font-size: 1.4em;">⚠️</span>' +
              '<span>' + msg + '</span>' +
              '</div>').appendTo('body');
        } else {
            $("#v-percent-alert").find('span:last').text(msg);
            $("#v-percent-alert").show();
        }
        
        frm.set_intro(__("Total vertical percentage <b>{0}%</b> exceeds 100%. Please adjust.", [total_v_percent.toFixed(2)]), "red");
        frm.dashboard.set_headline_alert(
            __("Total vertical percentage {0}% exceeds 100%. Please fix.", [total_v_percent.toFixed(2)]),
            "red"
        );
    } else {
        $("#v-percent-alert").hide();
        frm.set_intro(null);
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
}
