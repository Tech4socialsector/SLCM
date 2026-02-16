frappe.ui.form.on('Eligibility Rule', {

    refresh: function(frm) {
        apply_qualification_level_logic(frm);
        apply_rule_type_logic(frm);
        apply_unit_type_logic(frm);
    },

    qualification_level: function(frm) {

        if (frm.doc.docstatus === 1) return;  // 🚀 STOP if submitted

        frm.set_value('rule_type', '');
        frm.set_value('subject', '');
        frm.set_value('unit_type', '');
        frm.set_value('required_cgpa', '');
        frm.set_value('required_percentage', '');
        frm.set_value('required_score', '');

        apply_qualification_level_logic(frm);
    },

    rule_type: function(frm) {

        if (frm.doc.docstatus === 1) return;  // 🚀 STOP if submitted

        frm.set_value('subject', '');
        frm.set_value('unit_type', '');
        frm.set_value('required_cgpa', '');
        frm.set_value('required_percentage', '');
        frm.set_value('required_score', '');

        apply_rule_type_logic(frm);
    },

    unit_type: function(frm) {

        if (frm.doc.docstatus === 1) return;  // 🚀 STOP if submitted

        apply_unit_type_logic(frm);
    }
});

function apply_qualification_level_logic(frm) {

    let qualification_level = frm.doc.qualification_level;

    if (qualification_level === 'XII') {

        frm.set_df_property('rule_type', 'options', ['', 'Subject', 'Total Score', 'Percentage']);
        frm.set_df_property('unit_type', 'options', ['', 'Percentage', 'Score']);

        frm.set_df_property('allowed_degrees', 'hidden', 1);
        frm.set_df_property('rule_type', 'hidden', 0);

    } else if (qualification_level === 'UG' || qualification_level === 'PG') {

        frm.set_df_property('rule_type', 'options', ['', 'CGPA']);

        if (frm.doc.docstatus === 0) {
            frm.set_value('rule_type', 'CGPA');
            frm.set_value('unit_type', 'CGPA');
        }

        frm.set_df_property('rule_type', 'hidden', 0);
        frm.set_df_property('subject', 'hidden', 1);

        frm.set_df_property('unit_type', 'options', ['', 'CGPA']);

        frm.set_df_property('required_cgpa', 'hidden', 0);
        frm.set_df_property('required_percentage', 'hidden', 1);
        frm.set_df_property('required_score', 'hidden', 1);

        frm.set_df_property('allowed_degrees', 'hidden', 0);

    } else {

        frm.set_df_property('rule_type', 'hidden', 0);
        frm.set_df_property('subject', 'hidden', 1);
        frm.set_df_property('required_cgpa', 'hidden', 1);
        frm.set_df_property('required_percentage', 'hidden', 1);
        frm.set_df_property('required_score', 'hidden', 1);
        frm.set_df_property('allowed_degrees', 'hidden', 1);
    }
}

function apply_rule_type_logic(frm) {

    let qualification_level = frm.doc.qualification_level;
    let rule_type = frm.doc.rule_type;

    if (qualification_level === 'XII') {

        if (rule_type === 'Subject') {

            frm.set_df_property('subject', 'hidden', 0);
            frm.set_df_property('unit_type', 'options', ['', 'Percentage', 'Score']);
            frm.set_df_property('allowed_degrees', 'hidden', 1);

        } else if (rule_type === 'Total Score') {

            frm.set_df_property('subject', 'hidden', 1);
            frm.set_df_property('unit_type', 'options', ['', 'Score', 'Percentage']);
            frm.set_df_property('allowed_degrees', 'hidden', 1);

        } else if (rule_type === 'Percentage') {

            frm.set_df_property('subject', 'hidden', 1);

            if (frm.doc.docstatus === 0) {
                frm.set_value('unit_type', 'Percentage');
            }

            frm.set_df_property('unit_type', 'options', ['', 'Percentage']);

            frm.set_df_property('required_percentage', 'hidden', 0);
            frm.set_df_property('required_cgpa', 'hidden', 1);
            frm.set_df_property('required_score', 'hidden', 1);

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
            frm.set_df_property('required_score', 'hidden', 1);

        } else if (unit_type === 'Score') {

            frm.set_df_property('required_score', 'hidden', 0);
            frm.set_df_property('required_cgpa', 'hidden', 1);
            frm.set_df_property('required_percentage', 'hidden', 1);

        } else {

            frm.set_df_property('required_cgpa', 'hidden', 1);
            frm.set_df_property('required_percentage', 'hidden', 1);
            frm.set_df_property('required_score', 'hidden', 1);
        }

    } else if (qualification_level === 'UG' || qualification_level === 'PG') {

        frm.set_df_property('required_cgpa', 'hidden', 0);
        frm.set_df_property('required_percentage', 'hidden', 1);
        frm.set_df_property('required_score', 'hidden', 1);
    }
}
