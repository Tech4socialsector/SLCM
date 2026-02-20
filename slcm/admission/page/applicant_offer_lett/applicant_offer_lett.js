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
		window.cur_page = this;
		this.data = data;
		const { offer, applicant, fee_breakdown, rendered_content, currency } = data;

		if (offer.offer_status === 'Issued') {
			this.page.set_primary_action(__('Accept Admission Offer'), () => me.handle_accept(), 'octicon octicon-check');
		} else {
			this.page.clear_primary_action();
		}
		this.page.set_secondary_action(__('Download Letter (PDF)'), () => me.handle_download(), 'octicon octicon-cloud-download');

		let html = `
			<div class="offer-container">
				<div class="row">
					<!-- Statistics & Actions -->
					<div class="col-md-4">
						<div class="mobile-action-container">
							<div class="card shadow-sm border-0">
								<div class="card-body p-3">
									${offer.offer_status === 'Issued' ? `
									<button class="btn btn-primary btn-block mb-2 font-weight-bold" onclick="cur_page.handle_accept()">
										<i class="fa fa-check mr-2"></i> ${__('Accept Admission Offer')}
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
									<div class="status-indicator ${offer.offer_status.toLowerCase()} mr-3"></div>
									<h4 class="mb-0 font-weight-bold">${offer.offer_status}</h4>
								</div>
							</div>
						</div>

						<div class="card mb-4 shadow-sm border-0">
							<div class="card-body">
								<h6 class="text-muted text-uppercase small font-weight-bold mb-3">${__('Summary')}</h6>
								<div class="summary-item mb-2">
									<span class="text-muted text-small">${__('Program')}:</span>
									<div class="font-weight-bold text-primary">${offer.program}</div>
								</div>
								<div class="summary-item mb-2">
									<span class="text-muted text-small">${__('Campus')}:</span>
									<div class="font-weight-bold">${offer.campus}</div>
								</div>
								<div class="summary-item mb-2">
                                    <span class="text-muted text-small">${__('Payable Amount')}:</span>
                                    <div class="h4 font-weight-bold">${format_currency(offer.payable_amount, currency)}</div>
                                </div>
							</div>
						</div>

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
								<button class="btn btn-sm btn-outline-primary shadow-sm" onclick="window.print()">
									<i class="fa fa-print mr-1"></i> ${__('Print Preview')}
								</button>
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

	handle_accept() {
		let me = this;
		frappe.confirm(
			__('Are you sure you want to accept this admission offer? By accepting, you agree to the university\'s terms and conditions.'),
			() => {
				frappe.dom.freeze(__('Processing Acceptance...'));
				frappe.call({
					method: 'slcm.api.service.offer_service.accept_offer',
					args: {
						offer_name: me.data.offer.name
					},
					callback: function (r) {
						frappe.dom.unfreeze();
						if (r.message) {
							frappe.show_alert({
								message: __('Congratulations! You have successfully accepted the admission offer.'),
								indicator: 'green'
							});
							me.fetch_data();
						}
					}
				});
			}
		);
	}
}
