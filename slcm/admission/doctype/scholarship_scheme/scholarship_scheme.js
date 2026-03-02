// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Scheme", {
    refresh(frm) {
        frm.trigger("scheme_type");
        frm.trigger("coverage_type");
    },
    scheme_type(frm) {
        const type = frm.doc.scheme_type;

        // Fields to manage
        const income_fields = ["min_income", "max_income", "income_certificate_required"];
        const merit_fields = ["min_merit_score"];

        // Reset defaults
        [...income_fields, ...merit_fields].forEach(f => {
            frm.set_df_property(f, "hidden", 0);
            frm.set_df_property(f, "reqd", 0);
        });
        frm.set_df_property("coverage_type", "read_only", 0);
        frm.set_df_property("approval_authority", "read_only", 0);

        if (type === "Need") {
            income_fields.forEach(f => frm.set_df_property(f, "reqd", 1));
            merit_fields.forEach(f => frm.set_df_property(f, "hidden", 1));

            if (frm.is_new() && !frm.doc.income_certificate_required) {
                frm.set_value("income_certificate_required", 1);
            }
        } else if (type === "Merit") {
            merit_fields.forEach(f => frm.set_df_property(f, "reqd", 1));
            income_fields.forEach(f => frm.set_df_property(f, "hidden", 1));
        } else if (type === "Government") {
            // Government schemes are often fixed and have strict authority
            frm.set_df_property("coverage_type", "read_only", 1);
            frm.set_df_property("approval_authority", "read_only", 1);

            if (frm.is_new()) {
                if (!frm.doc.coverage_type) frm.set_value("coverage_type", "Fixed");
                if (!frm.doc.approval_authority) frm.set_value("approval_authority", "Finance Head");
            }
        }
    },
    coverage_type(frm) {
        if (frm.doc.coverage_type === "Percentage") {
            frm.set_df_property("coverage_value", "label", __("Coverage Percentage (%)"));
        } else if (frm.doc.coverage_type === "Fixed") {
            frm.set_df_property("coverage_value", "label", __("Fixed Amount"));
        }
    }
});
