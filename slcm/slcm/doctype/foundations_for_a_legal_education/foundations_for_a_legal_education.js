// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Foundations for a Legal Education", {
    refresh(frm) {
        // Trigger the check on form load
        if (frm.doc.candidate_dob) {
            frm.trigger('candidate_dob');
        } else {
            frm.set_df_property('declaration_consent', 'reqd', 0);
        }
    },
    candidate_dob(frm) {
        let is_mandatory = false;

        if (frm.doc.candidate_dob) {
            const dob = new Date(frm.doc.candidate_dob);
            const today = new Date();
            let age = today.getFullYear() - dob.getFullYear();
            const monthDiff = today.getMonth() - dob.getMonth();

            // Adjust age if birthday hasn't occurred yet this year
            if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
                age--;
            }

            // If under 18, make declaration mandatory
            if (age < 18) {
                is_mandatory = true;
            }
        }

        frm.set_df_property('declaration_consent', 'reqd', is_mandatory ? 1 : 0);
    }
});
