// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance Condonation Configuration", {
	refresh(frm) {
		frm.add_custom_button(__("Go to Attendance Condonation List"), function () {
			frappe.set_route("List", "Student Attendance Condonation");
		});

		frm.set_query("authority", "level_one_authority", () => {
			return {
				query: "slcm.slcm.doctype.attendance_condonation_configuration.attendance_condonation_configuration.get_users_by_role",
				filters: { role: "AAD" }
			};
		});

		frm.set_query("authority", "level_two_authority", () => {
			return {
				query: "slcm.slcm.doctype.attendance_condonation_configuration.attendance_condonation_configuration.get_users_by_role",
				filters: { role: "Programme Chair" }
			};
		});
	},
});
