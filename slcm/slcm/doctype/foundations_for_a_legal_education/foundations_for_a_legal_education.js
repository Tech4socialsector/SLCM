// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

<<<<<<< HEAD
frappe.ui.form.on("Foundations for a Legal Education", {
    refresh(frm) {
        // Trigger the check on form load
        frm.trigger('candidate_dob');
    },
    candidate_dob(frm) {
        let is_visible = false;

        if (frm.doc.candidate_dob) {
            const dob = new Date(frm.doc.candidate_dob);
            const today = new Date();
            let age = today.getFullYear() - dob.getFullYear();
            const monthDiff = today.getMonth() - dob.getMonth();

            // Adjust age if birthday hasn't occurred yet this year
            if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
                age--;
            }

            // If under 18, show declaration section
            if (age < 18) {
                is_visible = true;
            }
        }

        // Toggle visibility: show if under 18, hide otherwise
        frm.toggle_display(['section_break_declaration', 'declaration_html', 'declaration_consent'], is_visible);
    }
});
=======
// frappe.ui.form.on("Foundations for a Legal Education", {
// 	refresh(frm) {

// 	},
// });
>>>>>>> 16c31c6bc49ac85d2c17031080df954fc7af2ea3
