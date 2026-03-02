// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Application", {
    refresh(frm) {
        frm.trigger("scholarship_scheme");
    },
    scholarship_scheme(frm) {
        if (frm.doc.scholarship_scheme) {
            frappe.db.get_value("Scholarship Scheme", frm.doc.scholarship_scheme,
                ["scheme_type", "income_certificate_required"], (r) => {
                    if (r) {
                        const is_need = r.scheme_type === "Need" || r.income_certificate_required;
                        frm.toggle_display("family_income", is_need);
                        frm.toggle_reqd("family_income", is_need);
                        frm.toggle_display("income_certificate", is_need);
                        frm.toggle_reqd("income_certificate", is_need);
                    }
                });
        }
    }
});
