// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

/**
 * Scholarship Application Form Script
 */

// ─── Form View Events ────────────────────────────────────────────────────────
frappe.ui.form.on("Scholarship Application", {
    setup(frm) {
        frm.add_fetch("applicant_id", "candidate_name", "applicant_name");
    },
    refresh(frm) {
        frm.trigger("scholarship_scheme_ui");
        
        if (!frm.is_new() && (frappe.user_roles.includes("Scholarship Admin") || frappe.user_roles.includes("System Manager"))) {
            if (frm.doc.status === "Submitted") {
                frm.add_custom_button(__("Approve"), () => {
                    frappe.confirm(__("Are you sure you want to approve this scholarship application?"), () => {
                        frm.set_value("status", "Approved");
                        frm.set_value("approval_date", frappe.datetime.now_datetime());
                        frm.save().then(() => {
                            frappe.msgprint(__("Scholarship Application Approved"));
                        });
                    });
                }).addClass("btn-primary");

                frm.add_custom_button(__("Reject"), () => {
                    frappe.prompt([
                        {
                            label: __("Rejection Reason"),
                            fieldname: "reason",
                            fieldtype: "Small Text",
                            reqd: 1
                        }
                    ], (values) => {
                        frm.set_value("status", "Rejected");
                        frm.set_value("rejection_reason", values.reason);
                        frm.save().then(() => {
                            frappe.msgprint(__("Scholarship Application Rejected"));
                        });
                    }, __("Reject Scholarship Application"), __("Submit"));
                }).addClass("btn-danger");
            } else if (frm.doc.status === "Approved") {
                frm.add_custom_button(__("Revoke"), () => {
                    frappe.confirm(__("Are you sure you want to revoke this approved scholarship?"), () => {
                        frm.set_value("status", "Revoked");
                        frm.save().then(() => {
                            frappe.msgprint(__("Scholarship Application Revoked"));
                        });
                    });
                }).addClass("btn-danger");
            }
        }
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
    campus(frm) {
        frm.trigger("fetch_original_fee");
    },
    admission_cycle(frm) {
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
                    if (r.message !== undefined) {
                        frm.set_value("original_fee_amount", r.message);
                        frm.trigger("calculate_benefit");
                    }
                }
            });
        }
    },
    scholarship_scheme(frm) {
        frm.trigger("scholarship_scheme_ui");
        frm.trigger("calculate_benefit");
    },
    scholarship_scheme_ui(frm) {
        if (frm.doc.scholarship_scheme) {
            frm.toggle_display("family_income", true);
            frm.toggle_reqd("family_income", true);
            frm.toggle_display("income_certificate", true);
            frm.toggle_reqd("income_certificate", true);
        }
    },
    original_fee_amount(frm) {
        frm.trigger("calculate_benefit");
    },
    calculate_benefit(frm) {
        if (frm.doc.scholarship_scheme && frm.doc.original_fee_amount) {
            // We must pass the doc so server has all context (cycle, campus, program)
            frappe.call({
                method: "slcm.admission.doctype.scholarship_application.scholarship_application.get_calculated_benefit",
                args: {
                    doc: frm.doc
                },
                callback: function(res) {
                    if (res.message) {
                        frm.set_value("calculated_benefit", res.message.benefit);
                        frm.set_value("final_fee_amount", res.message.final_fee);
                        frm.refresh_fields(["calculated_benefit", "final_fee_amount"]);
                    }
                }
            });
        }
    }
});
