frappe.ui.form.on("PACE Applicant Fee Assignment", {
	refresh: function(frm) {
		// Calculate total when refresh
		frm.trigger("calculate_totals");

		if (frm.doc.status === "Assigned" && frm.doc.final_payable_amount > 0) {
			frm.add_custom_button(__("Pay Now"), function() {
				frm.trigger("pay_now");
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Paid") {
			frm.add_custom_button(__("Enroll Student"), function() {
				frappe.confirm(__("Are you sure you want to enroll this applicant?"), function() {
					frappe.call({
						method: "slcm.pace.api.service.pace_to_student.convert_pace_to_student",
						args: {
							pace_app_name: frm.doc.applicant
						},
						freeze: true,
						freeze_message: __("Enrolling..."),
						callback: function(r) {
							if (r.message && r.message.created) {
								frappe.show_alert({
									message: __("Successfully enrolled applicant. Student Master {0} created.", [r.message.student_name]),
									indicator: "green"
								});
								frm.reload_doc();
							}
						}
					});
				});
			}).addClass("btn-primary");
		}
	},
	currency: function(frm) {
		// Refresh child table to show updated currency symbols
		frm.refresh_field("fee_components");
	},
	pay_now: function(frm) {
		frappe.confirm(__("Do you want to proceed with the payment of {0}?", [format_currency(frm.doc.final_payable_amount, frm.doc.currency)]), function() {
			frappe.call({
				method: "slcm.pace.api.create_pace_razorpay_order",
				args: {
					assignment_name: frm.doc.name
				},
				callback: function(r) {
					if (r.message) {
						const data = r.message;
						const options = {
							"key": data.key_id,
							"amount": data.amount,
							"currency": data.currency,
							"name": "NLSIU PACE",
							"description": "Fee Payment for " + frm.doc.program,
							"order_id": data.order_id,
							"handler": function (response) {
								frappe.call({
									method: "slcm.pace.api.verify_pace_payment",
									args: {
										razorpay_payment_id: response.razorpay_payment_id,
										razorpay_order_id: response.razorpay_order_id,
										razorpay_signature: response.razorpay_signature,
										assignment_name: frm.doc.name
									},
									callback: function(res) {
										if (res.message && res.message.status === "success") {
											frappe.msgprint(__("Payment Successful"));
											frm.reload_doc();
										}
									}
								});
							},
							"prefill": {
								"name": frm.doc.applicant_name,
								"email": data.payer_email
							},
							"theme": {
								"color": "#3399cc"
							}
						};

						if (typeof Razorpay === 'undefined') {
							$.getScript('https://checkout.razorpay.com/v1/checkout.js', function () {
								const rzp = new Razorpay(options);
								rzp.open();
							});
						} else {
							const rzp = new Razorpay(options);
							rzp.open();
						}
					}
				}
			});
		});
	},
	calculate_totals: function(frm) {
		if (frm.doc.status !== "Paid" && frm.doc.fee_components && frm.doc.fee_components.length > 0) {
			let total_amount = 0;
			frm.doc.fee_components.forEach(row => {
				total_amount += row.total_amount || 0;
			});
			frm.set_value("total_amount", total_amount);
			frm.set_value("final_payable_amount", total_amount);
		}
	}
});

frappe.ui.form.on("PACE Fee Component", {
	amount: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let total = row.amount + (row.tax_amount || 0);
		frappe.model.set_value(cdt, cdn, "total_amount", total);
		frm.trigger("calculate_totals");
	},
	tax_amount: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let total = row.amount + (row.tax_amount || 0);
		frappe.model.set_value(cdt, cdn, "total_amount", total);
		frm.trigger("calculate_totals");
	},
	fee_components_remove: function(frm) {
		frm.trigger("calculate_totals");
	}
});
