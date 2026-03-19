frappe.ui.form.on('Refund Request', {
	refresh: function(frm) {
		if (frm.is_new()) return;
		
		frm.clear_custom_buttons();

		// Workflow Actions
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button(__('Submit for Review'), function() {
				frm.set_value('status', 'Under Review');
				frm.save();
			}, __('Actions'));
		}

		if (frm.doc.status === 'Under Review') {
			frm.add_custom_button(__('Approve'), function() {
				frm.set_value('status', 'Approved');
				frm.save();
			}, __('Actions'));

			frm.add_custom_button(__('Reject'), function() {
				frappe.prompt([
					{
						label: __('Reason for Rejection'),
						fieldname: 'reason',
						fieldtype: 'Small Text',
						reqd: 1
					}
				], (values) => {
					frm.set_value('status', 'Rejected');
					frm.set_value('failure_message', values.reason);
					frm.save();
				}, __('Reject Refund Request'), __('Confirm Rejection'));
			}, __('Actions'));
		}

		if (frm.doc.status === 'Approved') {
			frm.add_custom_button(__('Process Refund'), function() {
				frappe.confirm(
					__('Are you sure you want to process this refund? This will initiate the transaction via Razorpay.'),
					function() {

						// ── Step 1: Show Processing state immediately on UI ──
						frm.doc.status = 'Processing';
						frm.refresh_field('status');
						frm.disable_save();

						// ── Step 2: Show inline loading indicator ──
						frappe.show_alert({
							message: __('Processing refund, please wait...'),
							indicator: 'blue'
						});

						frappe.call({
							method: 'slcm.admission_cancel_api.process_refund',
							args: { name: frm.doc.name },
							callback: function(r) {
								if (r.message && r.message.status === 'Success') {

									// ── Step 3: Backend done → update UI to Processed ──
									frm.doc.status = 'Processed';
									frm.refresh_field('status');

									frappe.show_alert({
										message: __('Refund Processed Successfully!'),
										indicator: 'green'
									});

									// ── Step 4: Reload full form after short delay
									//            so user can see the success alert ──
									setTimeout(function() {
										frm.reload_doc();
									}, 1200);

								} else {

									// ── Step 5: If failed → update UI to Failed ──
									frm.doc.status = 'Failed';
									frm.refresh_field('status');

									frappe.show_alert({
										message: r.message && r.message.message
											? r.message.message
											: __('Refund processing failed. Please retry.'),
										indicator: 'red'
									});

									// Reload to sync with backend failed state
									setTimeout(function() {
										frm.reload_doc();
									}, 1200);
								}
							},
							error: function(err) {
								// ── Step 6: Network/server error handler ──
								frm.doc.status = 'Failed';
								frm.refresh_field('status');

								frappe.show_alert({
									message: __('An error occurred while processing the refund.'),
									indicator: 'red'
								});

								setTimeout(function() {
									frm.reload_doc();
								}, 1200);
							}
						});
					}
				);
			});
			frm.change_custom_button_type(__('Process Refund'), null, 'primary');
		}

		// ── Auto-refresh if form is stuck in Processing ──
		// This handles edge case where user opens form mid-processing
		if (frm.doc.status === 'Processing') {
			frm.disable_save();

			frappe.show_alert({
				message: __('Refund is being processed...'),
				indicator: 'blue'
			});

			// Poll every 3 seconds until status changes from Processing
			if (frm._processing_poll) clearInterval(frm._processing_poll);
			
			frm._processing_poll = setInterval(function() {
				frappe.db.get_value(
					'Refund Request',
					frm.doc.name,
					'status',
					function(r) {
						if (r && r.status && r.status !== 'Processing') {
							// Status has changed — stop polling and reload
							clearInterval(frm._processing_poll);
							frm._processing_poll = null;

							frappe.show_alert({
								message: r.status === 'Processed'
									? __('Refund has been Processed!')
									: __('Refund status updated: ') + r.status,
								indicator: r.status === 'Processed' ? 'green' : 'orange'
							});

							frm.reload_doc();
						}
					}
				);
			}, 3000); // poll every 3 seconds
		}

		if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry Refund'), function() {
				frm.set_value('status', 'Approved');
				frm.save();
			});
			frm.change_custom_button_type(__('Retry Refund'), null, 'primary');
		}
	},

	// ── Clear polling interval when form is refreshed/navigated away ──
	before_unload: function(frm) {
		if (frm._processing_poll) {
			clearInterval(frm._processing_poll);
			frm._processing_poll = null;
		}
	},

	payment_request: function(frm) {
		if (frm.doc.payment_request) {
			frappe.db.get_value('Fee Payment', frm.doc.payment_request, ['amount', 'reference_number', 'payment_date'], (r) => {
				if (r) {
					frm.set_value('amount_paid', r.amount);
					frm.set_value('razorpay_payment_id', r.reference_number);
					
					if (frm.doc.refund_type === 'Partial' && r.payment_date) {
						frm.trigger('select_policy_by_days');
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
			frm.trigger('calculate_refund_amount');
		} else if (frm.doc.refund_type === 'Partial') {
			frm.trigger('select_policy_by_days');
		}
	},

	select_policy_by_days: function(frm) {
		if (!frm.doc.payment_request) return;

		frappe.db.get_value('Fee Payment', frm.doc.payment_request, 'payment_date', (r) => {
			if (r && r.payment_date) {
				const today = frappe.datetime.get_today();
				const days = frappe.datetime.get_diff(today, r.payment_date);
				
				frappe.call({
					method: 'frappe.client.get_list',
					args: {
						doctype: 'Refund Policy',
						filters: { is_active: 1 },
						fields: ['name', 'days_from_payment'],
						order_by: 'days_from_payment asc'
					},
					callback: function(res) {
						if (res.message && res.message.length > 0) {
							let selected_policy = null;
							for (let p of res.message) {
								if (days <= p.days_from_payment) {
									selected_policy = p.name;
									break;
								}
							}
							if (!selected_policy) {
								selected_policy = res.message[res.message.length - 1].name;
							}
							
							if (selected_policy) {
								frm.set_value('refund_policy', selected_policy);
								frm.trigger('calculate_refund_amount');
							}
						}
					}
				});
			}
		});
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
