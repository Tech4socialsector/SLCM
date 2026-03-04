frappe.ui.form.on('Exam Schema', {
    refresh(frm) {
        toggle_assessment_tables(frm);
        calculate_totals(frm);
    },
    total_marks(frm) {
        calculate_totals(frm);
    }
});

function toggle_assessment_tables(frm) {
    let components = (frm.doc.weightages || []).map(row => (row.exam_component || "").toLowerCase());

    // Internal
    let has_internal = components.some(c => c.includes('internal'));
    frm.toggle_display(['section_break_zfjn', 'internal_assessment_composition', 'total_effective_internal_marks'], has_internal);

    // External
    let has_external = components.some(c => c.includes('external'));
    frm.toggle_display(['section_break_external', 'external_assessment_composition', 'total_effective_external_marks'], has_external);

    // Makeup
    let has_makeup = components.some(c => c.includes('makeup') || c.includes('make up'));
    frm.toggle_display(['section_break_makeup', 'makeup_assessment_composition', 'total_effective_makeup_marks'], has_makeup);

    // Re-Exam
    let has_reexam = components.some(c => c.includes('re-exam') || c.includes('re exam'));
    frm.toggle_display(['section_break_re_exam', 're_exam_assessment_composition', 'total_effective_re_exam_marks'], has_reexam);
}

function calculate_totals(frm) {
    let total_internal = 0;
    let total_external = 0;
    let total_makeup = 0;
    let total_re_exam = 0;

    // internal
    (frm.doc.internal_assessment_composition || []).forEach(row => {
        let eff = calculate_row_effective(frm, row, 'internal_assessment_composition');
        total_internal += eff;
    });

    // external
    (frm.doc.external_assessment_composition || []).forEach(row => {
        let eff = calculate_row_effective(frm, row, 'external_assessment_composition');
        total_external += eff;
    });

    // makeup
    (frm.doc.makeup_assessment_composition || []).forEach(row => {
        let eff = calculate_row_effective(frm, row, 'makeup_assessment_composition');
        total_makeup += eff;
    });

    // re-exam
    (frm.doc.re_exam_assessment_composition || []).forEach(row => {
        let eff = calculate_row_effective(frm, row, 're_exam_assessment_composition');
        total_re_exam += eff;
    });

    frm.set_value('total_effective_internal_marks', total_internal);
    frm.set_value('total_effective_external_marks', total_external);
    frm.set_value('total_effective_makeup_marks', total_makeup);
    frm.set_value('total_effective_re_exam_marks', total_re_exam);
}

function calculate_row_effective(frm, cdt, cdn) {
    let row = typeof cdt === 'string' ? frappe.get_doc(cdt, cdn) : cdt;
    let weightage = row.weightage || 0;

    // As per user requirement in previous session: effective marks = maximum marks.
    // Wait, the user said "effective mark should be the maximum mark but if i give 89 then it should be effective mark right".
    let eff = row.maximum_marks || 0;
    frappe.model.set_value(row.doctype, row.name, 'effective_maximum_marks', eff);

    // Substitution Logic
    if (row.substitution_type) {
        let sub_weight = row.substitute_weightage || 0;
        let sub_eff = eff * (sub_weight / 100.0);
        let sub_assess_eff = sub_eff; // Normally same for assessment level

        frappe.model.set_value(row.doctype, row.name, 'substitute_effective_marks', sub_eff);
        frappe.model.set_value(row.doctype, row.name, 'substitute_assessment_effective_marks', sub_assess_eff);
    } else {
        frappe.model.set_value(row.doctype, row.name, 'substitute_effective_marks', 0);
        frappe.model.set_value(row.doctype, row.name, 'substitute_assessment_effective_marks', 0);
    }

    return eff;
}

frappe.ui.form.on('Exam Schema Weightage', {
    exam_component(frm, cdt, cdn) {
        toggle_assessment_tables(frm);
    },
    weightages_remove(frm) {
        toggle_assessment_tables(frm);
    }
});

frappe.ui.form.on('Exam Schema Assessment', {
    maximum_marks(frm, cdt, cdn) {
        calculate_totals(frm);
    },
    weightage(frm, cdt, cdn) {
        calculate_totals(frm);
    },
    substitute_weightage(frm, cdt, cdn) {
        calculate_totals(frm);
    },
    substitution_type(frm, cdt, cdn) {
        calculate_totals(frm);
    },
    internal_assessment_composition_remove(frm) {
        calculate_totals(frm);
    },
    external_assessment_composition_remove(frm) {
        calculate_totals(frm);
    },
    makeup_assessment_composition_remove(frm) {
        calculate_totals(frm);
    },
    re_exam_assessment_composition_remove(frm) {
        calculate_totals(frm);
    }
});
