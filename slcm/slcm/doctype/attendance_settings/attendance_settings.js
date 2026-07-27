// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance Settings", {
	refresh(frm) {
		frm.set_query("authority", "level_one_authority", () => {
			return {
				query: "slcm.slcm.doctype.attendance_settings.attendance_settings.get_users_by_role",
				filters: { role: "AAD" }
			};
		});

		frm.set_query("authority", "level_two_authority", () => {
			return {
				query: "slcm.slcm.doctype.attendance_settings.attendance_settings.get_users_by_role",
				filters: { role: "Programme Chair" }
			};
		});

		toggle_condonation_list_button(frm);
	},

	on_tab_change(frm) {
		toggle_condonation_list_button(frm);
	},
});

function toggle_condonation_list_button(frm) {
	const label = __("Go to Attendance Condonation List");
	const active_tab_fieldname = frm.get_active_tab()?.df?.fieldname;

	if (active_tab_fieldname === "tab_condonation") {
		if (!frm.custom_buttons[label]) {
			frm.add_custom_button(label, () => {
				frappe.set_route("List", "Student Attendance Condonation");
			});
		}
	} else {
		frm.remove_custom_button(label);
	}
}
