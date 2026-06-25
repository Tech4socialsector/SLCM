frappe.ui.form.on('Admission Cancellation', {
	refresh: function(frm) {
		if (frm.doc.refund_request) {
			frm.add_custom_button(__('View Refund Request'), function() {
				frappe.set_route('Form', 'Refund Request', frm.doc.refund_request);
			}, __('Actions'));
		}
	},
	applicant: function(frm) {
		if (frm.doc.applicant) {
			frappe.db.get_value('Applicant', frm.doc.applicant, ['program', 'campus'], (r) => {
				if (r) {
					frm.set_value('program', r.program);
					frm.set_value('campus', r.campus);
				}
			});
			
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Offer Letter',
					filters: {
						applicant: frm.doc.applicant,
						status: ['not in', ['Rejected', 'Withdrawn']]
					},
					order_by: 'creation desc',
					limit: 1
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						const offer_name = r.message[0].name;
						frm.set_value('offer', offer_name);
						
						// Fetch associated payment details
						frappe.db.get_value('Applicant Fee Assignment', 
							{offer_letter: offer_name, status: ['!=', 'Cancelled']}, 'fee_invoice', (afa) => {
								if (afa && afa.fee_invoice) {
									frappe.call({
										method: 'frappe.client.get_list',
										args: {
											doctype: 'Fee Payment',
											filters: {fee_invoice: afa.fee_invoice, status: 'Submitted'},
											fields: ['name', 'amount', 'reference_number'],
											limit: 1
										},
										callback: (pay) => {
											if (pay.message && pay.message.length > 0) {
												frm.set_value('payment_request', pay.message[0].name);
												frm.set_value('amount_paid', pay.message[0].amount);
												frm.set_value('razorpay_id', pay.message[0].reference_number);
											}
										}
									});
								}
							}
						);
					} else {
						frm.set_value('offer', '');
						frm.set_value('payment_request', '');
						frm.set_value('amount_paid', 0);
						frm.set_value('razorpay_id', '');
					}
				}
			});
		} else {
			frm.set_value('program', '');
			frm.set_value('campus', '');
			frm.set_value('offer', '');
		}
	}
});
