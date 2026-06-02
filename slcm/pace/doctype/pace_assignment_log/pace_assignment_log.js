// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PACE Assignment Log", {
	refresh(frm) {
        setTimeout(() => {

            // Hide Assignments
            frm.page.wrapper.find('.form-assignments').hide();

            // Hide Tags
            frm.page.wrapper.find('.form-tags').hide();

            // Hide Shared
            frm.page.wrapper.find('.form-shared').hide();

            frm.page.wrapper.find('.form-attachments').hide();

        }, 200);
	},
});
