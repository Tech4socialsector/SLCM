frappe.ui.form.on('Refund Request', {
	refresh: function(frm) {
		if (frm.doc.status === 'Approved' && !frm.is_new()) {
			frm.add_custom_button(__('Process Refund'), function() {
				frappe.confirm(__('Are you sure you want to process this refund? This will initiate the transaction via Razorpay.'), function() {
					// Show a quick alert instead of freezing the whole screen
					frappe.show_alert({
						message: __('Initiating refund with Razorpay...'),
						indicator: 'blue'
					});
					
					frappe.call({
						method: 'slcm.admission_cancel_api.process_refund',
						args: { name: frm.doc.name },
						callback: function(r) {
							if (r.message && r.message.status === 'Success') {
								frappe.msgprint({
									title: __('Success'),
									message: __('Refund Processed successfully'),
									indicator: 'green'
								});
							}
							// Always reload to show new status or failure message
							frm.reload_doc();
						}
					});
				});
			});
		}

		if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry Refund'), function() {
				frm.set_value('status', 'Approved');
				frm.save();
			});
		}
	},

	payment_request: function(frm) {
		if (frm.doc.payment_request) {
			frappe.db.get_value('Fee Payment', frm.doc.payment_request, ['amount', 'reference_number', 'payment_date'], (r) => {
				if (r) {
					frm.set_value('amount_paid', r.amount);
					frm.set_value('razorpay_payment_id', r.reference_number);
					
					// If it's a new record and no policy/type is set, try to auto-calculate
					if (!frm.doc.refund_policy && frm.doc.refund_type !== 'Full' && r.payment_date) {
						const today = frappe.datetime.get_today();
						const days = frappe.datetime.get_diff(today, r.payment_date);
						
						frappe.call({
							method: 'frappe.client.get_list',
							args: {
								doctype: 'Refund Policy',
								filters: { is_active: 1 },
								fields: ['name', 'refund_percentage', 'days_from_payment'],
								order_by: 'days_from_payment asc'
							},
							callback: function(res) {
								if (res.message && res.message.length > 0) {
									let selected = null;
									for (let p of res.message) {
										if (days <= p.days_from_payment) {
											selected = p;
											break;
										}
									}
									if (!selected) {
										selected = res.message[res.message.length - 1];
									}
									
									if (selected) {
										frm.set_value('refund_policy', selected.name);
										frm.trigger('calculate_refund_amount');
									}
								}
							}
						});
					} else {
						frm.trigger('calculate_refund_amount');
					}
				}
			});
		}
	},

	refund_type: function(frm) {
		if (frm.doc.refund_type === 'Full') {
			frm.set_value('refund_policy', '');
		}
		frm.trigger('calculate_refund_amount');
	},

	refund_policy: function(frm) {
		frm.trigger('calculate_refund_amount');
	},

	calculate_refund_amount: function(frm) {
		if (frm.doc.refund_type === 'Full') {
			frm.set_value('refund_amount', frm.doc.amount_paid);
		} else if (frm.doc.refund_policy) {
			frappe.db.get_value('Refund Policy', frm.doc.refund_policy, 'refund_percentage', (r) => {
				if (r && r.refund_percentage !== undefined) {
					let amount = flt(frm.doc.amount_paid) * (flt(r.refund_percentage) / 100.0);
					frm.set_value('refund_amount', amount);
				}
			});
		}
	}
});
