frappe.pages['applicant-offer-lett'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('My Admission Offer'),
		single_column: true
	});

	new ApplicantOfferLetter(wrapper);
}

class ApplicantOfferLetter {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.init();
	}

	init() {
		this.fetch_data();
		this.setup_premium_loader();
	}

	setup_premium_loader() {
		let me = this;
		this.show_loader = (message) => {
			if ($('.premium-loader-overlay').length) return;
			const loader_html = `
				<div class="premium-loader-overlay" id="payment-loader">
					<div class="premium-loader-spinner"></div>
					<div class="premium-loader-text">${message || __('Processing...')}</div>
					<div class="premium-loader-subtext">${__('Please do not refresh or close this window.')}</div>
				</div>
			`;
			$('body').append(loader_html);
		};

		this.hide_loader = () => {
			$('.premium-loader-overlay').fadeOut(400, function () {
				$(this).remove();
			});
		};
	}


	fetch_data() {
		let me = this;
		// Check for offer name in the route (e.g. #applicant-offer-lett/OFFER-2026-0001)
		const route = frappe.get_route();
		const offer_name = route[1];

		frappe.call({
			method: 'slcm.admission.page.applicant_offer_lett.applicant_offer_lett.get_offer_details',
			args: {
				offer_name: offer_name
			},
			callback: function (r) {
				if (r.message && !r.message.error) {
					me.render(r.message);
				} else {
					me.render_error(r.message ? r.message.error : "Unknown Error");
				}
			}
		});
	}

	render(data) {
		let me = this;
		this.page.clear_inner_toolbar();
		this.page.clear_menu();

		window.cur_page = this;
		this.data = data;
		const { offer, applicant, fee_breakdown, rendered_content, currency, is_fee_paid, online_payment_enabled } = data;

		if (offer.status === 'Issued') {
			this.page.set_primary_action(__('Accept Admission Offer'), () => me.handle_accept(), 'octicon octicon-check');
			this.page.add_inner_button(__('Reject Admission Offer'), () => me.handle_reject(), __('Actions'));
		} else if (offer.status === 'Accepted' && !is_fee_paid && online_payment_enabled) {
			this.page.set_primary_action(__('Pay Fee'), () => me.handle_pay_fee(), 'octicon octicon-credit-card');
		} else {
			this.page.clear_primary_action();
		}
		this.page.set_secondary_action(__('Download Letter (PDF)'), () => me.handle_download(), 'octicon octicon-cloud-download');

		if (offer.status === 'Payment Completed' || is_fee_paid || applicant.status === 'Fee Paid') {
			this.page.add_inner_button(__('Download Receipt'), () => me.handle_download_receipt(), __('Actions'));
		}


		let html = `
			<div class="offer-container">
				<div class="row">
					<!-- Statistics & Actions -->
					<div class="col-md-4">
									${offer.status === 'Payment Completed' || is_fee_paid || applicant.status === 'Fee Paid' ? `
									<div class="desktop-buttons-container mb-3">
										<button class="btn btn-success btn-block mb-2 font-weight-bold" onclick="cur_page.handle_download_receipt()">
											<i class="fa fa-file-text-o mr-2"></i> ${__('Download Receipt')}
										</button>
									</div>
									` : ''}
									<div class="mobile-action-container">
										<div class="card shadow-sm border-0">
											<div class="card-body p-3">
												${offer.status === 'Issued' ? `
												<button class="btn btn-primary btn-block mb-2 font-weight-bold" onclick="cur_page.handle_accept()">
													<i class="fa fa-check mr-2"></i> ${__('Accept Admission Offer')}
												</button>
												<button class="btn btn-danger btn-block mb-2 font-weight-bold" onclick="cur_page.handle_reject()">
													<i class="fa fa-times mr-2"></i> ${__('Reject Admission Offer')}
												</button>
												` : (offer.status === 'Accepted' && !is_fee_paid && online_payment_enabled) ? `
												<button class="btn btn-primary btn-block mb-2 font-weight-bold" onclick="cur_page.handle_pay_fee()">
													<i class="fa fa-credit-card mr-2"></i> ${__('Pay Fee')}
												</button>
												` : ''}
												<button class="btn btn-outline-primary btn-block font-weight-bold" onclick="cur_page.handle_download()">
													<i class="fa fa-cloud-download mr-2"></i> ${__('Download Letter (PDF)')}
												</button>
											</div>
										</div>
									</div>


						<div class="card mb-4 shadow-sm border-0">
							<div class="card-body">
								<h6 class="text-muted text-uppercase small font-weight-bold mb-3">${__('Offer Status')}</h6>
								<div class="d-flex align-items-center">
									<div class="status-indicator ${offer.status.toLowerCase().replace(/ /g, '-')} mr-3"></div>
									<h4 class="mb-0 font-weight-bold">${offer.status}</h4>
								</div>
							</div>
						</div>

						<div class="card mb-4 shadow-sm border-0">
							<div class="card-body">
								<h6 class="text-muted text-uppercase small font-weight-bold mb-3">${__('Summary')}</h6>
								<div class="summary-item mb-2">
									<span class="text-muted text-small">${__('Programme')}:</span>
									<div class="font-weight-bold text-primary">${offer.program}</div>
								</div>
								<div class="summary-item mb-2">
									<span class="text-muted text-small">${__('Campus')}:</span>
									<div class="font-weight-bold">${offer.campus}</div>
								</div>
								<div class="summary-item mb-2">
                                    <span class="text-muted text-small">${__('Payable Amount')}:</span>
                                    <div class="h4 font-weight-bold d-flex align-items-center justify-content-between">
										<span>${format_currency(offer.payable_amount, currency)}</span>
										${is_fee_paid || offer.status === 'Payment Completed' ? `<span class="badge badge-pill badge-success small ml-2" style="font-size: 0.7rem;"><i class="fa fa-check mr-1"></i> ${__('Paid')}</span>` : ''}
									</div>
                                </div>
							</div>
						</div>

                        ${offer.payment_deadline && (offer.status === 'Issued' || offer.status === 'Accepted') ? `
                        <div class="card mb-4 shadow-sm border-0" style="background: linear-gradient(135deg, #FF9900 0%, #FF2E2E 100%); color: #fff;">
                            <div class="card-body">
                                <h6 class="text-uppercase small font-weight-bold mb-3" style="color: rgba(255,255,255,0.6);">${__('Offer Expiry Timer')}</h6>
                                <div id="offer-expiry-timer" class="h3 font-weight-bold mb-2">--:--:--</div>
                                <div class="small" style="color: rgba(255,255,255,0.7);">
                                    <i class="fa fa-calendar-o mr-1"></i> ${__('Deadline')}: ${frappe.datetime.str_to_user(offer.payment_deadline)}
                                </div>
                            </div>
                        </div>
                        ` : ''}

						${offer.status !== 'Payment Completed' && offer.status !== 'Accepted' && offer.status !== 'Issued' ? `
						<div class="card mb-4 shadow-sm border-0 bg-light-warning">
							<div class="card-body">
								<h6 class="text-warning text-uppercase small font-weight-bold mb-3">${__('Important Deadline')}</h6>
								<div class="h5 mb-1 text-danger font-weight-bold d-flex align-items-center justify-content-between">
									<span>${frappe.datetime.str_to_user(offer.payment_deadline)}</span>
									${(function () {
					if (!offer.payment_deadline) return '';
					const diff = frappe.datetime.get_day_diff(offer.payment_deadline, frappe.datetime.now_date());
					if (diff > 0) {
						return `<span class="badge badge-pill badge-danger animated pulse infinite" style="font-size: 0.7rem; padding: 5px 10px;">${diff} ${__('Days Left')}</span>`;
					} else if (diff === 0) {
						return `<span class="badge badge-pill badge-danger" style="font-size: 0.7rem; padding: 5px 10px;">${__('Expires Today')}</span>`;
					} else {
						return `<span class="badge badge-pill badge-secondary" style="font-size: 0.7rem; padding: 5px 10px;">${__('Expired')}</span>`;
					}
				})()}
								</div>
								<p class="text-muted small mb-0">${__('Decision and payment must be completed by this date.')}</p>
							</div>
						</div>
						` : ''}


                        <div class="card shadow-sm border-0">
                            <div class="card-body p-0">
                                <h6 class="px-4 pt-4 text-muted text-uppercase small font-weight-bold mb-2">${__('Fee Details')}</h6>
                                <table class="table table-hover mb-0">
                                    <tbody>
                                        ${fee_breakdown.map(f => `
                                            <tr>
                                                <td class="pl-4 py-2 border-0">${f.component}</td>
                                                <td class="pr-4 py-2 text-right border-0 font-weight-bold text-muted">${format_currency(f.amount, currency)}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                    <tfoot>
                                        <tr class="bg-light">
                                            <th class="pl-4 py-3 border-0">${__('Total')}</th>
                                            <th class="pr-4 py-3 text-right border-0 h5 mb-0 font-weight-bold text-dark">${format_currency(offer.payable_amount, currency)}</th>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        </div>
					</div>

					<!-- Letter Preview -->
					<div class="col-md-8">
						<div class="card shadow-lg border-0 offer-preview-card">
							<div class="card-header bg-white border-0 d-flex justify-content-between align-items-center pt-4 px-4 pb-0">
								<div>
									<h5 class="mb-0 font-weight-bold">${__('Offer Letter Preview')}</h5>
									<span class="text-muted small">${__('Digitally Verified Document')}</span>
								</div>
							</div>
							<div class="card-body p-4 preview-scroll-area">
								<div class="letter-content-container p-5 border rounded bg-light">
									${rendered_content || `<div class="text-center text-muted p-5">${__('Preview not available. Please download the PDF.')}</div>`}
								</div>
							</div>
							<div class="card-footer bg-white border-0 px-4 pb-4">
								<div class="d-flex align-items-start p-3 rounded" style="background: #f0f7ff; border: 1px solid #cce5ff;">
									<div class="text-primary mr-3 mt-1">
										<i class="fa fa-info-circle fa-lg"></i>
									</div>
									<div>
										<h6 class="mb-1 font-weight-bold text-dark">${__('Important Note')}</h6>
										<p class="small mb-0 text-muted">
											${__('This offer letter is a legally binding document once accepted. Please ensure you have reviewed all the terms, fee structures, and deadlines before proceeding with the acceptance.')}
										</p>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		`;

		this.wrapper.find('.layout-main-section').html(html);
		if (offer.payment_deadline && (offer.status === 'Issued' || offer.status === 'Accepted')) {
			this.start_timer(offer.payment_deadline);
		}
	}

	start_timer(deadline_str) {
		if (!deadline_str) return;

		const timer_el = this.wrapper.find('#offer-expiry-timer');
		if (!timer_el.length) return;

		if (this.timer_interval) clearInterval(this.timer_interval);

		// Adjust to end of day
		let deadline_val = deadline_str;
		if (deadline_str.length === 10) {
			deadline_val += " 23:59:59";
		}

		const deadline = new Date(deadline_val).getTime();

		const update = () => {
			const now = new Date().getTime();
			const distance = deadline - now;

			if (distance < 0) {
				if (this.timer_interval) clearInterval(this.timer_interval);
				timer_el.text(__('EXPIRED')).css('color', '#feb2b2');
				return;
			}

			const hours = Math.floor(distance / (1000 * 60 * 60));
			const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
			const seconds = Math.floor((distance % (1000 * 60)) / 1000);

			const display =
				(hours < 10 ? "0" + hours : hours) + " : " +
				(minutes < 10 ? "0" + minutes : minutes) + " : " +
				(seconds < 10 ? "0" + seconds : seconds) + " more";

			timer_el.html(display);
		};

		this.timer_interval = setInterval(update, 1000);
		update();
	}

	render_error(message) {
		this.wrapper.find('.layout-main-section').html(`
			<div class="container-fluid py-5">
				<div class="row justify-content-center">
					<div class="col-md-6 text-center">
						<div class="mb-5">
							<div class="display-1 text-light mb-4">
								<i class="fa fa-envelope-o"></i>
							</div>
							<h3 class="font-weight-bold text-dark">${__('No Active Offer Found')}</h3>
							<p class="text-muted lead pb-4 border-bottom">
								${message || __("We couldn't locate an active admission offer for your account at this moment.")}
							</p>
						</div>

						<div class="row text-left mb-5">
							<div class="col-sm-6 mb-4">
								<div class="d-flex align-items-center">
									<div class="icon-box bg-white shadow-sm rounded p-3 mr-3 text-primary">
										<i class="fa fa-list-ul fa-lg"></i>
									</div>
									<div>
										<h6 class="mb-0 font-weight-bold">${__('View All Offers')}</h6>
										<a href="#offer-letter-list" class="small text-primary">${__('Visit Offer List')}</a>
									</div>
								</div>
							</div>
							<div class="col-sm-6 mb-4">
								<div class="d-flex align-items-center">
									<div class="icon-box bg-white shadow-sm rounded p-3 mr-3 text-primary">
										<i class="fa fa-support fa-lg"></i>
									</div>
									<div>
										<h6 class="mb-0 font-weight-bold">${__('Admissions Help')}</h6>
										<a href="mailto:admissions@university.edu" class="small text-primary">admissions@university.edu</a>
									</div>
								</div>
							</div>
						</div>

						<div class="bg-light p-4 rounded text-muted small text-left border">
							<h6 class="font-weight-bold text-dark mb-2">${__('Why am I seeing this?')}</h6>
							<ul class="pl-3 mb-0">
								<li>${__('Your application might still be under review by the admissions committee.')}</li>
								<li>${__('The offer may have expired or been withdrawn due to missed deadlines.')}</li>
								<li>${__('There might be a delay in processing your recent acceptance.')}</li>
							</ul>
						</div>

						<div class="mt-5">
							<button class="btn btn-primary px-4 shadow-sm" onclick="location.reload()">
								<i class="fa fa-refresh mr-2"></i> ${__('Refresh Dashboard')}
							</button>
						</div>
					</div>
				</div>
			</div>
		`);
	}

	handle_download() {
		const offer = this.data.offer;
		let file_url = offer.offer_letter_pdf;

		if (!file_url) {
			// Fallback: Generate PDF on the fly via standard Frappe API
			file_url = `/api/method/frappe.utils.print_format.download_pdf?doctype=Offer%20Letter&name=${encodeURIComponent(offer.name)}&format=Offer%20Letter&no_letterhead=0`;
		}

		if (file_url) {
			const full_url = frappe.urllib.get_full_url(file_url);
			// Navigate to the path directly in a new tab
			window.open(full_url, '_blank');
		} else {
			frappe.msgprint(__('Unable to find or generate the Offer Letter PDF.'));
		}
	}

	handle_download_receipt() {
		const offer = this.data.offer;
		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				doctype: 'Applicant Payment Receipt',
				filters: { offer_letter: offer.name, docstatus: 1 },
				fieldname: 'name'
			},
			callback: function (r) {
				if (r.message && r.message.name) {
					const format = 'Applicant Payment Receipt Format';
					const url = `/api/method/frappe.utils.print_format.download_pdf?doctype=Applicant+Payment+Receipt&name=${encodeURIComponent(r.message.name)}&format=${encodeURIComponent(format)}&no_letterhead=1`;
					window.open(url, '_blank');
				} else {
					frappe.msgprint(__('Payment Receipt not found. It might still be generating, please refresh in a moment.'));
				}
			}
		});
	}


	handle_accept() {
		let me = this;
		frappe.confirm(
			__('Are you sure you want to accept this admission offer? By accepting, you agree to the university\'s terms and conditions and your other offer letters will be rejected.'),
			() => {
				me.show_loader(__('Processing Acceptance...'));
				frappe.call({
					method: 'slcm.api.service.offer_service.accept_offer',
					args: {
						offer_name: me.data.offer.name
					},
					callback: function (r) {
						me.hide_loader();
						if (r.message) {
							frappe.show_alert({
								message: __('Congratulations! You have successfully accepted the admission offer.'),
								indicator: 'green'
							});
							me.fetch_data();
							frappe.call({
								method: 'slcm.api.service.offer_service.reject_applicant_other_offer',
								args: {
									applicant: me.data.offer.applicant,
									reason: 'Applicant accepted another offer ' + me.data.offer.name
								},
								callback: function (r) {
									if (r.message) {
										frappe.show_alert({
											message: __('Your other offer letters have been rejected.'),
											indicator: 'green'
										});
										me.fetch_data();
									}
								}
							});
						}
					}
				});
			}
		);
	}

	handle_reject() {
		let me = this;
		frappe.prompt([
			{
				label: __('Reason for Rejection'),
				fieldname: 'reason',
				fieldtype: 'Small Text',
				reqd: 1
			}
		], (values) => {
			me.show_loader(__('Processing Rejection...'));
			frappe.call({
				method: 'slcm.api.service.offer_service.reject_offer',
				args: {
					offer_name: me.data.offer.name,
					reason: values.reason
				},
				callback: function (r) {
					me.hide_loader();
					if (r.message) {
						frappe.show_alert({
							message: __('You have rejected the admission offer.'),
							indicator: 'orange'
						});
						me.fetch_data();
					}
				}
			});
		}, __('Confirm Rejection'), __('Reject Offer'));
	}

	handle_pay_fee() {
		let me = this;
		const { offer, fee_breakdown, currency, online_payment_enabled } = this.data;

		let fields = [
			{
				fieldname: 'fee_html',
				fieldtype: 'HTML'
			}
		];

		// If online payment is NOT the only option or we want to allow other modes, we keep the select
		// But requirement says "clicking the button show fee brakdown with pay now button as model"
		// This implies a simpler flow for online payment.

		let d = new frappe.ui.Dialog({
			title: __('Admission Fee Payment'),
			fields: fields,
			primary_action_label: __('Pay Now'),
			primary_action(values) {
				console.log("Proceeding with Online Payment (Razorpay Modal)");
				d.hide();
				me.initiate_razorpay_payment(offer.name);
			}
		});

		let fee_html = `
			<div class="fee-receipt-preview mb-4 p-4 border-0 rounded bg-white shadow-sm">
				<div class="text-center mb-4">
					<div class="display-4 font-weight-bold text-dark mb-1">${format_currency(offer.payable_amount, currency)}</div>
					<div class="text-muted small text-uppercase letter-spacing-1">${__('Total Payable Amount')}</div>
				</div>
				
				<div class="border-top pt-3">
					<h6 class="text-muted text-uppercase tiny-bold mb-3">${__('Fee Components')}</h6>
					<table class="table table-sm table-borderless mb-0">
						<tbody>
							${fee_breakdown.map(f => `
								<tr>
									<td class="text-muted">${f.component}</td>
									<td class="text-right font-weight-bold">${format_currency(f.amount, currency)}</td>
								</tr>
							`).join('')}
						</tbody>
					</table>
				</div>
				
				<div class="mt-4 p-3 rounded bg-light border d-flex align-items-center">
					<div class="text-primary mr-3">
						<i class="fa fa-shield fa-2x"></i>
					</div>
					<div class="small text-muted">
						${__('You will be redirected to a secure payment gateway to complete your transaction.')}
					</div>
				</div>
			</div>
		`;


		d.fields_dict.fee_html.$wrapper.html(fee_html);
		d.show();
	}

	initiate_razorpay_payment(offer_name) {
		let me = this;
		me.show_loader(__('Launching Secure Payment Gateway...'));

		frappe.call({
			method: "slcm.api.service.offer_service.create_offer_razorpay_order",
			args: {
				offer_name: offer_name
			},
			callback: function (r) {
				me.hide_loader();
				if (r.message) {
					me.open_razorpay_modal(r.message, offer_name);
				}
			},
			error: function () {
				me.hide_loader();
			}
		});
	}

	open_razorpay_modal(data, offer_name, retry_count = 0) {
		let me = this;
		const options = {
			"key": data.key_id,
			"amount": data.amount,
			"currency": data.currency,
			"name": __("Admission Fee"),
			"description": __("Offer Acceptance Fee Payment"),
			"order_id": data.order_id,
			"handler": function (response) {
				me.verify_razorpay_payment(response, data.order_id, offer_name);
			},
			"prefill": {
				"name": this.data.applicant.candidate_name,
				"email": this.data.applicant.email || ""
			},
			"theme": {
				"color": "#3399cc"
			},
			"modal": {
				"ondismiss": function () {
					console.log("Payment modal closed by user");
					me.log_payment_failure(offer_name, data.order_id, { "message": "User closed the payment modal" });
				}
			}
		};

		if (typeof Razorpay === 'undefined') {
			$.getScript('https://checkout.razorpay.com/v1/checkout.js')
				.done(function () {
					me.hide_loader();
					const rzp = new Razorpay(options);
					rzp.on('payment.failed', function (response) {
						me.log_payment_failure(offer_name, data.order_id, response.error);
					});
					rzp.open();
				})
				.fail(function (jqxhr, settings, exception) {
					me.hide_loader();
					console.error("Razorpay SDK load failed:", exception);

					if (retry_count < 2) {
						frappe.show_alert({
							message: __('Network issue detected. Retrying to connect to payment gateway...'),
							indicator: 'orange'
						});
						setTimeout(() => me.open_razorpay_modal(data, offer_name, retry_count + 1), 2000);
					} else {
						frappe.msgprint({
							title: __('Connection Error'),
							message: __('We are having trouble connecting to the payment gateway (Razorpay). Please check your internet connection and try again.'),
							indicator: 'red'
						});
					}
				});
		} else {
			const rzp = new Razorpay(options);
			rzp.on('payment.failed', function (response) {
				me.log_payment_failure(offer_name, data.order_id, response.error);
			});
			rzp.open();
		}
	}

	log_payment_failure(offer_name, order_id, error_data) {
		frappe.call({
			method: "slcm.api.service.fee_service.log_payment_failure",
			args: {
				offer_name: offer_name,
				order_id: order_id,
				error_data: error_data
			}
		});
	}


	verify_razorpay_payment(response, order_id, offer_name) {
		let me = this;
		me.show_loader(__('Verifying Payment Status. Please wait...'));

		frappe.call({
			method: "slcm.api.service.offer_service.verify_offer_payment",
			args: {
				razorpay_payment_id: response.razorpay_payment_id,
				razorpay_order_id: response.razorpay_order_id,
				razorpay_signature: response.razorpay_signature,
				offer_name: offer_name
			},
			callback: function (r) {
				me.hide_loader();
				if (r.message && r.message.status === 'success') {
					frappe.show_alert({
						message: __('Payment Successful! Congratulations.'),
						indicator: 'green'
					});
					me.fetch_data();
				} else {
					frappe.msgprint({
						title: __('Payment Verification Failed'),
						message: r.message ? r.message.message : __('Verification failed.'),
						indicator: 'red'
					});
				}
			},
			error: function () {
				me.hide_loader();
			}
		});
	}

}
