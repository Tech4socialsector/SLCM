frappe.ui.form.on("Fine Imposition", {
	refresh(frm) {
		if (frm.doc.status === "Draft" && !frm.is_new() && !frm.is_dirty()) {
			frm.add_custom_button(__("Apply Fine"), () => {
				frappe.confirm(
					__("This will scan outstanding Fee Demands with a Due Date between "
						+ "<b>{0}</b> and <b>{1}</b> and create a Fine demand for each match. "
						+ "This action cannot be undone. Proceed?",
						[frm.doc.from_date, frm.doc.to_date]),
					() => {
						frappe.show_alert({ message: __("Applying fine..."), indicator: "blue" });
						frm.call("apply_fine").then((r) => {
							frm.reload_doc();
							if (r.message) {
								frappe.msgprint(
									__("Applied fine to {0} demand(s) totalling {1}.", [
										r.message.total_demands_affected,
										format_currency(r.message.total_fine_amount),
									])
								);
							}
						});
					}
				);
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Applied") {
			frm.set_intro(
				__("This Fine Imposition has already been applied on {0} and cannot be re-applied.",
					[frappe.datetime.str_to_user(frm.doc.applied_on)]),
				"green"
			);
		}
	},
});
