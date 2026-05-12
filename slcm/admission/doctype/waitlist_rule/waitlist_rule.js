frappe.ui.form.on("Waitlist Rule", {
	setup(frm) {
		frm.set_query("admission_cycle", () => {
			return {
				filters: {
					"status": "Active"
				}
			};
		});
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.status === "Active") {
			frm.add_custom_button("Run Promotion", () => {
				frappe.call({
					method: "slcm.admission.doctype.waitlist_rule.waitlist_promotion.run_manual_waitlist",
					args: {
						rule: frm.doc.name
					},
					callback: () => {
						frm.reload_doc();
					}
				});
			});
		}
	}
});
