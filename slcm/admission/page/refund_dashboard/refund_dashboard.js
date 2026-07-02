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
		.stat-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px 24px; display: flex; align-items: center; gap: 16px; transition: transform 0.2s; cursor: pointer; }
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
		change() { 
			window.current_limit_start = 0;
			refresh_dashboard(); 
		}
	});

	page.add_field({
		label: __('To Date'),
		fieldtype: 'Date',
		fieldname: 'to_date',
		default: frappe.datetime.nowdate(),
		change() { 
			window.current_limit_start = 0;
			refresh_dashboard(); 
		}
	});

	page.add_field({
		label: __('Campus'),
		fieldtype: 'Link',
		options: 'Campus',
		fieldname: 'campus',
		change() { 
			window.current_limit_start = 0;
			refresh_dashboard(); 
		}
	});

	page.add_field({
		label: __('Programme'),
		fieldtype: 'Link',
		options: 'Program',
		fieldname: 'program',
		change() { 
			window.current_limit_start = 0;
			refresh_dashboard(); 
		}
	});

	// Initialize pagination
	window.current_limit_start = 0;
	window.page_len = 10;

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
		<div class="col-md-6 d-flex"><div id="refund_trend" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 400px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
		<div class="col-md-6 d-flex"><div id="status_dist" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 400px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
	</div>`).appendTo(page.body);
	
	// Charts Row 2
	let chart_row_2 = $(`<div class="row mb-4" style="padding: 0 15px;">
		<div class="col-md-6 d-flex"><div id="reasons_dist" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 400px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
		<div class="col-md-6 d-flex"><div id="program_dist" class="card shadow-sm p-3 w-100 chart-container" style="min-height: 400px; border-radius: 12px; border: 1px solid #e2e8f0;"></div></div>
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

	const open_list_view = (type) => {
		let filters = {};
		let from_date = page.fields_dict.from_date.get_value();
		let to_date = page.fields_dict.to_date.get_value();

		let doctype = 'Refund Request';

		switch (type) {
			case 'total_refunded':
				filters.status = 'Processed';
				if (from_date && to_date) {
					filters.refund_date = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.refund_date = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.refund_date = ['<=', to_date + ' 23:59:59'];
				}
				break;
			case 'refunded_today':
				filters.status = 'Processed';
				filters.refund_date = ['between', [frappe.datetime.nowdate() + ' 00:00:00', frappe.datetime.nowdate() + ' 23:59:59']];
				break;
			case 'total_requests':
				if (from_date && to_date) {
					filters.request_date = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.request_date = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.request_date = ['<=', to_date + ' 23:59:59'];
				}
				break;
			case 'total_cancellations':
				doctype = 'Admission Cancellation';
				let campus = page.fields_dict.campus.get_value();
				let program = page.fields_dict.program.get_value();
				if (campus) filters.campus = campus;
				if (program) filters.program = program;
				if (from_date && to_date) {
					filters.requested_on = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.requested_on = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.requested_on = ['<=', to_date + ' 23:59:59'];
				}
				break;
			case 'pending_review':
				filters.status = 'Under Review';
				if (from_date && to_date) {
					filters.request_date = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.request_date = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.request_date = ['<=', to_date + ' 23:59:59'];
				}
				break;
			case 'approved_queue':
				filters.status = 'Approved';
				if (from_date && to_date) {
					filters.request_date = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.request_date = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.request_date = ['<=', to_date + ' 23:59:59'];
				}
				break;
			case 'processed':
				filters.status = 'Processed';
				if (from_date && to_date) {
					filters.refund_date = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.refund_date = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.refund_date = ['<=', to_date + ' 23:59:59'];
				}
				break;
			case 'failed':
				filters.status = 'Failed';
				if (from_date && to_date) {
					filters.request_date = ['between', [from_date + ' 00:00:00', to_date + ' 23:59:59']];
				} else if (from_date) {
					filters.request_date = ['>=', from_date + ' 00:00:00'];
				} else if (to_date) {
					filters.request_date = ['<=', to_date + ' 23:59:59'];
				}
				break;
		}

		frappe.set_route('List', doctype, filters);
	};

	function refresh_dashboard() {
		let filters = {
			from_date: page.fields_dict.from_date.get_value(),
			to_date: page.fields_dict.to_date.get_value(),
			campus: page.fields_dict.campus.get_value(),
			program: page.fields_dict.program.get_value(),
			limit_start: window.current_limit_start,
			limit_page_length: window.page_len
		};

		frappe.call({
			method: 'slcm.api.refund_dashboard.get_dashboard_data',
			args: { filters: filters },
			callback: function(r) {
				if (r.message) {
					render_kpis(r.message.kpis);
					render_charts(r.message.charts);
					render_table(r.message.recent_refunds, r.message.total_recent_refunds);
				}
			}
		});
	}

	function render_kpis(kpis) {
		kpi_section_1.empty();
		kpi_section_2.empty();

		// Row 1: Primary Metrics
		const row1 = [
			{ label: __('Total Refunded'), value: format_currency(kpis.total_refund_amount), icon: 'payments', cls: 'icon-blue', type: 'total_refunded' },
			{ label: __('Refunded Today'), value: format_currency(kpis.refunded_today), icon: 'calendar_today', cls: 'icon-green', type: 'refunded_today' },
			{ label: __('Total Requests'), value: kpis.total_requests, icon: 'description', cls: 'icon-orange', type: 'total_requests' },
			{ label: __('Total Cancellations'), value: kpis.total_cancellations, icon: 'cancel', cls: 'icon-red', type: 'total_cancellations' }
		];

		// Row 2: Status Breakdown (Unified with Row 1 design)
		const row2 = [
			{ label: __('Pending Review'), value: kpis.review, icon: 'pending', cls: 'icon-orange', type: 'pending_review' },
			{ label: __('Approved (Queue)'), value: kpis.approved, icon: 'verified', cls: 'icon-blue', type: 'approved_queue' },
			{ label: __('Processed'), value: kpis.processed, icon: 'task_alt', cls: 'icon-green', type: 'processed' },
			{ label: __('Failed'), value: kpis.failed, icon: 'error', cls: 'icon-red', type: 'failed' }
		];

		row1.forEach(item => {
			let $card = $(`<div class="stat-card shadow-sm">
				<div class="icon-box ${item.cls}">
					<span class="material-symbols-outlined">${item.icon}</span>
				</div>
				<div>
					<div class="stat-label">${item.label}</div>
					<div class="stat-value">${item.value}</div>
				</div>
			</div>`).appendTo(kpi_section_1);
			$card.on('click', () => open_list_view(item.type));
		});

		row2.forEach(item => {
			let $card = $(`<div class="stat-card shadow-sm">
				<div class="icon-box ${item.cls}">
					<span class="material-symbols-outlined">${item.icon}</span>
				</div>
				<div>
					<div class="stat-label">${item.label}</div>
					<div class="stat-value" style="color: inherit;">${item.value}</div>
				</div>
			</div>`).appendTo(kpi_section_2);
			$card.on('click', () => open_list_view(item.type));
		});
	}

	function render_charts(charts) {
		// Map colors to labels for the pie chart to ensure specific colors for Processed and Failed
		const status_colors_map = {
			'Processed': '#16a34a', // Green
			'Failed': '#dc2626',    // Red
			'Approved': '#2563eb',  // Blue
			'Under Review': '#f59e0b', // Orange
			'Rejected': '#4b5563',  // Slate
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
			height: 320,
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
			height: 340, // Slightly reduced height
			colors: pie_colors,
			maxSlices: 15,
			legendOptions: { position: 'bottom' }
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

	function render_table(refunds, total_count) {
		let html = `<div class="d-flex gap-2 mb-3 align-items-center" id="bulk_actions_container" style="display: none !important;">
			<span class="text-muted small" id="selected_count">0 selected</span>
			<button class="btn btn-sm btn-primary" onclick="process_selected_refunds()" style="font-weight: 700; border-radius: 6px;">
				<span class="material-symbols-outlined" style="font-size: 16px; margin-right: 4px; vertical-align: middle;">auto_mode</span>
				Bulk Process Refunds
			</button>
		</div>`;
		
		html += `<table class="table refund-table mt-2" style="font-size: 13px;">
			<thead class="custom-table-header">
				<tr>
					<th style="width: 40px;"><input type="checkbox" id="select_all_refunds" onclick="toggle_all_refunds(this)"></th>
					<th>${__('Refund ID')}</th>
					<th>${__('Applicant')}</th>
					<th>${__('Program')}</th>
					<th class="text-right">${__('Paid')}</th>
					<th class="text-right">${__('Refunded')}</th>
					<th>${__('Status')}</th>
					<th>${__('Request Date')}</th>
				</tr>
			</thead>
			<tbody id="refund_table_body">`;

		refunds.forEach(r => {
			let status_color = get_status_color(r.status);
			let checkbox_disabled = r.status !== 'Approved' ? 'disabled' : '';
			html += `<tr data-name="${r.name}" onclick="handle_row_click(event, '${r.name}')">
				<td><input type="checkbox" class="refund-checkbox" value="${r.name}" ${checkbox_disabled} onclick="event.stopPropagation(); update_bulk_actions();"></td>
				<td><a class="clickable-id" onclick="event.stopPropagation(); frappe.set_route('Form', 'Refund Request', '${r.name}')">${r.name}</a></td>
				<td>${r.applicant}</td>
				<td>${r.program}</td>
				<td class="font-weight-bold text-right" style="white-space: nowrap;">${format_currency(r.amount_paid)}</td>
				<td class="font-weight-bold text-dark text-right" style="white-space: nowrap;">${format_currency(r.refund_amount)}</td>
				<td><span class="badge badge-${status_color}" style="font-weight: 600; padding: 4px 8px;">${r.status}</span></td>
				<td class="text-muted">${frappe.datetime.global_date_format(r.request_date)}</td>
			</tr>`;
		});

		if (refunds.length === 0) {
			html += `<tr><td colspan="8" class="text-center text-muted p-4">${__('No recent refund requests found')}</td></tr>`;
		}
		html += `</tbody></table>`;

		// Pagination Controls
		if (total_count > window.page_len) {
			let has_prev = window.current_limit_start > 0;
			let has_next = (window.current_limit_start + window.page_len) < total_count;
			
			html += `<div class="d-flex justify-content-between align-items-center mt-3 p-2" style="background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
				<div class="text-muted small" style="font-weight: 600;">
					Showing ${window.current_limit_start + 1} - ${Math.min(window.current_limit_start + window.page_len, total_count)} of ${total_count}
				</div>
				<div class="d-flex gap-2">
					<button class="btn btn-xs btn-default ${!has_prev ? 'disabled' : ''}" 
							${has_prev ? 'onclick="change_page(-1)"' : ''} style="font-weight: 600; border-radius: 4px; border: 1px solid #d1d5db;">
						<span class="material-symbols-outlined" style="font-size: 16px; vertical-align: middle;">chevron_left</span>
						${__('Prev')}
					</button>
					<button class="btn btn-xs btn-default ${!has_next ? 'disabled' : ''}" 
							${has_next ? 'onclick="change_page(1)"' : ''} style="font-weight: 600; border-radius: 4px; border: 1px solid #d1d5db;">
						${__('Next')}
						<span class="material-symbols-outlined" style="font-size: 16px; vertical-align: middle;">chevron_right</span>
					</button>
				</div>
			</div>`;
		}

		$('#refund_table_container').html(html);
	}

	window.change_page = function(direction) {
		window.current_limit_start += (direction * window.page_len);
		// Force refresh table part
		refresh_dashboard();
	};

	window.toggle_all_refunds = function(source) {
		$('.refund-checkbox:not(:disabled)').prop('checked', source.checked);
		update_bulk_actions();
	};

	window.handle_row_click = function(event, name) {
		// If clicking a link or checkbox, let it be
		if (event.target.tagName === 'A' || event.target.tagName === 'INPUT') return;
		
		frappe.set_route('Form', 'Refund Request', name);
	};

	window.update_bulk_actions = function() {
		let selected = $('.refund-checkbox:checked').length;
		if (selected > 0) {
			$('#bulk_actions_container').attr('style', 'display: flex !important;');
			$('#selected_count').text(`${selected} selected`);
		} else {
			$('#bulk_actions_container').attr('style', 'display: none !important;');
			$('#select_all_refunds').prop('checked', false);
		}
	};

	window.process_selected_refunds = function() {
		let selected_refunds = [];
		$('.refund-checkbox:checked').each(function() {
			selected_refunds.push($(this).val());
		});

		if (selected_refunds.length === 0) return;

		frappe.confirm(
			__('Are you sure you want to process {0} refunds via Razorpay?', [selected_refunds.length]),
			function() {
				frappe.show_alert({ message: __('Initiating bulk refund process...'), indicator: 'blue' });
				
				frappe.call({
					method: 'slcm.admission_cancel_api.process_bulk_refunds',
					args: { names: selected_refunds },
					callback: function(r) {
						if (r.message) {
							show_bulk_results(r.message);
							refresh_dashboard();
						}
					}
				});
			}
		);
	};

	function show_bulk_results(results) {
		let success = results.filter(res => res.status === 'Success').length;
		let failed = results.filter(res => res.status === 'Error').length;
		
		let detail_html = `<div style="max-height: 300px; overflow-y: auto; margin-top: 15px;">
			<table class="table table-bordered table-sm" style="font-size: 12px;">
				<thead><tr><th>ID</th><th>Status</th><th>Result</th></tr></thead>
				<tbody>`;
		
		results.forEach(res => {
			let icon = res.status === 'Success' ? '🟢' : '🔴';
			detail_html += `<tr>
				<td><strong>${res.name}</strong></td>
				<td>${icon} ${res.status}</td>
				<td class="text-muted"><small>${res.message || ''}</small></td>
			</tr>`;
		});
		
		detail_html += `</tbody></table></div>`;

		frappe.msgprint({
			title: __('Bulk Refund Summary'),
			message: `
				<div class="text-center mb-3">
					<div class="d-inline-block p-3 rounded" style="background: #f0fdf4; margin-right: 15px;">
						<div style="font-size: 24px; font-weight: 800; color: #16a34a;">${success}</div>
						<div style="font-size: 11px; font-weight: 700; color: #15803d; text-transform: uppercase;">Success</div>
					</div>
					<div class="d-inline-block p-3 rounded" style="background: #fef2f2;">
						<div style="font-size: 24px; font-weight: 800; color: #dc2626;">${failed}</div>
						<div style="font-size: 11px; font-weight: 700; color: #991b1b; text-transform: uppercase;">Failed</div>
					</div>
				</div>
				${detail_html}
			`,
			indicator: failed > 0 ? 'orange' : 'green',
			wide: true
		});
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
