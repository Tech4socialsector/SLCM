// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scholarship Application", {
    setup(frm) {
        frm.add_fetch("applicant_id", "candidate_name", "applicant_name");
    },
    refresh(frm) {
        frm.trigger("scholarship_scheme");
    },
    applicant_id(frm) {
        if (frm.doc.applicant_id) {
            frappe.db.get_value("Applicant", frm.doc.applicant_id, "candidate_name", (r) => {
                if (r && r.candidate_name) {
                    frm.set_value("applicant_name", r.candidate_name);
                }
            });
        }
        frm.trigger("fetch_original_fee");
    },
    program(frm) {
        frm.trigger("fetch_original_fee");
    },
    fetch_original_fee(frm) {
        if (frm.doc.applicant_id && frm.doc.program) {
            frappe.call({
                method: "slcm.admission.doctype.scholarship_application.scholarship_application.get_original_fee_amount",
                args: {
                    applicant_id: frm.doc.applicant_id,
                    program: frm.doc.program,
                    campus: frm.doc.campus,
                    cycle: frm.doc.admission_cycle
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("original_fee_amount", r.message);
                    }
                }
            });
        }
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
