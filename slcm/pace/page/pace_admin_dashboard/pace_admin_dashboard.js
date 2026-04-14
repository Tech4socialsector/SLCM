frappe.pages['pace-admin-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('PACE Admissions Dashboard'),
		single_column: true
	});

	// --- 1. Inject Material Symbols and Custom Styles ---
	$('<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">').appendTo('head');
	$(`<style>
		.dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 24px; padding: 0 15px; }
		.stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; display: flex; align-items: center; gap: 16px; transition: transform 0.2s, box-shadow 0.2s; cursor: pointer; }
		.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
		
		.icon-box { width: 48px; height: 48px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
		.icon-blue   { background: #dbeafe !important; color: #2563eb !important; }
		.icon-green  { background: #dcfce7 !important; color: #16a34a !important; }
		.icon-orange { background: #ffedd5 !important; color: #ea580c !important; }
		.icon-red    { background: #fee2e2 !important; color: #dc2626 !important; }
		.icon-purple { background: #f3e8ff !important; color: #9333ea !important; }
		.icon-teal   { background: #f0fdf4 !important; color: #0d9488 !important; }

		.stat-label { font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
		.stat-value { font-size: 20px; font-weight: 800; color: #1e293b; line-height: 1.2; }
		
		.section-title-container { border-left: 4px solid #2563eb; padding-left: 15px; margin: 30px 15px 24px 15px; }
		.section-title { font-size: 18px; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
		.section-subtitle { font-size: 13px; color: #64748b; }

		.chart-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; height: 100%; }
		.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
		.chart-title { font-size: 14px; font-weight: 700; color: #334155; margin: 0; }

		.recent-apps-table th { background: #f8fafc !important; color: #64748b !important; font-weight: 700 !important; text-transform: uppercase !important; font-size: 11px !important; letter-spacing: 0.05em !important; border: none !important; }
		.recent-apps-table td { vertical-align: middle !important; font-size: 13px; color: #1e293b; }
		.status-badge { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; }
		
		.priority-badge { padding: 4px 10px; border-radius: 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
		.priority-high { background: #fee2e2; color: #dc2626; }
		.priority-medium { background: #fef3c7; color: #d97706; }
		.priority-low { background: #f1f5f9; color: #64748b; }

		.days-pending-red { color: #dc2626; font-weight: 700; }
		.days-pending-amber { color: #d97706; font-weight: 700; }

		.clickable-id { color: #2563eb; font-weight: 700; cursor: pointer; }
		.clickable-id:hover { text-decoration: underline; }

		.filter-bar { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px 20px; margin: 0 15px 24px 15px; display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end; }
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
	
	let kpi_grid = $(`<div class="dashboard-grid"></div>`).appendTo(page.body);

	// Charts Section
	$(`<div class="section-title-container">
		<div class="section-title">${__('Trends & Analytics')}</div>
		<div class="section-subtitle">${__('Deep dive into application funnel and demographics')}</div>
	</div>`).appendTo(page.body);

	let chart_row_1 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-7"><div class="chart-card"><div class="chart-header"><h6 class="chart-title">${__('Application Funnel')}</h6></div><div id="funnel_chart"></div></div></div>
		<div class="col-md-5"><div class="chart-card"><div class="chart-header"><h6 class="chart-title">${__('Daily Application Trend')}</h6></div><div id="trend_chart"></div></div></div>
	</div>`).appendTo(page.body);

	let chart_row_2 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-6"><div class="chart-card"><div class="chart-header"><h6 class="chart-title">${__('Status Distribution')}</h6></div><div id="status_chart"></div></div></div>
		<div class="col-md-6"><div class="chart-card"><div class="chart-header"><h6 class="chart-title">${__('Program Popularity')}</h6></div><div id="program_chart"></div></div></div>
	</div>`).appendTo(page.body);

	// Pending Work Section
	$(`<div class="section-title-container">
		<div class="section-title">${__('Section 5 — Pending Work')}</div>
		<div class="section-subtitle">${__('Actionable items requiring attention')}</div>
	</div>`).appendTo(page.body);

	let pending_section = $(`<div class="card shadow-sm p-4 mt-4 mx-3 mb-5" style="border-radius: 12px; border: 1px solid #e2e8f0;">
		<div id="pending_work_container" style="overflow-x: auto;"></div>
	</div>`).appendTo(page.body);

	// Recent Table
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
					render_charts(r.message.charts);
					render_table(r.message.recent_applications);
					render_pending_work(r.message.pending_work);
				}
			}
		});
	}

	function render_kpis(kpis) {
		kpi_grid.empty();
		const items = [
			{ label: __('Applications'), value: kpis.total_applications, icon: 'description', cls: 'icon-purple', route: 'List/PACE Application' },
			{ label: __('Unassigned Docs'), value: kpis.unassigned, icon: 'assignment_ind', cls: 'icon-orange', route: 'List/PACE Application/Submitted' },
			{ label: __('Verified'), value: kpis.verified_apps, icon: 'verified', cls: 'icon-teal', route: 'List/PACE Application/Verified' },
			{ label: __('Admissions'), value: kpis.total_admissions, icon: 'school', cls: 'icon-green', route: 'List/PACE Application/Admitted' },
			{ label: __('Revenue'), value: format_currency(kpis.total_revenue), icon: 'payments', cls: 'icon-green', route: 'List/PACE Receipt' },
			{ label: __('Re-upload Req'), value: kpis.returned, icon: 'replay', cls: 'icon-orange', route: 'List/PACE Application/Returned for Correction' },
			{ label: __('Pending'), value: kpis.pending, icon: 'history', cls: 'icon-orange', route: 'List/PACE Application/Submitted,Under Verification' },
			{ label: __('Rejected'), value: kpis.rejected, icon: 'cancel', cls: 'icon-red', route: 'List/PACE Application/Rejected' }
		];

		items.forEach(item => {
			$(`<div class="stat-card" onclick="frappe.set_route('${item.route}')">
				<div class="icon-box ${item.cls}">
					<span class="material-symbols-outlined">${item.icon}</span>
				</div>
				<div>
					<div class="stat-label">${item.label}</div>
					<div class="stat-value">${item.value}</div>
				</div>
			</div>`).appendTo(kpi_grid);
		});
	}

	function render_charts(charts) {
		// 1. Funnel
		new frappe.Chart("#funnel_chart", {
			data: {
				labels: charts.funnel.labels,
				datasets: [{ values: charts.funnel.values }]
			},
			type: 'bar',
			height: 300,
			colors: ['#2563eb'],
			barOptions: { space_between_bars: 35 }
		});

		// 2. Trend
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

		// 3. Status
		new frappe.Chart("#status_chart", {
			data: {
				labels: charts.status_dist.map(d => d.label),
				datasets: [{ values: charts.status_dist.map(d => d.value) }]
			},
			type: 'donut',
			height: 300,
			colors: ['#2563eb', '#16a34a', '#ea580c', '#dc2626', '#94a3b8']
		});

		// 4. Programs
		new frappe.Chart("#program_chart", {
			data: {
				labels: charts.program_dist.map(d => d.label),
				datasets: [{ values: charts.program_dist.map(d => d.value) }]
			},
			type: 'bar',
			height: 300,
			colors: ['#0d9488'],
			axisOptions: { xIsSeries: true }
		});
	}

	function render_pending_work(pending) {
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

		pending.forEach(item => {
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

		if (pending.length === 0) {
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
			'Admitted': { bg: '#f3e8ff', text: '#7e22ce' },
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
