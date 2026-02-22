frappe.ui.form.on('Applicant', {
    validate: function (frm) {
        // Final validation check before saving
        let errors = [];

        // HSC Percentage
        if (frm.doc.hsc_percentage) {
            if (frm.doc.hsc_percentage < 35) {
                errors.push(__('HSC percentage should be above 35 %'));
            } else if (frm.doc.hsc_percentage > 100) {
                errors.push(__('HSC percentage cannot be more than 100%'));
            }
        }

        // UG CGPA
        if (frm.doc.ug_degree_details) {
            frm.doc.ug_degree_details.forEach(row => {
                if (row.ug_cgpa && (row.ug_cgpa < 4 || row.ug_cgpa > 10)) {
                    errors.push(__('UG CGPA for degree {0} should be between 4 and 10', [row.degree || '']));
                }
            });
        }

        // PG CGPA
        if (frm.doc.pg_degree_details) {
            frm.doc.pg_degree_details.forEach(row => {
                if (row.pg_cgpa && (row.pg_cgpa < 4 || row.pg_cgpa > 10)) {
                    errors.push(__('PG CGPA for degree {0} should be between 4 and 10', [row.degree || '']));
                }
            });
        }

        if (errors.length > 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: errors.join('<br>')
            });
            frappe.validated = false;
        }
    },

    hsc_percentage: function (frm) {
        if (frm.doc.hsc_percentage) {
            if (frm.doc.hsc_percentage < 35) {
                frappe.show_alert({
                    message: __('Your percentage should be above 35 %'),
                    indicator: 'orange'
                });
                frm.set_value('hsc_percentage', null);
            } else if (frm.doc.hsc_percentage > 100) {
                frappe.show_alert({
                    message: __('Percentage cannot be more than 100%'),
                    indicator: 'orange'
                });
                frm.set_value('hsc_percentage', null);
            }
        }
    }
});

// Field level triggers for immediate feedback in child tables
frappe.ui.form.on('UG Degree Detail', {
    ug_cgpa: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.ug_cgpa && (row.ug_cgpa < 4 || row.ug_cgpa > 10)) {
            frappe.show_alert({
                message: __('CGPA should be between 4 and 10'),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'ug_cgpa', null);
        }
    }
});

frappe.ui.form.on('PG Degree Details', {
    pg_cgpa: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.pg_cgpa && (row.pg_cgpa < 4 || row.pg_cgpa > 10)) {
            frappe.show_alert({
                message: __('CGPA should be between 4 and 10'),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'pg_cgpa', null);
        }
    }
});
