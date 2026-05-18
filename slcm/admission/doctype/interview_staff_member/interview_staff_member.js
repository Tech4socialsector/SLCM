// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Interview Staff Member", {
    refresh(frm) {
        // Filter user field to show only users with 'Interview Staff Member' role or role profile
        frm.set_query("user", function() {
            return {
                query: "slcm.admission.doctype.interview_staff_member.interview_staff_member.get_user_query"
            };
        });
    }
});
