frappe.ui.form.on("PACE Receipt", {
	refresh: function(frm) {
		if (frm.doc.name) {
			frm.add_custom_button(__('Download Receipt'), function() {
				frappe.call({
					method: "slcm.pace.doctype.pace_receipt.pace_receipt.get_receipt_template_api",
					args: {
						receipt_name: frm.doc.name
					},
					callback: function(r) {
						let template = r.message || "PACE Payment Reciept";
						let url = `/api/method/frappe.utils.print_format.download_pdf?doctype=PACE Receipt&name=${frm.doc.name}&format=${template}&no_letterhead=1`;
						window.open(url, "_blank");
					}
				});
			}, __("Actions"));
		}
	}
});
