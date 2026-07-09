frappe.ui.form.on('Eligibility Rule Mapping', {
    onload: function (frm) {
        frm.set_query("admission_cycle", function () {
            return {
                filters: {
                    "status": "Active"
                }
            };
        });
    },

    priority: function (frm) {
        if (frm.doc.priority && frm.doc.priority > 100) {
            frappe.show_alert({
                message: __("Priority value cannot be greater than 100."),
                indicator: "orange"
            });
            frm.set_value('priority', '');
        }
    },

    validate: function (frm) {
        if (frm.doc.priority && frm.doc.priority > 100) {
            frappe.msgprint({
                title: __("Invalid Priority"),
                message: __("Priority value must be 100 or less."),
                indicator: "red"
            });
            frappe.validated = false;
        }

        // Final check for child table
        if (frm.doc.reservation_category && frm.doc.rule) {
            // We skip async check in validate for now since field triggers handle most cases.
            // However, if needed, we could fetch unit_type here.
        }
    }
});

frappe.ui.form.on('Rule Mapping Category', {
    minimum_percentage_hsc: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.minimum_percentage_hsc && (row.minimum_percentage_hsc < 35 || row.minimum_percentage_hsc > 100)) {
            frappe.show_alert({
                message: __('HSC Percentage should be between 35 and 100'),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'minimum_percentage_hsc', null);
        }
    },
    minimum_percentage_sslc: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.minimum_percentage_sslc && (row.minimum_percentage_sslc < 35 || row.minimum_percentage_sslc > 100)) {
            frappe.show_alert({
                message: __('SSLC Percentage should be between 35 and 100'),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'minimum_percentage_sslc', null);
        }
    },
    minimum_cgpa_ug: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.minimum_cgpa_ug && (row.minimum_cgpa_ug < 4 || row.minimum_cgpa_ug > 10)) {
            frappe.show_alert({
                message: __('UG CGPA should be between 4 and 10'),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'minimum_cgpa_ug', null);
        }
    },
    minimum_cgpa_pg: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.minimum_cgpa_pg && (row.minimum_cgpa_pg < 4 || row.minimum_cgpa_pg > 10)) {
            frappe.show_alert({
                message: __('PG CGPA should be between 4 and 10'),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'minimum_cgpa_pg', null);
        }
    }
});
