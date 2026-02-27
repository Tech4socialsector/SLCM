frappe.ready(function () {
	// --------------------------------------------------
	// Sets the declaration consent as mandatory based on the candidate's age (under 18).
	// --------------------------------------------------
	function toggle_declaration_section() {
		try {
			const dob_val = frappe.web_form.get_value('candidate_dob');
			let is_mandatory = false;
			let age = null;

			if (dob_val) {
				const dob = new Date(dob_val);
				const today = new Date();
				age = today.getFullYear() - dob.getFullYear();
				const m = today.getMonth() - dob.getMonth();

				if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
					age--;
				}

				if (age < 18) {
					is_mandatory = true;
				}
			}

			if (typeof frappe.web_form.set_df_property === 'function') {
				frappe.web_form.set_df_property('declaration_consent', 'reqd', is_mandatory ? 1 : 0);
			} else if (frappe.web_form.fields_dict && frappe.web_form.fields_dict['declaration_consent']) {
				frappe.web_form.fields_dict['declaration_consent'].df.reqd = is_mandatory ? 1 : 0;
				frappe.web_form.fields_dict['declaration_consent'].refresh();
			}

		} catch (e) {
			// Error handling silently in production or log to system console if available
		}
	}

	frappe.web_form.on('candidate_dob', function () {
		toggle_declaration_section();
	});

	// Run on load
	console.log("Loading Custom JS for Payment");
	toggle_declaration_section();
	setup_payment();

	// --------------------------------------------------
	// Initializes the payment flow by loading the Razorpay checkout script if not already loaded.
	// Required to ensure the Razorpay library is available before creating the payment button.
	// --------------------------------------------------
	function setup_payment() {
		console.log("Setting up payment...");
		// Load Razorpay Script
		if (typeof Razorpay === 'undefined') {
			let script = document.createElement('script');
			script.src = 'https://checkout.razorpay.com/v1/checkout.js';
			script.onload = function () {
				console.log("Razorpay script loaded");
				init_payment_button();
			};
			document.head.appendChild(script);
		} else {
			console.log("Razorpay script already loaded");
			init_payment_button();
		}
	}

	// --------------------------------------------------
	// Replaces the standard Frappe "Save" button with a custom "Proceed to Payment" button.
	// Required to enforce the payment step explicitly after successfully saving the form.
	// --------------------------------------------------
	function init_payment_button() {
		console.log("Initializing payment button...");
		let $payment_trigger = $('.web-form-footer .web-form-actions');
		if ($payment_trigger.length === 0) {
			$payment_trigger = $('.web-form-actions');
		}

		if ($payment_trigger.length) {
			// Hide the default standard Frappe "Save" button to enforce payment
			$('.web-form-actions').find('button.btn-primary').hide();
			$('.web-form-actions').find('[data-action="save"]').hide();

			// Add a professional Proceed to Payment button
			let $btn = $(`<button class="btn btn-primary ml-2" style="display: flex; align-items: center; gap: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="5" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="2" y1="10" x2="22" y2="10"></line>
                </svg>
                Proceed to Payment
            </button>`);

			$btn.click(function (e) {
				console.log("Proceed to Payment clicked");
				e.preventDefault();

				// OVERRIDE FRAppe's DEFAULT BEHAVIOR to prevent redirect and form hiding
				if (typeof frappe.web_form !== 'undefined' && !frappe.web_form._custom_handle_success) {
					frappe.web_form._original_handle_success = frappe.web_form.handle_success;
					frappe.web_form.handle_success = function (data) {
						// Suppress default UI changes (hiding form, redirecting to gateway)
						frappe.form_dirty = false;
					};
					frappe.web_form._custom_handle_success = true;
				}

				// Give user feedback while saving
				let original_html = $btn.html();
				$btn.prop('disabled', true).html('Processing...');

				frappe.web_form.save().then(() => {
					console.log("Form saved, initiating payment...");

					initiate_payment();
					// Restore button state after some time in case modal closes
					setTimeout(() => {
						$btn.prop('disabled', false).html(original_html);
					}, 3000);
				}).catch(() => {
					// On validation error, re-enable
					$btn.prop('disabled', false).html(original_html);
				});
			});

			// Append so it sits on the right side next to Discard
			$payment_trigger.append($btn);
			console.log("Button added to DOM");
		} else {
			console.error("Could not find place to insert payment button");
		}
	}

	// --------------------------------------------------
	// Calls the backend to create a new Razorpay order for the submitted web form.
	// Required to securely fetch the checkout options and order ID from Razorpay to initialize the modal.
	// --------------------------------------------------
	function initiate_payment() {
		frappe.call({
			method: "slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education.create_razorpay_order",
			args: {
				doc_name: frappe.web_form.doc.name
			},
			freeze: true,
			freeze_message: "Creating Order...",
			callback: function (r) {
				if (r.message) {
					// Save doc_name NOW — before modal opens — so the success page
					// fallback works regardless of how redirect happens
					localStorage.setItem('recent_fle_payment_doc', frappe.web_form.doc.name);
					open_razorpay_checkout(r.message);
				}
			}
		});
	}

	// --------------------------------------------------
	// Configures and opens the Razorpay checkout modal with the order details and handles the callbacks.
	// Required to securely process the payment client-side and communicate success/failure to the backend.
	// --------------------------------------------------
	function open_razorpay_checkout(data) {
		console.log("Razorpay Data:", data);
		var options = {
			"key": data.key_id,
			"amount": data.amount,
			"currency": data.currency,
			"name": "Foundations for a Legal Education",
			"description": "Admission Fees",
			"order_id": data.order_id,
			"handler": function (response) {
				// Verify payment signature on backend and redirect to success page
				frappe.call({
					method: "slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education.verify_payment",
					args: {
						razorpay_payment_id: response.razorpay_payment_id,
						razorpay_order_id: response.razorpay_order_id,
						razorpay_signature: response.razorpay_signature,
						doc_name: frappe.web_form.doc.name,
						amount_paise: data.amount  // order amount in paise from Razorpay
					},
					freeze: true,
					freeze_message: "Verifying payment...",
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							// Redirect to success page with receipt details
							let doc_name = frappe.web_form.doc.name;
							let transaction_id = response.razorpay_payment_id;
							// Save to localStorage as fallback in case params get stripped
							localStorage.setItem('recent_fle_payment_doc', doc_name);
							window.location.href = "/fle-success-page?name=" + encodeURIComponent(doc_name) + "&transaction_id=" + encodeURIComponent(transaction_id);
						} else {
							frappe.msgprint({
								title: __('Verification Failed'),
								message: r.message ? r.message.message : __('Payment verification failed. Please contact support.'),
								indicator: 'red'
							});
						}
					}
				});
			},
			"prefill": {
				"name": frappe.web_form.doc.candidate_name,
				"email": frappe.web_form.doc.email_address,
				"contact": frappe.web_form.doc.candidate_contact_number
			},
			"theme": {
				"color": "#3399cc"
			},
			"modal": {
				"ondismiss": function () {
					frappe.call({
						method: "slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education.update_payment_status",
						args: {
							doc_name: frappe.web_form.doc.name,
							status: "Cancelled"
						},
						callback: function (r) {
							frappe.msgprint({
								title: __('Payment Cancelled'),
								message: __('You have cancelled the payment process.'),
								indicator: 'orange'
							});
						}
					});
				}
			}
		};
		var rzp1 = new Razorpay(options);
		rzp1.on('payment.failed', function (response) {
			frappe.call({
				method: "slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education.update_payment_status",
				args: {
					doc_name: frappe.web_form.doc.name,
					status: "Payment Failed"
				},
				callback: function (r) {
					frappe.msgprint({
						title: __('Payment Failed'),
						message: response.error ? response.error.description : __('Payment process failed.'),
						indicator: 'red'
					});
				}
			});
		});
		rzp1.open();
	}

	// verify_payment function removed to strictly enforce backend-only payment verification (Master Tip)
});

