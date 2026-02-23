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
        // Filter merit_rule by this program offering's admission cycle and programme_level
        frm.set_query("merit_rule", function () {
            return {
                filters: {
                    admission_cycle: frm.doc.admission_cycle,
                    program_level: frm.doc.programme_level,
                    is_active: 1
                }
            };
        });

        // Show Set Merit Rule button if cycle enables merit list
        check_and_add_merit_rule_button(frm);
    },

    admission_cycle(frm) {
        if (!frm.doc.admission_cycle) return;
        // Auto-fetch programme_level from cycle
        frappe.db.get_value(
            "Admission Cycle",
            frm.doc.admission_cycle,
            ["programme_level", "enable_merit_list"],
            function (r) {
                if (r && r.programme_level) {
                    frm.set_value("programme_level", r.programme_level);
                }
                check_and_add_merit_rule_button(frm, r);
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
        calculate_reservation_seats(frm);
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

function calculate_reservation_seats(frm) {
    let total = frm.doc.total_available_seats || 0;
    if (frm.doc.reservations) {
        frm.doc.reservations.forEach(row => {
            if (row.reservation_percentage) {
                row.seats = Math.floor((total * row.reservation_percentage) / 100);
            }
        });
        frm.refresh_field("reservations");
    }
}

function check_and_add_merit_rule_button(frm, cycle_data) {
    // Remove existing button first to avoid duplicates
    frm.remove_custom_button(__("Set Merit Rule"));

    if (!frm.doc.admission_cycle) return;

    const do_check = (enable_merit_list) => {
        if (enable_merit_list) {
            frm.add_custom_button(__("Set Merit Rule"), function () {
                open_merit_rule_dialog(frm);
            }, __("Actions"));
        }
    };

    if (cycle_data && cycle_data.enable_merit_list !== undefined) {
        do_check(cycle_data.enable_merit_list);
    } else {
        frappe.db.get_value("Admission Cycle", frm.doc.admission_cycle, "enable_merit_list", function (r) {
            do_check(r && r.enable_merit_list);
        });
    }
}

function open_merit_rule_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __("Set Merit Rule"),
        fields: [
            {
                label: __("Link Existing Merit Rule"),
                fieldname: "existing_rule",
                fieldtype: "Link",
                options: "Merit Rule",
                get_query: function () {
                    return {
                        filters: {
                            admission_cycle: frm.doc.admission_cycle,
                            program_level: frm.doc.programme_level,
                            is_active: 1
                        }
                    };
                },
                description: __("Select an existing rule, or fill the fields below to create a new one.")
            },
            { fieldname: "or_divider", fieldtype: "Section Break", label: __("— OR Create New Rule —") },
            {
                label: __("Rule Name"),
                fieldname: "rule_name",
                fieldtype: "Data"
            },
            {
                label: __("Version"),
                fieldname: "version",
                fieldtype: "Int",
                default: 1
            },
            {
                label: __("Effective From"),
                fieldname: "effective_from",
                fieldtype: "Date"
            },
            {
                label: __("Effective To"),
                fieldname: "effective_to",
                fieldtype: "Date"
            },
            {
                label: __("Is Active"),
                fieldname: "is_active",
                fieldtype: "Check",
                default: 1
            },
            {
                fieldname: "components_section",
                fieldtype: "Section Break",
                label: __("Components")
            },
            {
                label: __("Components"),
                fieldname: "components",
                fieldtype: "Table",
                fields: [
                    {
                        label: __("Component Type"),
                        fieldname: "component_type",
                        fieldtype: "Select",
                        options: "\nHSC Percentage\nEntrance Test\nInterview",
                        in_list_view: 1,
                        reqd: 1
                    },
                    {
                        label: __("Weight (%)"),
                        fieldname: "weight",
                        fieldtype: "Float",
                        in_list_view: 1,
                        reqd: 1
                    },
                    {
                        label: __("Is Active"),
                        fieldname: "is_active",
                        fieldtype: "Check",
                        in_list_view: 1,
                        default: 1
                    }
                ]
            }
        ],
        primary_action_label: __("Save & Link"),
        primary_action(values) {
            if (values.existing_rule) {
                // Just link existing rule
                frm.set_value("merit_rule", values.existing_rule);
                frm.save();
                d.hide();
            } else if (values.rule_name) {
                // Create new Merit Rule doc, then link it
                frappe.call({
                    method: "slcm.admission.doctype.program_offering.program_offering.create_merit_rule",
                    args: {
                        program_offering: frm.doc.name,
                        admission_cycle: frm.doc.admission_cycle,
                        programme_level: frm.doc.programme_level,
                        rule_name: values.rule_name,
                        version: values.version || 1,
                        effective_from: values.effective_from,
                        effective_to: values.effective_to,
                        is_active: values.is_active,
                        components: values.components || []
                    },
                    callback: function (r) {
                        if (r.message) {
                            frm.set_value("merit_rule", r.message);
                            frm.save();
                            frappe.show_alert({
                                message: __("Merit Rule '{0}' created and linked.", [r.message]),
                                indicator: "green"
                            });
                        }
                    }
                });
                d.hide();
            } else {
                frappe.msgprint(__("Please select an existing rule or fill the Rule Name to create a new one."));
            }
        }
    });
    d.show();
}
