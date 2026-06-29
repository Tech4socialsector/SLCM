frappe.ui.form.on('Eligibility Rule', {

    refresh: function (frm) {
        apply_qualification_level_logic(frm);
        apply_rule_type_logic(frm);
        apply_unit_type_logic(frm);
    },

    qualification_level: function (frm) {

        if (frm.doc.docstatus === 1) return;  // 🚀 STOP if submitted

        frm.set_value('rule_type', '');
        frm.set_value('hsc_group', '');
        frm.set_value('unit_type', '');
        frm.set_value('required_cgpa', '');
        frm.set_value('required_percentage', '');

        apply_qualification_level_logic(frm);
    },

    rule_type: function (frm) {

        if (frm.doc.docstatus === 1) return;  // 🚀 STOP if submitted

        frm.set_value('hsc_group', '');
        frm.set_value('unit_type', '');
        frm.set_value('required_cgpa', '');
        frm.set_value('required_percentage', '');

        apply_rule_type_logic(frm);
    },

    unit_type: function (frm) {

        if (frm.doc.docstatus === 1) return;  // 🚀 STOP if submitted

        apply_unit_type_logic(frm);
    },

    required_cgpa: function (frm) {
        if (frm.doc.required_cgpa && (frm.doc.required_cgpa < 4 || frm.doc.required_cgpa > 10)) {
            frappe.show_alert({
                message: __('CGPA should be between 4 and 10'),
                indicator: 'orange'
            });
            frm.set_value('required_cgpa', null);
        }
    },

    required_percentage: function (frm) {
        if (frm.doc.required_percentage && (frm.doc.required_percentage < 35 || frm.doc.required_percentage > 100)) {
            frappe.show_alert({
                message: __('Percentage should be between 35 and 100'),
                indicator: 'orange'
            });
            frm.set_value('required_percentage', null);
        }
    }
});

function apply_qualification_level_logic(frm) {

    let qualification_level = frm.doc.qualification_level;

    if (qualification_level === 'XII') {

        frm.set_df_property('rule_type', 'options', ['', 'HSC Group', 'Percentage']);
        frm.set_df_property('unit_type', 'options', ['', 'Percentage']);

        frm.set_df_property('allowed_degrees', 'hidden', 1);
        frm.set_df_property('rule_type', 'hidden', 0);

    } else if (qualification_level === 'Undergraduate' || qualification_level === 'Postgraduate') {

        frm.set_df_property('rule_type', 'options', ['', 'CGPA']);

        if (frm.doc.docstatus === 0) {
            frm.set_value('rule_type', 'CGPA');
            frm.set_value('unit_type', 'CGPA');
        }

        frm.set_df_property('rule_type', 'hidden', 0);
        frm.set_df_property('hsc_group', 'hidden', 1);

        frm.set_df_property('unit_type', 'options', ['', 'CGPA']);

        frm.set_df_property('required_cgpa', 'hidden', 0);
        frm.set_df_property('required_percentage', 'hidden', 1);

        frm.set_df_property('allowed_degrees', 'hidden', 0);

    } else {

        frm.set_df_property('rule_type', 'hidden', 0);
        frm.set_df_property('hsc_group', 'hidden', 1);
        frm.set_df_property('required_cgpa', 'hidden', 1);
        frm.set_df_property('required_percentage', 'hidden', 1);
        frm.set_df_property('allowed_degrees', 'hidden', 1);
    }
}

function apply_rule_type_logic(frm) {

    let qualification_level = frm.doc.qualification_level;
    let rule_type = frm.doc.rule_type;

    if (qualification_level === 'XII') {

        if (rule_type === 'HSC Group') {

            frm.set_df_property('hsc_group', 'hidden', 0);
            frm.set_df_property('unit_type', 'options', ['', 'Percentage']);
            frm.set_df_property('allowed_degrees', 'hidden', 1);

        } else if (rule_type === 'Percentage') {

            frm.set_df_property('hsc_group', 'hidden', 1);

            if (frm.doc.docstatus === 0) {
                frm.set_value('unit_type', 'Percentage');
            }

            frm.set_df_property('unit_type', 'options', ['', 'Percentage']);

            frm.set_df_property('required_percentage', 'hidden', 0);
            frm.set_df_property('required_cgpa', 'hidden', 1);

            frm.set_df_property('allowed_degrees', 'hidden', 1);
        }
    }
}

function apply_unit_type_logic(frm) {

    let qualification_level = frm.doc.qualification_level;
    let unit_type = frm.doc.unit_type;

    if (qualification_level === 'XII') {

        if (unit_type === 'Percentage') {

            frm.set_df_property('required_percentage', 'hidden', 0);
            frm.set_df_property('required_cgpa', 'hidden', 1);
        } else {

            frm.set_df_property('required_cgpa', 'hidden', 1);
            frm.set_df_property('required_percentage', 'hidden', 1);
        }

    } else if (qualification_level === 'Undergraduate' || qualification_level === 'Postgraduate') {

        frm.set_df_property('required_cgpa', 'hidden', 0);
        frm.set_df_property('required_percentage', 'hidden', 1);
    }
}
frappe.ui.form.on('Eligibility Rule', {

    validate: function (frm) {
        validate_values(frm);
    }
});

function validate_values(frm) {
    if (frm.doc.required_cgpa && (frm.doc.required_cgpa < 4 || frm.doc.required_cgpa > 10)) {
        frappe.msgprint({
            title: __('Validation Error'),
            message: __('Required CGPA should be between 4 and 10'),
            indicator: 'red'
        });
        frappe.validated = false;
    }

    if (frm.doc.required_percentage && (frm.doc.required_percentage < 35 || frm.doc.required_percentage > 100)) {
        frappe.msgprint({
            title: __('Validation Error'),
            message: __('Required Percentage should be between 35 and 100'),
            indicator: 'red'
        });
        frappe.validated = false;
    }
}
