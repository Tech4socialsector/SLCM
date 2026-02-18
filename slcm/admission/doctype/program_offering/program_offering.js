// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Program Offering", {
    refresh(frm) {
        if (!frm.doc.admission_year) {
            return;
        }
        configure_stages(frm);
    },
    async onload(frm) {
        if (!frm.doc.academic_year) {
            const value = await frappe.db.get_single_value(
                'Admission Settings',
                'current_academic_year'
            );
            frm.set_value('academic_year', value);
        }

        frm.set_query('admission_year', () => {
            return {
                filters: {
                    academic_year: frm.doc.academic_year,
                    is_active: 1
                }
            }
        })
    },
});

frappe.ui.form.on("Program Offering Criteria", {
    program(frm, cdt, cdn) {
        child_duplicate_entry(
            frm,
            cdt,
            cdn,
            "programs",
            "program",
            "Program"
        )
    }
})

function configure_stages(frm) {
    frappe.call({
        method: "slcm.admission.doctype.program_offering.program_offering.configuration_settings",
        args: {
            admission_year: frm.doc.admission_year
        },
        callback: function (r) {
            if (!r.message) return;

            if (r.message.status === "Error") {
                frappe.msgprint({
                    title: "Error",
                    message: r.message.message,
                    indicator: "red"
                })
                return;
            }

            if (!r.message.enable_interview) {
                frm.set_value("interview_required", 0);
            }
            frm.set_df_property(
                "interview_required",
                "read_only",
                r.message.enable_interview ? 0 : 1
            );

            if (!r.message.enable_scholarship) {
                frm.set_value("scholarship_applicable", 0);
            }
            frm.set_df_property(
                "scholarship_applicable",
                "read_only",
                r.message.enable_scholarship ? 0 : 1
            );

            if (!r.message.enable_reservation) {
                frm.set_value("is_reservation_applicable", 0);
            }
            frm.set_df_property(
                "is_reservation_applicable",
                "read_only",
                r.message.enable_reservation ? 0 : 1
            );

        },
        error: (e) => {
            frappe.msgprint(e.message);
        }
    });
}


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
