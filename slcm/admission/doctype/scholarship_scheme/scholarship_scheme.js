// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Scheme", {
    refresh(frm) {
        frm.trigger("coverage_type");
    },
    coverage_type(frm) {
        if (frm.doc.coverage_type === "Percentage") {
            frm.set_df_property("coverage_value", "label", __("Coverage Percentage (%)"));
        } else if (frm.doc.coverage_type === "Fixed") {
            frm.set_df_property("coverage_value", "label", __("Fixed Amount"));
        }
    }
});
