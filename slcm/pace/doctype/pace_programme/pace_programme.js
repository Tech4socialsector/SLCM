// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PACE Programme", {
	refresh(frm) {
		setTimeout(() => {

            // Hide Assignments
            frm.page.wrapper.find('.form-assignments').hide();

            // Hide Tags
            frm.page.wrapper.find('.form-tags').hide();

            // Hide Shared
            frm.page.wrapper.find('.form-shared').hide();

        }, 200);
	},
	programme_prefix(frm) {
		frm.trigger("set_title");
	},
	programme_name(frm) {
		frm.trigger("set_title");
	},
	set_title(frm) {
		let prefix = (frm.doc.programme_prefix || "").trim();
		let name = (frm.doc.programme_name || "").trim();
		let title = (prefix + " " + name).trim();
		frm.set_value("title", title);
	}
});
