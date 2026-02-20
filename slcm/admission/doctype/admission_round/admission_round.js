// Copyright (c) 2026, TFSS and contributors
// Admission Round Client Script

frappe.ui.form.on("Admission Round", {

    refresh(frm) {
        // Filter admission_cycle to active cycles
        frm.set_query("admission_cycle", function () {
            return { filters: { status: ["in", ["Active", "Draft"]], docstatus: ["!=", 2] } };
        });
        set_date_readonly(frm);
    },

    onload(frm) {
        set_date_readonly(frm);
    },

    admission_cycle(frm) {
        if (!frm.doc.admission_cycle) return;
        // Show cycle dates as helper text
        frappe.db.get_value(
            "Admission Cycle",
            frm.doc.admission_cycle,
            ["start_date", "end_date"],
            function (r) {
                if (r && r.start_date && r.end_date) {
                    frm.set_intro(
                        __("Admission Cycle: {0} to {1}", [r.start_date, r.end_date]),
                        "blue"
                    );
                }
            }
        );
    }
});

function set_date_readonly(frm) {
    if (frm.doc.stage_locked) {
        ["start_date", "end_date", "fee_payment_deadline", "doc_verification_deadline"].forEach(f => {
            frm.set_df_property(f, "read_only", 1);
        });
    }
}
