frappe.ui.form.on('Refund Request', {
	refresh: function(frm) {
		// ── Filter: only Admission Fee, submitted AFA for this applicant ──
		frm.set_query('applicant_fee_assignment', function() {
			const filters = {
				fee_type: 'Admission Fee',
				docstatus: 1
			};
			if (frm.doc.applicant) {
				filters['applicant'] = frm.doc.applicant;
			}
			return { filters };
		});

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
								// Show server-side exceptions (frappe.throw, validation errors)
								if (r.exc) {
									frm.doc.status = 'Failed';
									frm.refresh_field('status');
									frappe.show_alert({
										message: __('Refund failed: ') + (r.exc || __('Unknown server error')),
										indicator: 'red'
									});
									setTimeout(function() { frm.reload_doc(); }, 1500);
									return;
								}

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

									var failMsg = (r.message && r.message.message)
										? r.message.message
										: __('Refund processing failed. Please retry.');

									frappe.show_alert({
										message: failMsg,
										indicator: 'red'
									});

									// Also show as a msgprint dialog so it's not missed
									frappe.msgprint({
										title: __('Refund Failed'),
										message: failMsg,
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

								var errMsg = (err && err.message) ? err.message : __('An error occurred while processing the refund.');
								frappe.show_alert({
									message: errMsg,
									indicator: 'red'
								});
								frappe.msgprint({ title: __('Refund Error'), message: errMsg, indicator: 'red' });

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

		if (frm.doc.status === 'Processed') {
			frm.add_custom_button(__('Download Receipt'), function() {
				const print_url = `/api/method/frappe.utils.print_format.download_pdf?doctype=Refund%20Request&name=${encodeURIComponent(frm.doc.name)}&format=Refund%20Receipt%20Format&no_letterhead=0`;
				window.open(print_url);
			});
		}

		if (['Approved', 'Processing', 'Processed', 'Failed'].includes(frm.doc.status) && frm.doc.razorpay_payment_id && frm.doc.refund_type !== 'No Refund') {
			frm.add_custom_button(__('Reconcile with Razorpay'), function() {
				frappe.call({
					method: 'slcm.admission_cancel_api.reconcile_refund_status',
					args: { name: frm.doc.name },
					callback: function(r) {
						if (r.message) {
							frappe.show_alert({
								message: r.message.message,
								indicator: r.message.status === 'Success' ? 'green' : r.message.status === 'Info' ? 'blue' : 'red'
							});
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));
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

	// ── Re-apply AFA filter when applicant changes ──
	applicant: function(frm) {
		frm.set_query('applicant_fee_assignment', function() {
			const filters = {
				fee_type: 'Admission Fee',
				docstatus: 1
			};
			if (frm.doc.applicant) {
				filters['applicant'] = frm.doc.applicant;
			}
			return { filters };
		});
		// Clear AFA if applicant changes
		frm.set_value('applicant_fee_assignment', '');
	},

	// ── Clear polling interval when form is refreshed/navigated away ──
	before_unload: function(frm) {
		if (frm._processing_poll) {
			clearInterval(frm._processing_poll);
			frm._processing_poll = null;
		}
	},

	applicant_fee_assignment: function(frm) {
		if (!frm.doc.applicant_fee_assignment) return;

		// Fetch the offer_letter from the AFA, then get the Payment Receipt
		frappe.db.get_value('Applicant Fee Assignment', frm.doc.applicant_fee_assignment,
			['offer_letter', 'final_payable_amount'], (afa) => {
			if (!afa || !afa.offer_letter) return;

			frappe.db.get_value('Applicant Payment Receipt',
				{ offer_letter: afa.offer_letter },
				['net_amount', 'total_amount', 'transaction_id'],
				(r) => {
					if (r) {
						const paidAmt = (r.net_amount && r.net_amount > 0) ? r.net_amount : r.total_amount;
						frm.set_value('amount_paid', paidAmt);
						frm.set_value('razorpay_payment_id', r.transaction_id);

						if (frm.doc.refund_type === 'Partial') {
							frm.trigger('select_policy_by_days');
						} else {
							frm.trigger('calculate_refund_amount');
						}
					}
				}
			);
		});
	},

	refund_type: function(frm) {
		if (frm.doc.refund_type === 'Full') {
			frm.set_value('refund_policy', '');
			frm.trigger('calculate_refund_amount');
		} else if (frm.doc.refund_type === 'Partial') {
			frm.trigger('select_policy_by_days');
		} else if (frm.doc.refund_type === 'No Refund') {
			frm.set_value('refund_policy', '');
			frm.set_value('refund_amount', 0);
		}
	},

	select_policy_by_days: function(frm) {
		// Uses applicant_payment_receipt payment_date if available, falls back to today
		let paymentDatePromise;
		if (frm.doc.applicant_payment_receipt) {
			paymentDatePromise = frappe.db.get_value('Applicant Payment Receipt',
				frm.doc.applicant_payment_receipt, 'payment_date');
		} else {
			// No payment source available, skip
			return;
		}

		paymentDatePromise.then(r => {
			const paymentDate = r && r.message && r.message.payment_date;
			if (!paymentDate) return;

			const today = frappe.datetime.get_today();
			const days = frappe.datetime.get_diff(today, paymentDate);
			
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
		});
	},

	refund_policy: function(frm) {
		frm.trigger('calculate_refund_amount');
	},

	calculate_refund_amount: function(frm) {
		if (frm.doc.refund_type === 'Full') {
			frm.set_value('refund_amount', frm.doc.amount_paid);
		} else if (frm.doc.refund_type === 'No Refund') {
			frm.set_value('refund_amount', 0);
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
