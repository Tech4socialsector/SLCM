// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Access Result Settings", {
	refresh(frm) {
		// Ensure evaluator_doctype is initialised for rows loaded from DB
		// (existing rows saved before this field existed will have it empty)
		(frm.doc.evaluators || []).forEach(function (row) {
			if (!row.evaluator_doctype) {
				row.evaluator_doctype = row.evaluator_type === "Class Faculty" ? "Faculty" : "";
			}
		});
	},
});

frappe.ui.form.on("Result Course Evaluator", {
	// When the type changes, update the hidden doctype field so the Dynamic
	// Link field switches between Faculty-linked mode and free-text mode.
	evaluator_type(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		var doctype = row.evaluator_type === "Class Faculty" ? "Faculty" : "";
		frappe.model.set_value(cdt, cdn, "evaluator_doctype", doctype);
		frappe.model.set_value(cdt, cdn, "evaluator_name", "");
		frappe.model.set_value(cdt, cdn, "evaluator_email", "");
	},

	// Auto-fill email from Faculty when a Class Faculty name is selected.
	evaluator_name(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.evaluator_type === "Class Faculty" && row.evaluator_name) {
			frappe.db.get_value("Faculty", row.evaluator_name, "email", function (data) {
				if (data && data.email) {
					frappe.model.set_value(cdt, cdn, "evaluator_email", data.email);
				}
			});
		}
	},
});
