// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Admission Year", {

    async onload(frm) {
        let current_academic_year = await frappe.db.get_single_value(
            "Admission Settings",
            "current_academic_year"
        );
        if (frm.doc.is_active == 1 &&
            frm.doc.academic_year === current_academic_year) {
            frm.set_intro(
                "This Admission Year is active for the academic year " + frm.doc.academic_year + ".",
                "green"
            );
        } else {
            if (frm.doc.academic_year === current_academic_year)
                frm.set_intro(
                    "This Admission Year is not active for the academic year " + frm.doc.academic_year + ".",
                    "yellow"
                );
        }
        if (!frm.doc.academic_year) {
            const value = await frappe.db.get_single_value(
                'Admission Settings',
                'current_academic_year'
            );
            frm.set_value('academic_year', value);
        }
    },

    is_active: async function (frm) {

        if (!frm.doc.is_active) return;

        const confirmed = await new Promise((resolve) => {
            frappe.confirm(
                "Do you want to make this Admission Year Active?",
                () => resolve(true),
                () => resolve(false)
            );
        });

        if (!confirmed) {
            frm.set_value('is_active', 0);
            return;
        }

        const r = await frappe.call({
            method: "slcm.admission.doctype.admission_year.admission_year.activate_admission_year",
            args: {
                admission_year: frm.doc.name,
            }
        });

        if (r.message.status === "success") {
            frappe.msgprint({
                title: __(r.message.status),
                indicator: "green",
                message: __(r.message.message)
            })
            frm.reload_doc();
        } else {
            frappe.msgprint({
                title: __(r.message.status),
                indicator: "red",
                message: __(r.message.message)
            });
            frm.set_value('is_active', 0);
        }
    },

    application_end_date: function (frm) {
        validate_dates(frm);
    },

    application_start_date: function (frm) {
        validate_dates(frm);
    },

    refresh: function (frm) {
        frm.set_query("academic_year", () => {
            return {
                filters: {
                    // is_active: 1,
                }
            }
        });

        frm.set_query(
            "campus",
            "participating_campuses",
            function () {
                return {
                    filters: {
                        is_active: 1,
                        allow_admission: 1
                    }
                };
            }
        );

        configuration_settings(frm);
    },

});


frappe.ui.form.on("Participating Campus", {
    campus(frm, cdt, cdn) {
        child_duplicate_entry(frm, cdt, cdn, "participating_campuses", "campus", "Campus");
    }
});

frappe.ui.form.on("Admission Cycle", {
    cycle_name(frm, cdt, cdn) {
        child_duplicate_entry(frm, cdt, cdn, "cycles", "cycle_name", "Cycle");
    }
})


function child_duplicate_entry(frm, cdt, cdn, child_table, field_name, label) {

    let row = locals[cdt][cdn];
    let value = row[field_name];

    if (!value) return;

    let duplicate_row = frm.doc[child_table].find(d =>
        d.name !== row.name && d[field_name] === value
    );

    if (duplicate_row) {

        let dialog = frappe.msgprint({
            title: __("Duplicate Entry"),
            indicator: "red",
            message: __(
                "{0} '{1}' is already added in Row {2}. Remove it?",
                [label, value, duplicate_row.idx]
            ),
            primary_action: {
                label: __("Remove"),
                action: () => {
                    frappe.model.clear_doc(cdt, cdn);
                    frm.refresh_field(child_table);
                    dialog.hide();
                }
            }
        });

        dialog.$wrapper.find(".modal-header .close").hide();
    }
}

function validate_dates(frm) {

    if (!frm.doc.application_start_date ||
        !frm.doc.application_end_date ||
        !frm.doc.academic_year) {
        return;
    }

    const start_date = frappe.datetime.str_to_obj(frm.doc.application_start_date);
    const end_date = frappe.datetime.str_to_obj(frm.doc.application_end_date);

    if (start_date > end_date) {
        frappe.throw(__("Application Start Date cannot be greater than Application End Date"));
    }

    const academic_parts = frm.doc.academic_year.split("-");

    if (academic_parts.length !== 2) {
        frappe.throw(__("Invalid Academic Year format. Expected format: YYYY-YYYY"));
    }

    const academic_start_year = parseInt(academic_parts[0]);
    const academic_end_year = parseInt(academic_parts[1]);

    const start_year = start_date.getFullYear();
    const end_year = end_date.getFullYear();

    if (start_year !== academic_start_year) {
        frappe.throw(__("Application Start Date must be in Academic Start Year {0}", [academic_start_year]));
    }

    if (end_year !== academic_end_year) {
        frappe.throw(__("Application End Date must be in Academic End Year {0}", [academic_end_year]));
    }
}

function configuration_settings(frm) {
    frm.set_df_property("enable_scholarship", "read_only", frm.doc.is_active ? 0 : 1);
    frm.set_df_property("enable_interview", "read_only", frm.doc.is_active ? 0 : 1);
    frm.set_df_property("enable_reservation", "read_only", frm.doc.is_active ? 0 : 1);
    frm.set_df_property("allow_campus_enrollment", "read_only", frm.doc.is_active ? 0 : 1);
}