frappe.ui.form.on('Eligibility Rule Mapping', {
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
    minimum_percentage: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        // rule is now a Table MultiSelect, so frm.doc.rule is a list of child docs
        let selected_rules = (frm.doc.rule || []).map(r => r.rule).filter(Boolean);

        if (row.minimum_percentage && selected_rules.length > 0) {
            // Check the unit_type of the first rule for validation
            frappe.db.get_value('Eligibility Rule', selected_rules[0], 'unit_type', (r) => {
                if (!r) return;

                let unit_type = r.unit_type;
                if (unit_type === 'CGPA') {
                    if (row.minimum_percentage < 4 || row.minimum_percentage > 10) {
                        frappe.show_alert({
                            message: __('CGPA should be between 4 and 10'),
                            indicator: 'orange'
                        });
                        frappe.model.set_value(cdt, cdn, 'minimum_percentage', null);
                    }
                } else if (unit_type === 'Percentage') {
                    if (row.minimum_percentage < 35 || row.minimum_percentage > 100) {
                        frappe.show_alert({
                            message: __('Percentage should be between 35 and 100'),
                            indicator: 'orange'
                        });
                        frappe.model.set_value(cdt, cdn, 'minimum_percentage', null);
                    }
                }
            });
        }
    }
});
