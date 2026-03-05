// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Scheme", {
    refresh(frm) {
        frm.trigger("scheme_type");
        frm.trigger("apply_on");

        if (!frm.is_new()) {
            frm.add_custom_button(__("Sync Budget"), () => {
                frm.call({
                    doc: frm.doc,
                    method: "sync_budget",
                    callback: function (r) {
                        if (r.message && r.message.status === "Success") {
                            frappe.show_alert({
                                message: __("Budget synced successfully. Utilized: {0}", [format_currency(r.message.utilized_budget)]),
                                indicator: "green"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, __("Actions"));
        }
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
        frm.set_df_property("apply_on", "read_only", 0);
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
            frm.set_df_property("apply_on", "read_only", 1);
            frm.set_df_property("approval_authority", "read_only", 1);

            if (frm.is_new()) {
                if (!frm.doc.apply_on) frm.set_value("apply_on", "Total Fee");
                if (!frm.doc.approval_authority) frm.set_value("approval_authority", "Finance Head");
            }
        }
    },
    apply_on(frm) {
        if (frm.doc.apply_on === "Component-wise") {
            frm.set_value("coverage_type", "Component-wise");
            frm.set_value("coverage_value", 0);
            
            // Explicitly show component fields in JS just in case JSON depends_on is slow
            frm.toggle_display("section_component_coverage", true);
            frm.toggle_display("coverage_rules", true);
            
            // Hide simple coverage fields
            frm.toggle_display("coverage_type", false);
            frm.toggle_display("coverage_value", false);
        } else {
            // Show simple coverage fields
            frm.toggle_display("coverage_type", true);
            frm.toggle_display("coverage_value", true);
            
            // Hide component fields
            frm.toggle_display("section_component_coverage", false);
            frm.toggle_display("coverage_rules", false);
            
            // Reset coverage type if it was component-wise
            if (frm.doc.coverage_type === "Component-wise") {
                frm.set_value("coverage_type", "Percentage");
            }
        }
        frm.trigger("coverage_type");
    },
    coverage_type(frm) {
        if (frm.doc.coverage_type === "Percentage") {
            frm.set_df_property("coverage_value", "label", __("Coverage Percentage (%)"));
        } else if (frm.doc.coverage_type === "Fixed") {
            frm.set_df_property("coverage_value", "label", __("Fixed Amount"));
        }
        frm.trigger("calculate_max_beneficiaries");
    },
    total_budget(frm) {
        frm.trigger("calculate_max_beneficiaries");
    },
    coverage_value(frm) {
        frm.trigger("calculate_max_beneficiaries");
    },
    max_amount(frm) {
        frm.trigger("calculate_max_beneficiaries");
    },
    calculate_max_beneficiaries(frm) {
        if (frm.doc.total_budget && frm.doc.total_budget > 0) {
            let per_student_benefit = 0;

            if (frm.doc.coverage_type === "Fixed" && frm.doc.coverage_value > 0) {
                per_student_benefit = frm.doc.coverage_value;
            } else if (frm.doc.max_amount && frm.doc.max_amount > 0) {
                // For percentage or other types, use max_amount as an estimate if provided
                per_student_benefit = frm.doc.max_amount;
            }

            if (per_student_benefit > 0) {
                const max_bene = Math.floor(frm.doc.total_budget / per_student_benefit);
                if (max_bene > 0 && frm.doc.max_beneficiaries !== max_bene) {
                    frm.set_value("max_beneficiaries", max_bene);
                }
            }
        }
    }
});
