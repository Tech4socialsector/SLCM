// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance Condonation Configuration", {
	refresh(frm) {
		frm.add_custom_button(__("Go to Attendance Condonation List"), function () {
			frappe.set_route("List", "Student Attendance Condonation");
		});
	},
});
