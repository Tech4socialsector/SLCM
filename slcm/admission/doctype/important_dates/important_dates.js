// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Important Dates", {
	refresh(frm) {
		const today = new Date(frappe.datetime.get_today());

		if (frm.fields_dict.date && frm.fields_dict.date.datepicker) {
			frm.fields_dict.date.datepicker.update({
				minDate: today,
			});
		}
	},
});
