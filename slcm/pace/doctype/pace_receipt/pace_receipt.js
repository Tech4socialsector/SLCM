frappe.ui.form.on("PACE Receipt", {
	refresh: function(frm) {
		if (frm.doc.name) {
			frm.add_custom_button(__('Download Receipt'), function() {
				frappe.call({
					method: "frappe.client.get_value",
					args: {
						doctype: "PACE Applicant Fee Assignment",
						filters: { name: frm.doc.fee_assignment },
						fieldname: "fee_structure"
					},
					callback: function(r) {
						if (r.message && r.message.fee_structure) {
							frappe.call({
								method: "frappe.client.get_value",
								args: {
									doctype: "PACE Fee Structure",
									filters: { name: r.message.fee_structure },
									fieldname: "payment_reciept_template"
								},
								callback: function(res) {
									let template = res.message ? res.message.payment_reciept_template : "PACE Payment Reciept";
									let url = `/api/method/frappe.utils.print_format.download_pdf?doctype=PACE Receipt&name=${frm.doc.name}&format=${template || "PACE Payment Reciept"}&no_letterhead=1`;
									window.open(url, "_blank");
								}
							});
						} else {
							// Fallback if no fee structure found
							let url = `/api/method/frappe.utils.print_format.download_pdf?doctype=PACE Receipt&name=${frm.doc.name}&format=PACE Payment Reciept&no_letterhead=1`;
							window.open(url, "_blank");
						}
					}
				});
			}, __("Actions"));
		}
	}
});
