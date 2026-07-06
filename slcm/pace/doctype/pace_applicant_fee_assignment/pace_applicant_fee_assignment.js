frappe.ui.form.on("PACE Applicant Fee Assignment", {
	refresh: function(frm) {
		// Calculate total when refresh
		frm.trigger("calculate_totals");

        setTimeout(() => {

            // Hide Assignments
            frm.page.wrapper.find('.form-assignments').hide();

        }, 200);
		if (frm.doc.status === "Assigned" && frm.doc.final_payable_amount > 0) {
			frm.add_custom_button(__("Pay Now"), function() {
				frm.trigger("pay_now");
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Paid" && frm.doc.fee_type === "Course Fee") {
			frm.add_custom_button(__("Convert to Student"), function() {
				frappe.confirm(__("Are you sure you want to enroll this applicant?"), function() {
					frappe.call({
						method: "slcm.pace.api.service.pace_to_student.convert_pace_to_student",
						args: {
							pace_app_name: frm.doc.applicant
						},
						freeze: true,
						freeze_message: __("Enrolling..."),
						callback: function(r) {
							if (r.message) {
								const res = r.message;
								
								const success_count = res.created ? 1 : 0;
								const skipped_count = res.created ? 0 : 1;
								const error_count = 0;
								
								let message = `
									<div style="padding: 10px;">
										<div style="display: flex; gap: 15px; margin-bottom: 20px;">
											<div style="flex: 1; padding: 12px; background: #f0fff4; border: 1px solid #c6f6d5; border-radius: 8px; text-align: center;">
												<h3 style="margin: 0; color: #2f855a;">${success_count}</h3>
												<div style="font-size: 11px; color: #38a169; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Successful')}</div>
											</div>
											<div style="flex: 1; padding: 12px; background: #fef9c3; border: 1px solid #fef08a; border-radius: 8px; text-align: center;">
												<h3 style="margin: 0; color: #a16207;">${skipped_count}</h3>
												<div style="font-size: 11px; color: #ca8a04; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Skipped')}</div>
											</div>
											<div style="flex: 1; padding: 12px; background: ${error_count > 0 ? '#fff5f5' : '#f7fafc'}; border: 1px solid ${error_count > 0 ? '#fed7d7' : '#edf2f7'}; border-radius: 8px; text-align: center;">
												<h3 style="margin: 0; color: ${error_count > 0 ? '#c53030' : '#718096'};">${error_count}</h3>
												<div style="font-size: 11px; color: ${error_count > 0 ? '#e53e3e' : '#a0aec0'}; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Failed')}</div>
											</div>
										</div>
								`;

								if (skipped_count > 0) {
									message += `
										<div style="margin-bottom: 8px; font-weight: 600; color: #4a5568;">${__('Skipped Candidates (Already converted or missing requirements):')}</div>
										<div style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 15px;">
											<table class="table table-bordered table-condensed" style="margin:0; font-size: 12px; background: #fff;">
												<thead style="background: #f8fafc;">
													<tr>
														<th style="width: 35%;">${__('Applicant')}</th>
														<th>${__('Reason')}</th>
													</tr>
												</thead>
												<tbody>
													<tr>
														<td style="font-weight: 600;">${frappe.utils.escape_html(frm.doc.applicant)}</td>
														<td style="color: #ca8a04; word-break: break-word;">${__('Already converted to Student {0}', [res.student_name])}</td>
													</tr>
												</tbody>
											</table>
										</div>
									`;
								}
								
								message += `</div>`;
								
								frappe.msgprint({
									title: __("Convert to Student Report"),
									message: message,
									wide: true,
									indicator: error_count === 0 && skipped_count === 0 ? "green" : (error_count > 0 ? "red" : "orange"),
									primary_action: {
										label: __("Open Student Master"),
										action() {
											frappe.hide_msgprint();
											frappe.set_route("Form", "Student Master", res.student_name);
										},
									},
								});
								frm.reload_doc();
							}
						}
					});
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Paid") {
			let is_admin = false;
			const admin_roles = ["System Manager", "Administrator", "Academic Manager", "PACE Admission Manager", "Admission Admin"];
			for (let role of admin_roles) {
				if (frappe.user_roles.includes(role)) {
					is_admin = true;
					break;
				}
			}
			if (!is_admin) {
				frm.disable_form();
			}
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
							"name": "PACE",
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
