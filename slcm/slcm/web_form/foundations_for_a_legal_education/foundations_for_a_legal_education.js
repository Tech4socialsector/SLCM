frappe.ready(function () {
	function toggle_declaration_section() {
		try {
			const dob_val = frappe.web_form.get_value('candidate_dob');
			// Default to false (hidden) if no DOB or error
			let show_declaration = false;
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
					show_declaration = true;
				}
			}

			// --- 1. Toggle Section Break (Declaration) ---
			// Try standard API first
			toggle_field('section_break_declaration', show_declaration);

			// MASTER FALLBACK: Find the section header by text 'Declaration'
			// We search for header elements containing "Declaration" and hide their parent container
			const $headers = $('.section-head, .section-header, h2, h3, h4, h5, h6').filter(function () {
				return $(this).text().trim() === 'Declaration';
			});

			if ($headers.length > 0) {
				// Determine the container (usually .web-form-section or .section-break)
				const $section_container = $headers.closest('.web-form-section, .section-break');
				if ($section_container.length > 0) {
					$section_container.toggle(show_declaration);
				} else {
					// Fallback: hide the header and maybe its next sibling if it's a flat structure
					$headers.toggle(show_declaration);
					// This is risky without a container, but better than nothing
				}
			}

			// --- 2. Toggle HTML Content ---
			toggle_field('declaration_html', show_declaration);

			// MASTER FALLBACK: Find by content text
			const unique_text = "This declaration is only for the students below 18 years of age";
			// Find elements containing this text
			const $html_content = $(`div:contains("${unique_text}"), p:contains("${unique_text}")`).filter(function () {
				// Ensure it's the actual content element, not a parent container
				return $(this).children().length === 0 || $(this).hasClass('control-value') || $(this).hasClass('form-control');
			});
			$html_content.closest('.form-group, .web-form-field').toggle(show_declaration);

			// --- 3. Toggle Consent Checkbox ---
			toggle_field('declaration_consent', show_declaration);

		} catch (e) {
			// Error handling silently in production or log to system console if available
		}
	}

	function toggle_field(fieldname, show) {
		try {
			// Method 1: Try toggle_display (v15+)
			if (typeof frappe.web_form.toggle_display === 'function') {
				frappe.web_form.toggle_display(fieldname, show);
				return;
			}

			// Method 2: Try set_field_property (v13/14)
			if (typeof frappe.web_form.set_field_property === 'function') {
				frappe.web_form.set_field_property(fieldname, 'hidden', show ? 0 : 1);
				return;
			}

			// Method 3: Direct DOM manipulation via get_field
			let field = frappe.web_form.get_field(fieldname);
			if (field && field.$wrapper) {
				field.$wrapper.toggle(show);
				return;
			}

			// Method 4: Data attribute selector
			let $el = $('[data-fieldname="' + fieldname + '"]');
			if ($el.length) {
				// If it's a section break, hide the container
				if ($el.hasClass('section-break') || $el.hasClass('web-form-section')) {
					$el.toggle(show);
				} else {
					$el.closest('.form-group, .web-form-field').toggle(show);
				}
			}
		} catch (e) {
			// Error handling silently
		}
	}

	frappe.web_form.on('candidate_dob', function () {
		toggle_declaration_section();
	});

	// Run on load
	console.log("Loading Custom JS for Payment");
	toggle_declaration_section();
	setup_payment();

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

	function init_payment_button() {
		console.log("Initializing payment button...");
		// Find the payment section or a suitable place to put the button
		// We'll place it after 'payment_instructions' HTML field
		let $payment_trigger = $('[data-fieldname="payment_instructions"]');
		console.log("Payment trigger (field):", $payment_trigger.length);
		if ($payment_trigger.length === 0) {
			// Fallback if field not found
			$payment_trigger = $('.web-form-actions');
			console.log("Payment trigger (actions):", $payment_trigger.length);
		}

		if ($payment_trigger.length) {
			let amount = frappe.web_form.doc.amount || 10000;
			// Button styled like Frappe School 'Proceed to Payment'
			let $btn = $(`<button class="btn btn-lg btn-primary" style="margin-top: 15px; margin-bottom: 15px;">Proceed to Payment</button>`);

			$btn.click(function (e) {
				console.log("Proceed to Payment clicked");
				e.preventDefault();
				// Save form first
				frappe.web_form.save().then(() => {
					console.log("Form saved, initiating payment...");
					initiate_payment();
				});
			});

			// Insert after instructions if found, else prepend to actions
			if ($payment_trigger.hasClass('web-form-actions')) {
				$payment_trigger.prepend($btn);
			} else {
				$payment_trigger.after($btn);
			}
			console.log("Button added to DOM");
		} else {
			console.error("Could not find place to insert payment button");
		}
	}

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
					open_razorpay_checkout(r.message);
				}
			}
		});
	}

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
				verify_payment(response, data.order_id);
			},
			"prefill": {
				"name": frappe.web_form.doc.candidate_name,
				"email": frappe.web_form.doc.email_address,
				"contact": frappe.web_form.doc.candidate_contact_number
			},
			"theme": {
				"color": "#3399cc"
			}
		};
		var rzp1 = new Razorpay(options);
		rzp1.on('payment.failed', function (response) {
			frappe.msgprint({
				title: __('Payment Failed'),
				message: response.error.description,
				indicator: 'red'
			});
		});
		rzp1.open();
	}

	function verify_payment(response, order_id) {
		frappe.call({
			method: "slcm.slcm.doctype.foundations_for_a_legal_education.foundations_for_a_legal_education.verify_payment",
			args: {
				razorpay_payment_id: response.razorpay_payment_id,
				razorpay_order_id: response.razorpay_order_id,
				razorpay_signature: response.razorpay_signature,
				doc_name: frappe.web_form.doc.name
			},
			freeze: true,
			freeze_message: "Verifying Payment...",
			callback: function (r) {
				if (r.message && r.message.status === 'success') {
					frappe.msgprint({
						title: __('Success'),
						message: __('Payment Successful!'),
						indicator: 'green'
					});
					setTimeout(function () {
						window.location.reload();
					}, 2000);
				}
			}
		});
	}
});


