frappe.pages['refund_dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Refund Management Dashboard'),
		single_column: true
	});

	// --- 1. Inject Material Symbols and Custom Styles ---
	$('<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">').appendTo('head');
	$(`<style>
		.dashboard-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 24px; padding: 0 15px; }
		.stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; display: flex; align-items: center; gap: 16px; transition: transform 0.2s; }
		.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
		
		.icon-box { width: 48px; height: 48px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
		.icon-blue   { background: #dbeafe !important; color: #2563eb !important; }
		.icon-green  { background: #dcfce7 !important; color: #16a34a !important; }
		.icon-orange { background: #ffedd5 !important; color: #ea580c !important; }
		.icon-red    { background: #fee2e2 !important; color: #dc2626 !important; }

		.stat-label { font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: none; letter-spacing: 0.08em; margin-bottom: 4px; }
		.stat-value { font-size: 18px; font-weight: 800; color: #1e293b; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		
		.section-title-container { border-left: 3px solid #2563eb; padding-left: 12px; margin: 30px 15px 24px 15px; }
		.section-title { font-size: 16px; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
		.section-subtitle { font-size: 12px; color: #64748b; }

		.chart-container .title { font-size: 13px !important; font-weight: 700 !important; color: #374151 !important; }
		.graph-svg-tip .title { text-transform: none !important; }
		.graph-svg-tip .value { font-weight: 700 !important; }

		.refund-table tbody tr:hover { background: #f8fafc !important; cursor: pointer; }
		.custom-table-header th { background-color: #f8fafc !important; color: #64748b !important; font-weight: 600 !important; text-transform: none !important; font-size: 11px !important; letter-spacing: 0.05em !important; border-top: none !important; }
		.clickable-id { color: #2563eb; font-weight: 700; text-decoration: none; }
		.clickable-id:hover { text-decoration: underline; }
		
		.btn-view-all { border: 1px solid #e2e8f0; padding: 4px 12px; border-radius: 6px; font-size: 12px; color: #64748b; background: white; font-weight: 600; transition: all 0.2s; }
		.btn-view-all:hover { background: #f8fafc; border-color: #cbd5e1; color: #1e293b; }
	</style>`).appendTo('head');

	// --- 2. Filters ---
	page.add_field({
		label: __('From Date'),
		fieldtype: 'Date',
		fieldname: 'from_date',
		default: frappe.datetime.add_months(frappe.datetime.nowdate(), -1),
		change() { refresh_dashboard(); }
	});

	page.add_field({
		label: __('To Date'),
		fieldtype: 'Date',
		fieldname: 'to_date',
		default: frappe.datetime.nowdate(),
		change() { refresh_dashboard(); }
	});

	page.add_field({
		label: __('Campus'),
		fieldtype: 'Link',
		options: 'Campus',
		fieldname: 'campus',
		change() { refresh_dashboard(); }
	});

	page.add_field({
		label: __('Program'),
		fieldtype: 'Link',
		options: 'Program',
		fieldname: 'program',
		change() { refresh_dashboard(); }
	});

	// --- 3. Layout Structure ---
	
	// KPI Header
	let kpi_header = $(`<div class="section-title-container">
		<div class="section-title">${__('Financial & Operational Overview')}</div>
		<div class="section-subtitle">${__('Real-time tracking of refund requests and financial impact')}</div>
	</div>`).appendTo(page.body);
	
	let kpi_section_1 = $(`<div class="dashboard-grid"></div>`).appendTo(page.body);
	let kpi_section_2 = $(`<div class="dashboard-grid"></div>`).appendTo(page.body);

	// Charts Row 1
	let chart_row_1 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-8 d-flex"><div id="refund_trend" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 350px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
		<div class="col-md-4 d-flex"><div id="status_dist" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 350px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
	</div>`).appendTo(page.body);
	
	// Charts Row 2
	let chart_row_2 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-6 d-flex"><div id="reasons_dist" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 350px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
		<div class="col-md-6 d-flex"><div id="program_dist" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 350px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
	</div>`).appendTo(page.body);

	// Table Section
	let table_section = $(`<div class="card shadow-sm p-4 mt-4 mx-3 mb-5" style="border-radius: 12px; border: 1px solid #e2e8f0;">
		<div class="d-flex justify-content-between align-items-center mb-3">
			<h5 class="mb-0" style="font-size: 15px; font-weight: 700; color: #374151;">${__('Recent Refund Requests')}</h5>
			<button class="btn-view-all" onclick="frappe.set_route('List', 'Refund Request')">${__('View All')}</button>
		</div>
		<div id="refund_table_container" style="overflow-x: auto;"></div>
	</div>`).appendTo(page.body);

	// --- 4. Refresh Logic ---

	function refresh_dashboard() {
		let filters = {
			from_date: page.fields_dict.from_date.get_value(),
			to_date: page.fields_dict.to_date.get_value(),
			campus: page.fields_dict.campus.get_value(),
			program: page.fields_dict.program.get_value()
		};

		frappe.call({
			method: 'slcm.api.refund_dashboard.get_dashboard_data',
			args: { filters: filters },
			callback: function(r) {
				if (r.message) {
					render_kpis(r.message.kpis);
					render_charts(r.message.charts);
					render_table(r.message.recent_refunds);
				}
			}
		});
	}

	function render_kpis(kpis) {
		kpi_section_1.empty();
		kpi_section_2.empty();

		// Row 1: Primary Metrics
		const row1 = [
			{ label: __('Total Refunded'), value: format_currency(kpis.total_refund_amount), icon: 'payments', cls: 'icon-blue' },
			{ label: __('Refunded Today'), value: format_currency(kpis.refunded_today), icon: 'calendar_today', cls: 'icon-green' },
			{ label: __('Total Requests'), value: kpis.total_requests, icon: 'description', cls: 'icon-orange' },
			{ label: __('Total Cancellations'), value: kpis.total_cancellations, icon: 'cancel', cls: 'icon-red' }
		];

		// Row 2: Status Breakdown (Unified with Row 1 design)
		const row2 = [
			{ label: __('Pending Review'), value: kpis.review, icon: 'pending', cls: 'icon-orange' },
			{ label: __('Approved (Queue)'), value: kpis.approved, icon: 'verified', cls: 'icon-blue' },
			{ label: __('Processed'), value: kpis.processed, icon: 'task_alt', cls: 'icon-green' },
			{ label: __('Failed'), value: kpis.failed, icon: 'error', cls: 'icon-red' }
		];

		row1.forEach(item => {
			$(`<div class="stat-card shadow-sm">
				<div class="icon-box ${item.cls}">
					<span class="material-symbols-outlined">${item.icon}</span>
				</div>
				<div>
					<div class="stat-label">${item.label}</div>
					<div class="stat-value">${item.value}</div>
				</div>
			</div>`).appendTo(kpi_section_1);
		});

		row2.forEach(item => {
			$(`<div class="stat-card shadow-sm">
				<div class="icon-box ${item.cls}">
					<span class="material-symbols-outlined">${item.icon}</span>
				</div>
				<div>
					<div class="stat-label">${item.label}</div>
					<div class="stat-value" style="color: inherit;">${item.value}</div>
				</div>
			</div>`).appendTo(kpi_section_2);
		});
	}

	function render_charts(charts) {
		// Map colors to labels for the pie chart to ensure specific colors for Processed and Failed
		const status_colors_map = {
			'Processed': '#16a34a', // Green
			'Failed': '#dc2626',    // Red
			'Approved': '#2563eb',  // Blue
			'Under Review': '#f59e0b', // Orange
			'Draft': '#94a3b8'      // Grey
		};
		
		const pie_colors = charts.status_dist.map(d => status_colors_map[d.label] || '#94a3b8');

		// 1. Trend Line Chart
		new frappe.Chart("#refund_trend", {
			title: __("Refund Trend (Daily)"),
			data: {
				labels: charts.trend.map(d => d.date),
				datasets: [{ name: __("Amount"), values: charts.trend.map(d => d.amount) }]
			},
			type: 'line',
			height: 300,
			colors: ['#2563eb']
		});

		// 2. Status Pie Chart
		new frappe.Chart("#status_dist", {
			title: __("Status Distribution"),
			data: {
				labels: charts.status_dist.map(d => d.label),
				datasets: [{ values: charts.status_dist.map(d => d.value) }]
			},
			type: 'pie',
			height: 300,
			colors: pie_colors
		});

		// 3. Reasons Bar Chart
		new frappe.Chart("#reasons_dist", {
			title: __("Cancellation Reasons"),
			data: {
				labels: charts.reasons.map(d => d.label || 'Other'),
				datasets: [{ values: charts.reasons.map(d => d.value) }]
			},
			type: 'bar',
			height: 300,
			colors: ['#2563eb']
		});

		// 4. Program Bar Chart
		new frappe.Chart("#program_dist", {
			title: __("Refund by Program (Top 10)"),
			data: {
				labels: charts.program_dist.map(d => d.label),
				datasets: [{ values: charts.program_dist.map(d => d.value) }]
			},
			type: 'bar',
			height: 300,
			colors: ['#60a5fa']
		});
	}

	function render_table(refunds) {
		let html = `<table class="table refund-table mt-2" style="font-size: 13px;">
			<thead class="custom-table-header">
				<tr>
					<th>${__('Refund ID')}</th>
					<th>${__('Applicant')}</th>
					<th>${__('Program')}</th>
					<th>${__('Paid')}</th>
					<th>${__('Refunded')}</th>
					<th>${__('Status')}</th>
					<th>${__('Request Date')}</th>
				</tr>
			</thead>
			<tbody>`;

		refunds.forEach(r => {
			let status_color = get_status_color(r.status);
			html += `<tr onclick="frappe.set_route('Form', 'Refund Request', '${r.name}')">
				<td><a class="clickable-id">${r.name}</a></td>
				<td>${r.applicant}</td>
				<td>${r.program}</td>
				<td class="font-weight-bold">${format_currency(r.amount_paid)}</td>
				<td class="font-weight-bold text-dark">${format_currency(r.refund_amount)}</td>
				<td><span class="badge badge-${status_color}" style="font-weight: 600; padding: 4px 8px;">${r.status}</span></td>
				<td class="text-muted">${frappe.datetime.global_date_format(r.request_date)}</td>
			</tr>`;
		});

		if (refunds.length === 0) {
			html += `<tr><td colspan="7" class="text-center text-muted p-4">${__('No recent refund requests found')}</td></tr>`;
		}

		html += `</tbody></table>`;
		$('#refund_table_container').html(html);
	}

	function format_currency(v) {
		return frappe.format(v, { fieldtype: 'Currency' });
	}

	function get_status_color(status) {
		const map = {
			'Processed': 'success',
			'Approved': 'info',
			'Under Review': 'warning',
			'Failed': 'danger',
			'Draft': 'secondary',
			'Processing': 'blue'
		};
		return map[status] || 'secondary';
	}

	refresh_dashboard();
};
