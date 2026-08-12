// Copyright (c) 2025, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Course Offering", {
	refresh(frm) {
		set_faculty_table_section_query(frm);
	},
	batch(frm) {
		set_faculty_table_section_query(frm);
	},
});

function set_faculty_table_section_query(frm) {
	frm.set_query("section", "faculty_table", function () {
		return { filters: { batch: frm.doc.batch } };
	});
}
