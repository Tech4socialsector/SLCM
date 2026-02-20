// Copyright (c) 2026, TFSS and contributors
// Admission Cycle Client Script

frappe.ui.form.on("Admission Cycle", {

    refresh(frm) {
        // Filter admission_year to active ones
        frm.set_query("admission_year", function () {
            return { filters: { is_active: 1 } };
        });

        // Show/hide stage date sections based on flags
        toggle_stage_dates(frm);
    },

    enable_interview(frm) {
        toggle_stage_dates(frm);
    },

    enable_document_verification(frm) {
        toggle_stage_dates(frm);
    }
});

function toggle_stage_dates(frm) {
    // Interview date section collapses automatically via depends_on
    // This is just an extra refresh guard
    frm.refresh_field("interview_start_date");
    frm.refresh_field("interview_end_date");
    frm.refresh_field("doc_verification_start_date");
    frm.refresh_field("doc_verification_end_date");

    if (!frm.doc.enable_interview) {
        frm.set_value("interview_start_date", null);
        frm.set_value("interview_end_date", null);
    }
    if (!frm.doc.enable_document_verification) {
        frm.set_value("doc_verification_start_date", null);
        frm.set_value("doc_verification_end_date", null);
    }
}
