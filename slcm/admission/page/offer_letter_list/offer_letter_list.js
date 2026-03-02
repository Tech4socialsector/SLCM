frappe.pages['offer-letter-list'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('My Admission Offers'),
		single_column: true
	});

	new OfferLetterList(wrapper);
}

class OfferLetterList {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.current_page = 1;
		this.limit_page_length = 10; // Testing limit
		this.total_count = 0;
		this.init();
	}

	init() {
		this.fetch_data();
	}

	fetch_data() {
		let me = this;
		const limit_start = (this.current_page - 1) * this.limit_page_length;

		frappe.call({
			method: 'slcm.admission.page.offer_letter_list.offer_letter_list.get_offer_list',
			args: {
				limit_start: limit_start,
				limit_page_length: this.limit_page_length
			},
			callback: function (r) {
				if (r.message && !r.message.error) {
					me.total_count = r.message.total_count;
					me.render(r.message);
				} else {
					me.render_error(r.message ? r.message.error : "Unknown Error");
				}
			}
		});
	}

	render(data) {
		let me = this;
		const { offers, applicant_name, is_admin, currency } = data;

		if (!offers || offers.length === 0) {
			this.render_error(__('No admission offers found for your account.'));
			return;
		}

		// --- Render Skeleton/Container ---
		this.wrapper.find('.layout-main-section').html(`
            <div class="list-container p-4">
                <div class="list-header mb-4">
                    <h4>${is_admin ? __('Administrative View') : __('Welcome')} - <span class="text-primary">${applicant_name}</span></h4>
                    <p class="text-muted">${is_admin ? __('Viewing all system offers.') : __('Below are the admission offers issued to you.')}</p>
                </div>

                <div class="offer-list">
                    <div class="row" id="offer-grid"></div>
                </div>

                <!-- Numbered Pagination -->
                <div id="pagination-wrapper" class="d-flex justify-content-center align-items-center mt-5">
                </div>
            </div>
        `);

		// --- Render Offers ---
		const grid = this.wrapper.find('#offer-grid');
		offers.forEach(offer => {
			const status_class = offer.offer_status.toLowerCase().replace(/ /g, '-');
			const card_html = `
                <div class="col-md-6 mb-4">
                    <div class="card offer-card shadow-sm border-0 h-100 pointer" onclick="frappe.set_route('applicant-offer-lett', '${offer.name}')">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-3">
                                <div>
                                    <h5 class="card-title mb-1 text-dark font-weight-bold">${offer.program}</h5>
                                    <span class="text-muted small"><i class="fa fa-map-marker mr-1"></i> ${offer.campus}</span>
                                    ${is_admin ? `<div class="mt-2"><span class="badge badge-info small">${offer.applicant}</span></div>` : ''}
                                </div>
                                <span class="badge status-badge ${status_class} p-2">
                                    ${offer.offer_status}
                                </span>
                            </div>
                            
                            <div class="row mt-4">
                                <div class="col-6">
                                    <div class="text-muted small">${__('Date Issued')}</div>
                                    <div class="font-weight-bold">${frappe.datetime.str_to_user(offer.issued_on)}</div>
                                </div>
                                <div class="col-6 text-right">
                                    <div class="text-muted small">${__('Total Payable')}</div>
                                    <div class="font-weight-bold">${format_currency(offer.payable_amount, currency)}</div>
                                </div>
                            </div>

                            <div class="mt-3 pt-3 border-top">
                                <div class="d-flex align-items-center ${new Date(offer.payment_deadline) < new Date() ? 'text-danger' : 'text-warning'}">
                                    <i class="fa fa-clock-o mr-2"></i>
                                    <span class="small font-weight-bold">
                                        ${__('Deadline')}: ${frappe.datetime.str_to_user(offer.payment_deadline)}
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div class="card-footer bg-white border-0 text-right pb-3">
                            <span class="btn btn-sm btn-outline-primary">${__('View Details')} <i class="fa fa-arrow-right ml-1"></i></span>
                        </div>
                    </div>
                </div>
            `;
			grid.append(card_html);
		});

		this.render_pagination();
	}

	render_pagination() {
		let me = this;
		const total_pages = Math.ceil(this.total_count / this.limit_page_length);
		if (total_pages <= 1) return;

		const container = this.wrapper.find('#pagination-wrapper');
		let html = `
            <nav aria-label="Page navigation">
                <ul class="pagination pagination-sm mb-0">
                    <li class="page-item ${this.current_page === 1 ? 'disabled' : ''}">
                        <a class="page-link" href="#" data-page="${this.current_page - 1}" aria-label="Previous">
                            <span aria-hidden="true">&laquo; ${__('Prev')}</span>
                        </a>
                    </li>
        `;

		for (let i = 1; i <= total_pages; i++) {
			html += `
                <li class="page-item ${this.current_page === i ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>
            `;
		}

		html += `
                    <li class="page-item ${this.current_page === total_pages ? 'disabled' : ''}">
                        <a class="page-link" href="#" data-page="${this.current_page + 1}" aria-label="Next">
                            <span aria-hidden="true">${__('Next')} &raquo;</span>
                        </a>
                    </li>
                </ul>
            </nav>
            <div class="ml-3 text-muted small font-weight-bold">
                ${__('Page {0} of {1}', [this.current_page, total_pages])}
            </div>
        `;

		container.html(html);

		container.find('.page-link').on('click', function (e) {
			e.preventDefault();
			const new_page = $(this).data('page');
			if (new_page && new_page !== me.current_page && new_page >= 1 && new_page <= total_pages) {
				me.current_page = new_page;
				me.fetch_data();
				// Scroll to top of list
				$([document.documentElement, document.body]).animate({
					scrollTop: me.wrapper.offset().top - 100
				}, 400);
			}
		});
	}

	render_error(message) {
		this.wrapper.find('.layout-main-section').html(`
            <div class="text-center p-5 mt-5">
                <div class="mb-4">
                    <i class="fa fa-folder-open-o fa-4x text-light"></i>
                </div>
                <h4 class="text-muted font-weight-bold">${__('No Offers Found')}</h4>
                <p class="text-muted">${message}</p>
            </div>
        `);
	}
}