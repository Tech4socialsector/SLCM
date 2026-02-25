// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Admission Result", {
    applicant_id(frm) {
        if (frm.doc.applicant_id) {
            frappe.db.get_doc("Applicant", frm.doc.applicant_id).then(doc => {
                frm.set_value("applicant_name", doc.candidate_name);
                frm.set_value("campus", doc.campus);
                frm.set_value("program", doc.program);
                frm.set_value("program_level", doc.program_level);
                frm.set_value("reservation_category", doc.reservation_category);
                frm.set_value("email", doc.email);
                frm.set_value("admission_cycle", doc.admission_cycle);
                frm.set_value("hsc_percentage", doc.hsc_percentage);
            });
        }
    }
});
