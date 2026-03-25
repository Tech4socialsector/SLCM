frappe.ui.form.on('Refund Transaction', {
	refund_request: function(frm) {
		if (frm.doc.refund_request) {
			frappe.db.get_value('Refund Request', frm.doc.refund_request, ['payment_request', 'razorpay_payment_id', 'refund_amount'], (r) => {
				if (r) {
					frm.set_value('payment_request', r.payment_request);
					frm.set_value('razorpay_payment_id', r.razorpay_payment_id);
					frm.set_value('refund_amount', r.refund_amount);
				}
			});
		} else {
			frm.set_value('payment_request', '');
			frm.set_value('razorpay_payment_id', '');
			frm.set_value('refund_amount', 0);
		}
	}
});
