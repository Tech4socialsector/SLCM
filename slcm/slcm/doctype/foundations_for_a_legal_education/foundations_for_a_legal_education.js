// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Foundations for a Legal Education", {
    refresh(frm) {
        // Trigger the check on form load
        if (frm.doc.candidate_dob) {
            frm.trigger('candidate_dob');
        } else {
            // If no DOB, hide by default or handle as needed
            let is_visible = false;
            // Toggle visibility: show if under 18, hide otherwise
            if (frm.toggle_display) {
                frm.toggle_display(['section_break_declaration', 'declaration_html', 'declaration_consent'], is_visible);
            } else {
                // Fallback
                frm.set_df_property('section_break_declaration', 'hidden', is_visible ? 0 : 1);
                frm.set_df_property('declaration_html', 'hidden', is_visible ? 0 : 1);
                frm.set_df_property('declaration_consent', 'hidden', is_visible ? 0 : 1);
            }
        }
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
        if (frm.toggle_display) {
            frm.toggle_display(['section_break_declaration', 'declaration_html', 'declaration_consent'], is_visible);
        } else {
            // Fallback for older frappe versions if toggle_display isn't available on frm
            frm.set_df_property('section_break_declaration', 'hidden', is_visible ? 0 : 1);
            frm.set_df_property('declaration_html', 'hidden', is_visible ? 0 : 1);
            frm.set_df_property('declaration_consent', 'hidden', is_visible ? 0 : 1);
        }
    }
});
