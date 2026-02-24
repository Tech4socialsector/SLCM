frappe.ui.form.on("Fee Invoice", {
	refresh: function (frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Paid" && frm.doc.outstanding_amount > 0) {
			frm.add_custom_button(__("Pay Online"), function () {
				frm.events.pay_online(frm);
			}, __("Actions"));
		}
	},

	pay_online: function (frm) {
		frappe.dom.freeze(__('Redirecting to Payment Gateway...'));
		frm.call({
			doc: frm.doc,
			method: "initiate_online_payment",
			callback: function (r) {
				frappe.dom.unfreeze();
				if (r.message) {
					window.location.href = r.message;
				}
			},
			error: function () {
				frappe.dom.unfreeze();
			}
		});
	}
});
