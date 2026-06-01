frappe.ui.form.on("Faculty Announcement", {
	refresh(frm) {
		frm.trigger("toggle_target_fields");
	},

	target_audience(frm) {
		frm.trigger("toggle_target_fields");
	},

	toggle_target_fields(frm) {
		const audience = frm.doc.target_audience;
		frm.set_df_property("target_departments", "hidden", audience !== "Specific Department(s)");
		frm.set_df_property("target_faculties",   "hidden", audience !== "Specific Faculty");
	},

	validate(frm) {
		if (frm.doc.expiry_date && frm.doc.publish_date && frm.doc.expiry_date < frm.doc.publish_date) {
			frappe.throw(__("Expiry Date cannot be before Publish Date."));
		}
	},
});
