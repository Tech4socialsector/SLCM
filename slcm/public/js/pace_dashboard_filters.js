
/**
 * Global Filter Injection for PACE Dashboard
 * This script provides a robust global filter bar for the standard PACE dashboard.
 */

(function() {
	console.log("SLCM: PACE Dashboard Filters script initialized");

	// 1. Monkey-patch get_all_filters to inject/override filters for PACE widgets
	const original_get_all_filters = frappe.dashboard_utils.get_all_filters;
	frappe.dashboard_utils.get_all_filters = function(doc) {
		let filters = original_get_all_filters.apply(this, arguments);
		
		const route = frappe.get_route();
		if (route && route[0] === 'dashboard-view' && route[1] === 'PACE' && frappe._pace_dashboard_filters) {
			const global = frappe._pace_dashboard_filters;
			const target_doctype = doc.document_type || (doc.report_name ? 'PACE Application' : null);
			
			if (target_doctype) {
				const is_report = !!doc.report_name;
				
				if (!is_report && Array.isArray(filters)) {
					// Handle Standard DocType Filters (Arrays)
					apply_array_filters(filters, target_doctype, global);
				} else {
					// Handle Report/Object Filters (Objects)
					if (Array.isArray(filters)) filters = {};
					apply_object_filters(filters, target_doctype, global, doc.report_name);
				}
			}
		}
		return filters;
	};

	function apply_array_filters(filters, doctype, global) {
		const maps = {
			'PACE Application': { year: 'academic_year', prog: 'programme', date: 'creation' },
			'PACE Receipt': { year: null, prog: 'program', date: 'creation' },
			'PACE Applicant Fee Assignment': { year: 'academic_year', prog: 'program', date: 'assignment_date' },
			'PACE Document Verification': { year: 'academic_year', prog: null, date: 'creation' }
		};

		const map = maps[doctype] || { year: null, prog: null, date: 'creation' };

		const upsert = (fieldname, op, value) => {
			if (!fieldname) return;
			let found = false;
			for (let i = 0; i < filters.length; i++) {
				if (Array.isArray(filters[i]) && filters[i][1] === fieldname) {
					filters[i] = [doctype, fieldname, op, value];
					found = true;
					break;
				}
			}
			if (!found) filters.push([doctype, fieldname, op, value]);
		};

		if (global.academic_year) upsert(map.year, '=', global.academic_year);
		if (global.programme) upsert(map.prog, '=', global.programme);
		if (global.from_date || global.to_date) {
			let start = global.from_date || '1900-01-01';
			let end = global.to_date || '2099-12-31';
			upsert(map.date, 'between', [start, end]);
		}
	}

	function apply_object_filters(filters, doctype, global, report_name) {
		if (global.academic_year) filters.academic_year = global.academic_year;
		if (global.programme) {
			// Reports ALWAYS use 'program'
			let prog_key = (doctype === 'PACE Receipt' || report_name) ? 'program' : 'programme';
			filters[prog_key] = global.programme;
		}
		if (global.from_date) filters.from_date = global.from_date;
		if (global.to_date) filters.to_date = global.to_date;
	}

	// 2. Dashboard Integration Logic
	let filter_check_interval = setInterval(() => {
		const route = frappe.get_route();
		if (route && route[0] === 'dashboard-view' && route[1] === 'PACE') {
			let dashboard = frappe.dashboard;
			if (!dashboard && cur_page && cur_page.page.dashboard) {
				dashboard = cur_page.page.dashboard;
			}

			if (dashboard && (dashboard.dashboard_name === 'PACE' || dashboard.name === 'PACE')) {
				if (!dashboard.$filter_bar) {
					render_pace_filters(dashboard);
				}
			} else {
				const $container = $('.dashboard-graph');
				if ($container.length && !$('.pace-filter-bar').length) {
					render_pace_filters({ container: $container });
				}
			}
		}
	}, 200);

	function render_pace_filters(dashboard) {
		if ($('.pace-filter-bar').length) return;

		const $target = dashboard.container || $('.dashboard-graph');
		if (!$target || !$target.length) return;

		dashboard.$filter_bar = $(`
			<div class="pace-filter-bar shadow-sm px-3 py-3 mb-4" style="background: #fff; border-radius: 8px; border: 1px solid #e2e8f0; display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end; width: 100%; z-index: 101;">
			</div>
		`).prependTo($target);

		frappe._pace_dashboard_filters = {};

		const config = [
			{ label: __('Academic Year'), fieldname: 'academic_year', fieldtype: 'Link', options: 'Academic Year' },
			{ label: __('Programme'), fieldname: 'programme', fieldtype: 'Link', options: 'PACE Programme' },
			{ label: __('From Date'), fieldname: 'from_date', fieldtype: 'Date' },
			{ label: __('To Date'), fieldname: 'to_date', fieldtype: 'Date' }
		];

		config.forEach(f => {
			const $wrapper = $(`<div style="min-width: 180px;"></div>`).appendTo(dashboard.$filter_bar);
			const ctrl = frappe.ui.form.make_control({
				df: {
					...f,
					onchange: () => {
						frappe._pace_dashboard_filters[f.fieldname] = ctrl.get_value();
						refresh_pace_widgets(dashboard);
					}
				},
				parent: $wrapper,
				render_input: true
			});
		});

		$(`<button class="btn btn-default btn-sm ml-auto" style="height: 36px;">
			<i class="fa fa-refresh mr-1"></i> ${__('Reset')}
		</button>`).appendTo(dashboard.$filter_bar).on('click', () => {
			dashboard.$filter_bar.find('.form-control').val('').trigger('change');
			frappe._pace_dashboard_filters = {};
			refresh_pace_widgets(dashboard);
		});
	}

	function refresh_pace_widgets(dashboard) {
		let d = dashboard || frappe.dashboard;
		if (!d) return;
		const global = frappe._pace_dashboard_filters;

		// Refresh Cards
		if (d.number_card_group) {
			d.number_card_group.widgets_list.forEach(w => {
				if (w.render_card) w.render_card();
			});
		}

		// Refresh Charts
		if (d.chart_group) {
			d.chart_group.widgets_list.forEach(w => {
				// Reduce height for Pace Fee Status as requested
				if (w.chart_name === "Pace Fee Status" || w.name === "Pace Fee Status") {
					w.height = 180;
					if (w.body) w.body.find(".chart-loading-state, .chart-wrapper").css("height", "180px");
				}

				// Brute-force override filters for Reports just before refresh
				if (w.chart_doc && w.chart_doc.report_name) {
					if (!w.filters || Array.isArray(w.filters)) w.filters = {};
					apply_object_filters(w.filters, w.chart_doc.document_type, global, w.chart_doc.report_name);
				}
				
				if (w.set_chart_filters && w.fetch_and_update_chart) {
					w.set_chart_filters().then(() => {
						w.fetch_and_update_chart();
					});
				} else if (w.refresh) {
					w.refresh();
				}
			});
		}
	}
})();
