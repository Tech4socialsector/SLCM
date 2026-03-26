frappe.ui.form.on('Refund Transaction', {
	refresh: function(frm) {
		if (frm.doc.status === 'Processed' && frm.doc.refund_request) {
			frm.add_custom_button(__('Download Receipt'), function() {
				const print_url = `/api/method/frappe.utils.print_format.download_pdf?doctype=Refund%20Request&name=${encodeURIComponent(frm.doc.refund_request)}&format=Refund%20Receipt%20Format&no_letterhead=0`;
				window.open(print_url);
			});
		}
	},
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
