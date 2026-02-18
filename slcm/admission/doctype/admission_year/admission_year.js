// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Admission Year", {

    async onload(frm) {
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
    }

});


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
        frappe.throw(__("Application End Date must be in Academic Start Year {0}", [academic_end_year]));
    }
}
