frappe.pages['seat-matrix-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Advanced Seat Matrix Dashboard'),
		single_column: true
	});

	// Create a simple filter row at the top of the body for guaranteed visibility
	$(wrapper).find('.layout-main-section').html(`
		<div id="filter-area" class="row p-3 mb-4 mx-0" style="background: #fff; border-bottom: 1px solid #d1d8dd; border-radius: 8px; border: 1px solid #ddd;"></div>
		<div id="dashboard-body"></div>
	`);

	// Add Filters
	let cycle_field = page.add_field({
		fieldname: 'admission_cycle',
		label: __('Admission Cycle'),
		fieldtype: 'Link',
		options: 'Admission Cycle',
		change() { refresh_dashboard(page); }
	});
	cycle_field.$wrapper.appendTo('#filter-area').addClass('col-md-4').css('margin-bottom', '0');

	let campus_field = page.add_field({
		fieldname: 'campus',
		label: __('Campus'),
		fieldtype: 'Link',
		options: 'Campus',
		change() { refresh_dashboard(page); }
	});
	campus_field.$wrapper.appendTo('#filter-area').addClass('col-md-4').css('margin-bottom', '0');

	let program_field = page.add_field({
		fieldname: 'program',
		label: __('Programme'),
		fieldtype: 'Link',
		options: 'Programme',
		change() { refresh_dashboard(page); }
	});
	program_field.$wrapper.appendTo('#filter-area').addClass('col-md-4').css('margin-bottom', '0');

	// Initial Refresh
	refresh_dashboard(page);
}

function refresh_dashboard(page) {
	const admission_cycle = page.fields_dict.admission_cycle.get_value();
	const campus = page.fields_dict.campus.get_value();
	const program = page.fields_dict.program.get_value();

	frappe.call({
		method: 'slcm.admission.page.seat_matrix_dashboard.seat_matrix_dashboard.get_seat_matrix_data',
		args: {
			admission_cycle: admission_cycle,
			campus: campus,
			program: program
		},
		callback: function(r) {
			if (r.message) {
				render_dashboard(page, r.message);
			}
		}
	});
}

function render_dashboard(page, data) {
	let overall = data.overall;
	let programs = data.programs;

	let html = `
		<div class="seat-matrix-dashboard container-fluid px-0">
			<!-- Summary Cards -->
			<div class="row mx-0">
				<div class="col-sm-3 pl-0">
					<div class="card bg-light shadow-sm text-center mb-3" style="padding: 15px; border-radius: 8px; border: 1px solid #ddd;">
						<div class="text-muted small uppercase font-weight-bold">${__('Total Intake')}</div>
						<div class="h2 font-weight-bold" style="color: #2c3e50;">${overall.total_seats}</div>
					</div>
				</div>
				<div class="col-sm-3">
					<div class="card bg-success text-white shadow-sm text-center mb-3" style="padding: 15px; border-radius: 8px; border: none;">
						<div class="small uppercase font-weight-bold">${__('Total Allocated')}</div>
						<div class="h2 font-weight-bold">${overall.allocated}</div>
					</div>
				</div>
				<div class="col-sm-3">
					<div class="card bg-warning text-dark shadow-sm text-center mb-3" style="padding: 15px; border-radius: 8px; border: none;">
						<div class="small uppercase font-weight-bold">${__('Total Waitlisted')}</div>
						<div class="h2 font-weight-bold">${overall.waitlisted}</div>
					</div>
				</div>
				<div class="col-sm-3 pr-0">
					<div class="card bg-info text-white shadow-sm text-center mb-3" style="padding: 15px; border-radius: 8px; border: none;">
						<div class="small uppercase font-weight-bold">${__('Total Vacant')}</div>
						<div class="h2 font-weight-bold">${overall.vacant}</div>
					</div>
				</div>
			</div>

			<div class="row mx-0 mt-2">
				<div class="col-sm-12 px-0">
					<div class="card shadow-sm mb-4" style="border-radius: 8px; border: 1px solid #ddd; background: #fff;">
						<div class="card-header bg-white font-weight-bold" style="border-bottom: 1px solid #eee; padding: 15px;">
							${__('Overall Seat Utilization')}
						</div>
						<div class="card-body" style="padding: 20px;">
							<div class="progress" style="height: 25px; border-radius: 12px; background-color: #f5f5f5;">
								<div class="progress-bar progress-bar-striped progress-bar-animated bg-success" role="progressbar" 
									style="width: ${overall.utilization}%" aria-valuenow="${overall.utilization}" aria-valuemin="0" aria-valuemax="100">
									${overall.utilization.toFixed(1)}%
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Detailed Program Matrix -->
			<div class="mt-4 mx-0">
				<h4 class="mb-4 font-weight-bold" style="color: #444;">${__('Program-wise Seat Matrix')}</h4>
				<div class="accordion" id="programMatrix">
					${programs.map((p, i) => render_program_card(p, i)).join('')}
				</div>
			</div>
		</div>

		<style>
			.uppercase { text-transform: uppercase; letter-spacing: 0.5px; }
			.card { border: 1px solid #eee; }
		</style>
	`;

	$('#dashboard-body').html(html);
}

function render_program_card(p, i) {
	let utilization = (p.allocated / p.total_seats * 100) || 0;
	
	// Intuitive progress bar color: Green (success) for full, Blue (info) for moderate, Orange (warning) for low, Red (danger) for empty
	let util_color = 'danger';
	if (utilization >= 90) {
		util_color = 'success';
	} else if (utilization >= 50) {
		util_color = 'info';
	} else if (utilization > 0) {
		util_color = 'warning';
	}

	return `
		<div class="card mb-3 shadow-sm" style="border: 1px solid #ddd; border-radius: 8px; background: #fff; overflow: hidden;">
			<div class="card-header bg-white" id="heading${i}" style="padding: 15px; border-bottom: 1px solid #eee;">
				<div class="row align-items-center">
					<div class="col-md-5">
						<h5 class="mb-0 font-weight-bold" style="color: #34495e;">${p.program}</h5>
					</div>
					<div class="col-md-5">
						<div class="progress" style="height: 10px; margin-top: 5px; background-color: #f5f5f5;">
							<div class="progress-bar bg-${util_color}" style="width: ${utilization}%"></div>
						</div>
						<div class="small text-muted mt-1">
							${p.allocated} / ${p.total_seats} seats filled (${utilization.toFixed(1)}%)
						</div>
					</div>
					<div class="col-md-2 text-right">
						<button class="btn btn-sm btn-link font-weight-bold" type="button" data-toggle="collapse" data-target="#collapse${i}">
							${__('View Details')}
						</button>
					</div>
				</div>
			</div>

			<div id="collapse${i}" class="collapse" aria-labelledby="heading${i}" data-parent="#programMatrix">
				<div class="card-body p-0">
					<table class="table table-hover mb-0">
						<thead class="bg-light">
							<tr>
								<th style="padding-left: 20px; border-top: none;">${__('Category')}</th>
								<th class="text-center" style="border-top: none;">${__('Quota')}</th>
								<th class="text-center" style="border-top: none;">${__('Filled')}</th>
								<th class="text-center" style="border-top: none;">${__('Waitlist')}</th>
								<th class="text-center" style="border-top: none;">${__('Vacant')}</th>
								<th class="text-right" style="padding-right: 20px; border-top: none;">${__('Utilization')}</th>
							</tr>
						</thead>
						<tbody>
							${p.categories.map(c => {
								let cat_util = parseFloat(c.utilization);
								let cat_util_val = isNaN(cat_util) ? 0 : cat_util;
								let badge_class = 'secondary';
								if (cat_util_val >= 90) {
									badge_class = 'success';
								} else if (cat_util_val >= 50) {
									badge_class = 'info';
								} else if (cat_util_val > 0) {
									badge_class = 'warning';
								} else {
									badge_class = 'danger';
								}

								return `
									<tr>
										<td style="padding-left: 20px;">${c.category}</td>
										<td class="text-center">${c.total}</td>
										<td class="text-center font-weight-bold text-success">${c.allocated}</td>
										<td class="text-center text-warning">${c.waitlisted}</td>
										<td class="text-center text-info">${c.vacant}</td>
										<td class="text-right" style="padding-right: 20px;">
											<span class="badge badge-pill badge-${badge_class}">
												${cat_util_val.toFixed(1)}%
											</span>
										</td>
									</tr>
								`;
							}).join('')}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	`;
}
