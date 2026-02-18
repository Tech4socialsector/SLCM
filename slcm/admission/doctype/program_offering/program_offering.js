// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Program Offering", {
    refresh(frm) {

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
