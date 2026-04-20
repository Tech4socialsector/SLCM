frappe.pages['pace-admin-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('PACE Admissions Dashboard'),
		single_column: true
	});

	// --- 1. Inject Material Symbols and Custom Styles ---
	$('<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">').appendTo('head');
	$(`<style>
		.dashboard-grid { 
			display: grid; 
			grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); 
			gap: 20px; 
			margin-bottom: 24px; 
			padding: 0 15px;
			max-width: 1600px;
			margin-left: auto;
			margin-right: auto;
		}
		.stat-card { 
			background: #fff; 
			border: 1px solid #e2e8f0; 
			border-radius: 12px; 
			padding: 20px; 
			display: flex; 
			align-items: center; 
			gap: 16px; 
			transition: all 0.2s ease; 
			cursor: pointer; 
		}
		.stat-card:hover { 
			transform: translateY(-4px); 
			box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
			background: #fafafa;
		}
		
		.icon-box { 
			width: 52px; 
			height: 52px; 
			border-radius: 12px; 
			display: flex; 
			align-items: center; 
			justify-content: center; 
			flex-shrink: 0; 
		}
		.icon-box span { font-size: 26px !important; }

		.icon-blue   { background: #eff6ff; color: #2563eb; }
		.icon-green  { background: #f0fdf4; color: #16a34a; }
		.icon-orange { background: #fff7ed; color: #ea580c; }
		.icon-red    { background: #fef2f2; color: #dc2626; }
		.icon-purple { background: #faf5ff; color: #9333ea; }
		.icon-teal   { background: #f0fdfa; color: #0d9488; }
		.icon-slate  { background: #f8fafc; color: #475569; }

		.stat-info { 
			display: flex; 
			flex-direction: column; 
			align-items: flex-start; 
			text-align: left;
			overflow: hidden; 
		}
		.stat-label { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px; }
		.stat-value { font-size: 20px; font-weight: 800; color: #0f172a; line-height: 1.1; word-break: break-word; }
		
		.section-title-container { 
			border-left: 4px solid #2563eb; 
			padding-left: 15px; 
			margin: 40px auto 24px auto; 
			max-width: 1600px;
		}
		.section-title { font-size: 20px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
		.section-subtitle { font-size: 14px; color: #64748b; }

		.chart-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; height: 100%; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
		.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
		.chart-title { font-size: 15px; font-weight: 700; color: #334155; margin: 0; }
		
		/* Multi-color bars for single-dataset charts (Safe targeting for Bar charts ONLY) */
		#revenue_program_chart .dataset-0 .bar:nth-child(1), #program_chart .dataset-0 .bar:nth-child(1),
		#revenue_program_chart rect.bar:nth-of-type(1), #program_chart rect.bar:nth-of-type(1) { fill: #3b82f6 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(2), #program_chart .dataset-0 .bar:nth-child(2),
		#revenue_program_chart rect.bar:nth-of-type(2), #program_chart rect.bar:nth-of-type(2) { fill: #ef4444 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(3), #program_chart .dataset-0 .bar:nth-child(3),
		#revenue_program_chart rect.bar:nth-of-type(3), #program_chart rect.bar:nth-of-type(3) { fill: #10b981 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(4), #program_chart .dataset-0 .bar:nth-child(4),
		#revenue_program_chart rect.bar:nth-of-type(4), #program_chart rect.bar:nth-of-type(4) { fill: #f59e0b !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(5), #program_chart .dataset-0 .bar:nth-child(5),
		#revenue_program_chart rect.bar:nth-of-type(5), #program_chart rect.bar:nth-of-type(5) { fill: #6366f1 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(6), #program_chart .dataset-0 .bar:nth-child(6),
		#revenue_program_chart rect.bar:nth-of-type(6), #program_chart rect.bar:nth-of-type(6) { fill: #8b5cf6 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(7), #program_chart .dataset-0 .bar:nth-child(7),
		#revenue_program_chart rect.bar:nth-of-type(7), #program_chart rect.bar:nth-of-type(7) { fill: #ec4899 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(8), #program_chart .dataset-0 .bar:nth-child(8),
		#revenue_program_chart rect.bar:nth-of-type(8), #program_chart rect.bar:nth-of-type(8) { fill: #06b6d4 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(9), #program_chart .dataset-0 .bar:nth-child(9),
		#revenue_program_chart rect.bar:nth-of-type(9), #program_chart rect.bar:nth-of-type(9) { fill: #f97316 !important; opacity: 1 !important; }
		
		#revenue_program_chart .dataset-0 .bar:nth-child(10), #program_chart .dataset-0 .bar:nth-child(10),
		#revenue_program_chart rect.bar:nth-of-type(10), #program_chart rect.bar:nth-of-type(10) { fill: #84cc16 !important; opacity: 1 !important; }

		.recent-apps-table th { background: #f8fafc !important; color: #475569 !important; font-weight: 700 !important; text-transform: uppercase !important; font-size: 11px !important; letter-spacing: 0.05em !important; border: none !important; padding: 12px 15px !important; }
		.recent-apps-table td { vertical-align: middle !important; font-size: 14px; color: #1e293b; padding: 12px 15px !important; }
		.status-badge { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; display: inline-block; }
		
		.priority-badge { padding: 4px 10px; border-radius: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
		.priority-high { background: #fee2e2; color: #dc2626; }
		.priority-medium { background: #fef3c7; color: #d97706; }
		.priority-low { background: #f1f5f9; color: #64748b; }

		.clickable-id { color: #2563eb; font-weight: 700; cursor: pointer; }
		.clickable-id:hover { text-decoration: underline; color: #1d4ed8; }

		.filter-bar { 
			background: #fff; 
			border: 1px solid #e2e8f0; 
			border-radius: 12px; 
			padding: 20px; 
			margin: 20px auto 30px auto; 
			max-width: 1600px; 
			display: flex; 
			flex-wrap: wrap; 
			gap: 20px; 
			align-items: flex-end;
			box-shadow: 0 1px 2px rgba(0,0,0,0.05);
		}
		.fee-summary-card {
			background: #fff;
			border: 1px solid #e2e8f0;
			border-radius: 12px;
			padding: 30px 20px;
			display: flex;
			justify-content: space-around;
			align-items: center;
			margin-bottom: 24px;
			box-shadow: 0 1px 3px rgba(0,0,0,0.05);
		}
		.fee-metric { 
			flex: 1; 
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			border-right: 1px solid #f1f5f9;
		}
		.fee-metric:last-child { border-right: none; }
		.metric-label { font-size: 13px; font-weight: 600; color: #64748b; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
		.metric-value { font-size: 26px; font-weight: 800; display: block; line-height: 1; }
		.blue-text { color: #2563eb; }
		.dark-text { color: #0f172a; }
		.green-text { color: #16a34a; }
		.red-text { color: #dc2626; }
	</style>`).appendTo('head');

	// --- 2. Filters ---
	let filters_container = $(`<div class="filter-bar"></div>`).appendTo(page.body);
	
	function add_filter(label, fieldname, fieldtype, options) {
		let field = page.add_field({
			label: label,
			fieldname: fieldname,
			fieldtype: fieldtype,
			options: options,
			change() { refresh_dashboard(); }
		});
		field.$wrapper.appendTo(filters_container).css({'min-width': '180px', 'margin': '0'});
		return field;
	}

	add_filter(__('Academic Year'), 'academic_year', 'Link', 'Academic Year');
	add_filter(__('Programme'), 'programme', 'Link', 'PACE Programme');
	add_filter(__('From Date'), 'from_date', 'Date');
	add_filter(__('To Date'), 'to_date', 'Date');

	$(`<button class="btn btn-default btn-sm" style="height: 36px; margin-left: auto;">
		<span class="material-symbols-outlined" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">refresh</span>
		${__('Reset')}
	</button>`).appendTo(filters_container).on('click', () => {
		page.fields_dict.academic_year.set_value('');
		page.fields_dict.programme.set_value('');
		page.fields_dict.from_date.set_value('');
		page.fields_dict.to_date.set_value('');
		refresh_dashboard();
	});

	// --- 3. Layout Structure ---
	
	// KPI Section
	$(`<div class="section-title-container">
		<div class="section-title">${__('Admissions & Revenue Overview')}</div>
		<div class="section-subtitle">${__('High-level performance metrics and financial summary')}</div>
	</div>`).appendTo(page.body);
	
	let kpi_grid = $(`<div class="kpi-sections-container"></div>`).appendTo(page.body);

	// Analytical Section
	$(`<div class="section-title-container">
		<div class="section-title">${__('Financial & Operational Trends')}</div>
		<div class="section-subtitle">${__('Real-time fee status and application growth analytics')}</div>
	</div>`).appendTo(page.body);

	let layout_row_1 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-12">
			<div id="fee_summary_container"></div>
		</div>
	</div>`).appendTo(page.body);

	let layout_row_2 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-6"><div class="chart-card"><div class="chart-header"><h6 class="chart-title">${__('Daily Application Trend')}</h6></div><div id="trend_chart"></div></div></div>
		<div class="col-md-6"><div class="chart-card"><div class="chart-header"><h6 class="chart-title">${__('Revenue by Program')}</h6></div><div id="revenue_program_chart"></div></div></div>
	</div>`).appendTo(page.body);

	let layout_row_3 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<!-- Weekly Revenue Trend -->
		<div class="col-md-6">
			<div class="chart-card">
				<div class="chart-header">
					<h6 class="chart-title">${__('Weekly Revenue Trend')}</h6>
				</div>
				<div id="revenue_trend_chart"></div>
			</div>
		</div>
		
		<!-- Program Popularity -->
		<div class="col-md-6">
			<div class="chart-card">
				<div class="chart-header">
					<h6 class="chart-title">${__('Applications by Programme')}</h6>
				</div>
				<div id="program_chart"></div>
			</div>
		</div>
	</div>`).appendTo(page.body);

	// Pending Work Section
	$(`<div class="section-title-container">
		<div class="section-title">${__('Section 5 — Pending Work')}</div>
		<div class="section-subtitle">${__('Actionable items requiring attention (Top 5 Priority)')}</div>
	</div>`).appendTo(page.body);

	let pending_section = $(`<div class="card shadow-sm p-4 mt-4 mx-3 mb-5" style="border-radius: 12px; border: 1px solid #e2e8f0;">
		<div class="d-flex justify-content-between align-items-center mb-4">
			<h5 class="mb-0" style="font-size: 15px; font-weight: 700; color: #374151;">${__('High Priority Tasks')}</h5>
			<button class="btn btn-xs btn-default" onclick="frappe.set_route('List', 'PACE Document Verification', {status: ['in', ['Submitted', 'Under Verification', 'Returned for Correction']]})" style="font-weight: 600;">${__('View All')}</button>
		</div>
		<div id="pending_work_container" style="overflow-x: auto;"></div>
	</div>`).appendTo(page.body);

	// Recent Activity (Moved to bottom)
	$(`<div class="section-title-container">
		<div class="section-title">${__('Recent Activity')}</div>
		<div class="section-subtitle">${__('Latest applications received across all programs')}</div>
	</div>`).appendTo(page.body);

	let table_section = $(`<div class="card shadow-sm p-4 mt-4 mx-3 mb-5" style="border-radius: 12px; border: 1px solid #e2e8f0;">
		<div class="d-flex justify-content-between align-items-center mb-4">
			<h5 class="mb-0" style="font-size: 15px; font-weight: 700; color: #374151;">${__('Recent PACE Applications')}</h5>
			<button class="btn btn-xs btn-default" onclick="frappe.set_route('List', 'PACE Application')" style="font-weight: 600;">${__('View All')}</button>
		</div>
		<div id="recent_apps_container" style="overflow-x: auto;"></div>
	</div>`).appendTo(page.body);

	// --- 4. Logic ---

	function refresh_dashboard() {
		let filters = {
			academic_year: page.fields_dict.academic_year.get_value(),
			programme: page.fields_dict.programme.get_value(),
			from_date: page.fields_dict.from_date.get_value(),
			to_date: page.fields_dict.to_date.get_value()
		};

		frappe.call({
			method: 'slcm.pace.page.pace_admin_dashboard.pace_admin_dashboard.get_dashboard_data',
			args: { filters: filters },
			callback: function(r) {
				if (r.message) {
					render_kpis(r.message.kpis);
					render_fee_summary(r.message.fee_summary);
					render_charts(r.message.charts);
					render_table(r.message.recent_applications);
					render_pending_work(r.message.pending_work);
				}
			}
		});
	}

	const open_list_view = (type) => {
		let filters = {};
		let academic_year = page.fields_dict.academic_year.get_value();
		let programme = page.fields_dict.programme.get_value();
		let from_date = page.fields_dict.from_date.get_value();
		let to_date = page.fields_dict.to_date.get_value();

		if (academic_year) filters.academic_year = academic_year;
		if (programme) filters.programme = programme;
		if (from_date && to_date) {
			filters.creation = ['between', [from_date, to_date]];
		} else if (from_date) {
			filters.creation = ['>=', from_date];
		} else if (to_date) {
			filters.creation = ['<=', to_date];
		}

		let doctype = 'PACE Application';
		
		switch (type) {
			case 'total_applications':
				filters.status = ['!=', 'Draft'];
				break;
			case 'unassigned':
				filters.status = 'Submitted';
				filters.assigned_verifier = ['is', 'not set'];
				break;
			case 'verified_apps':
				filters.status = 'Verified';
				break;
			case 'total_enrolled':
				filters.status = ['in', ['Admitted', 'Enrolled']];
				break;
			case 'revenue':
				doctype = 'PACE Receipt';
				// Copy filters to receipt if applicable, though receipts don't have all the same fields
				filters = {}; 
				if (academic_year) filters.academic_year = academic_year;
				break;
			case 'app_revenue':
				doctype = 'PACE Receipt';
				filters = { fee_type: 'Application Fee' };
				if (academic_year) filters.academic_year = academic_year;
				break;
			case 'adm_revenue':
				doctype = 'PACE Receipt';
				filters = { fee_type: 'Admission Fee' };
				if (academic_year) filters.academic_year = academic_year;
				break;
			case 'returned':
				filters.status = 'Returned for Correction';
				break;
			case 'pending':
				filters.status = ['in', ['Submitted', 'Under Verification']];
				break;
			case 'rejected':
				filters.status = 'Rejected';
				break;
			case 'draft':
				filters.status = 'Draft';
				break;
		}

		frappe.set_route('List', doctype, filters);
	};

	function render_kpis(kpis) {
		kpi_grid.empty();
		
		const render_line = (items) => {
			let grid = $(`<div class="dashboard-grid" style="margin-bottom: 20px;"></div>`).appendTo(kpi_grid);
			items.forEach(item => {
				let $card = $(`<div class="stat-card">
					<div class="icon-box ${item.cls}">
						<span class="material-symbols-outlined">${item.icon}</span>
					</div>
					<div class="stat-info">
						<div class="stat-label">${item.label}</div>
						<div class="stat-value">${item.value}</div>
					</div>
				</div>`).appendTo(grid);
				$card.on('click', () => open_list_view(item.type));
			});
		};

		// Line 1
		render_line([
			{ label: __('Draft '), value: kpis.draft_apps, icon: 'edit_note', cls: 'icon-purple', type: 'draft' },
			{ label: __('Submitted'), value: kpis.total_applications, icon: 'description', cls: 'icon-purple', type: 'total_applications' },
			{ label: __('Verified'), value: kpis.verified_apps, icon: 'verified', cls: 'icon-teal', type: 'verified_apps' },
			{ label: __('Pending Verification'), value: kpis.pending, icon: 'history', cls: 'icon-orange', type: 'pending' },
		]);

		// Line 2
		render_line([
			{ label: __('Unassigned Documents'), value: kpis.unassigned, icon: 'assignment_ind', cls: 'icon-orange', type: 'unassigned' },
			{ label: __('Returned For Correction'), value: kpis.returned, icon: 'replay', cls: 'icon-orange', type: 'returned' },
			{ label: __('Enrolled Students'), value: kpis.total_enrolled, icon: 'school', cls: 'icon-green', type: 'total_enrolled' },
			{ label: __('Rejected'), value: kpis.rejected, icon: 'cancel', cls: 'icon-red', type: 'rejected' }
		]);

		// Line 3
		render_line([
			{ label: __('Application Revenue'), value: format_currency(kpis.application_revenue), icon: 'request_quote', cls: 'icon-green', type: 'app_revenue' },
			{ label: __('Admission Revenue'), value: format_currency(kpis.admission_revenue), icon: 'account_balance_wallet', cls: 'icon-green', type: 'adm_revenue' },
			{ label: __('Total Revenue'), value: format_currency(kpis.total_revenue), icon: 'payments', cls: 'icon-green', type: 'revenue' },
		]);
	}

	function render_fee_summary(data) {
		const container = $('#fee_summary_container');
		container.empty();
		
		const html = `
			<div class="fee-summary-card">
				<div class="fee-metric">
					<div class="metric-label">${__('Total Assignments')}</div>
					<span class="metric-value blue-text">${data.total_assignments}</span>
				</div>
				<div class="fee-metric">
					<div class="metric-label">${__('Total Amount Assigned')}</div>
					<span class="metric-value dark-text">${format_currency(data.total_assigned)}</span>
				</div>
				<div class="fee-metric">
					<div class="metric-label">${__('Total Amount Paid')}</div>
					<span class="metric-value green-text">${format_currency(data.total_paid)}</span>
				</div>
				<div class="fee-metric">
					<div class="metric-label">${__('Pending Amount')}</div>
					<span class="metric-value red-text">${format_currency(data.pending_amount)}</span>
				</div>
			</div>
		`;
		container.html(html);
	}

	function render_charts(charts) {
		// 1. Daily Trend
		new frappe.Chart("#trend_chart", {
			data: {
				labels: charts.trend.map(d => d.date),
				datasets: [{ name: __("Apps"), values: charts.trend.map(d => d.value) }]
			},
			type: 'line',
			height: 300,
			colors: ['#9333ea'],
			lineOptions: { regionFill: 1 }
		});

		// 3. Revenue by Program (Horizontal Bars with unique colors via CSS)
		let rev_chart_height = Math.max(300, charts.revenue_program.length * 45);
		new frappe.Chart("#revenue_program_chart", {
			data: {
				labels: charts.revenue_program.map(d => d.label),
				datasets: [{ values: charts.revenue_program.map(d => d.value) }]
			},
			type: 'bar',
			height: rev_chart_height,
			colors: ['#3b82f6'],
			axisOptions: { xIsSeries: 1 }
		});

		// 4. Weekly Revenue Trend (Area Chart)
		new frappe.Chart("#revenue_trend_chart", {
			data: {
				labels: charts.revenue_trend.map(d => d.label),
				datasets: [{ name: __("Revenue"), values: charts.revenue_trend.map(d => d.value) }]
			},
			type: 'line',
			height: 350,
			colors: ['#3b82f6'],
			lineOptions: { regionFill: 1, splines: 1 }
		});


		// 6. Applications by Programme (Curved Area with Smart Fallback)


		let prog_is_bar = charts.program_dist.length === 1 || charts.program_dist.length > 10;
		
		new frappe.Chart("#program_chart", {
			data: {
				labels: charts.program_dist.map(d => d.label),
				datasets: [{ name: __("Apps"), values: charts.program_dist.map(d => d.value) }]
			},
			type: prog_is_bar ? 'bar' : 'line',
			height: 350,
			colors: ['#3b82f6'],
			lineOptions: { regionFill: 1, splines: 1 },
			axisOptions: { xIsSeries: prog_is_bar ? 1 : 0 }
		});
	}

	function render_pending_work(pending) {
		// Limit to top 5 for the dashboard summary
		let visible_pending = pending.slice(0, 5);
		
		let html = `<table class="table recent-apps-table">
			<thead>
				<tr>
					<th>${__('Application ID')}</th>
					<th>${__('Applicant Name')}</th>
					<th>${__('Program')}</th>
					<th>${__('Status')}</th>
					<th>${__('Assigned To')}</th>
					<th class="text-center">${__('Days Pending')}</th>
					<th>${__('Last Action')}</th>
					<th class="text-right">${__('Action')}</th>
				</tr>
			</thead>
			<tbody>`;

		visible_pending.forEach(item => {
			let status_color = get_status_color(item.status);
			let days_cls = item.days_pending >= 4 ? 'days-pending-red' : (item.days_pending >= 2 ? 'days-pending-amber' : '');

			let route_doctype = item.verification_name ? 'PACE Document Verification' : 'PACE Application';
			let route_name = item.verification_name || item.name;

			html += `<tr>
				<td><span class="clickable-id" onclick="frappe.set_route('Form', 'PACE Application', '${item.name}')">${item.name}</span></td>
				<td style="font-weight: 600;">${item.applicant_name}</td>
				<td class="text-muted small">${item.programme}</td>
				<td><span class="status-badge" style="background: ${status_color.bg}; color: ${status_color.text};">${item.status}</span></td>
				<td class="text-muted">${item.assigned_to || '--'}</td>
				<td class="text-center ${days_cls}">${item.days_pending}</td>
				<td class="text-muted small">${frappe.datetime.global_date_format(item.last_action)}</td>
				<td class="text-right">
					<button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', '${route_doctype}', '${route_name}')">
						${__('Open')}
					</button>
				</td>
			</tr>`;
		});

		if (visible_pending.length === 0) {
			html += `<tr><td colspan="8" class="text-center p-4 text-muted">${__('No pending work found')}</td></tr>`;
		}
		html += `</tbody></table>`;
		$('#pending_work_container').html(html);
	}

	function render_table(apps) {
		let html = `<table class="table recent-apps-table">
			<thead>
				<tr>
					<th>${__('Application ID')}</th>
					<th>${__('Applicant')}</th>
					<th>${__('Programme')}</th>
					<th>${__('Status')}</th>
					<th>${__('Date')}</th>
				</tr>
			</thead>
			<tbody>`;

		apps.forEach(app => {
			let status_color = get_status_color(app.status);
			html += `<tr>
				<td><span class="clickable-id" onclick="frappe.set_route('Form', 'PACE Application', '${app.name}')">${app.name}</span></td>
				<td style="font-weight: 600;">${app.applicant_name}</td>
				<td class="text-muted small">${app.programme}</td>
				<td><span class="status-badge" style="background: ${status_color.bg}; color: ${status_color.text};">${app.status}</span></td>
				<td class="text-muted">${frappe.datetime.global_date_format(app.creation)}</td>
			</tr>`;
		});

		if (apps.length === 0) {
			html += `<tr><td colspan="5" class="text-center p-4 text-muted">${__('No recent applications found')}</td></tr>`;
		}
		html += `</tbody></table>`;
		$('#recent_apps_container').html(html);
	}

	function get_status_color(status) {
		const map = {
			'Draft': { bg: '#f1f5f9', text: '#475569' },
			'Submitted': { bg: '#e0f2fe', text: '#0369a1' },
			'Under Verification': { bg: '#fef3c7', text: '#92400e' },
			'Verified': { bg: '#dcfce7', text: '#166534' },
			'Fee Paid': { bg: '#f0fdf4', text: '#15803d' },
			'Enrolled': { bg: '#f3e8ff', text: '#7e22ce' },
			'Admitted': { bg: '#f3e8ff', text: '#7e22ce' },
			'Converted': { bg: '#f3e8ff', text: '#7e22ce' },
			'Rejected': { bg: '#fee2e2', text: '#991b1b' },
			'Returned for Correction': { bg: '#ffedd5', text: '#9a3412' }
		};
		return map[status] || { bg: '#f1f5f9', text: '#475569' };
	}

	function format_currency(v) {
		return frappe.format(v, { fieldtype: 'Currency' });
	}

	refresh_dashboard();
};
