/**
 * Global Filter Injection for PACE Document Verifier Dashboard
 */

(function() {
	console.log("SLCM: PACE Document Verifier Filters initialized");

	// 1. Monkey-patch get_all_filters
	const original_get_all_filters = frappe.dashboard_utils.get_all_filters;
	frappe.dashboard_utils.get_all_filters = function(doc) {
		let filters = original_get_all_filters.apply(this, arguments);
		
		const route = frappe.get_route();
		if (route && route[0] === 'dashboard-view' && route[1] === 'Document Verifier' && frappe._pace_verifier_filters) {
			const global = frappe._pace_verifier_filters;
			const target_doctype = doc.document_type || 'PACE Document Verification';
			
			if (Array.isArray(filters)) {
				// Clear existing and re-apply to ensure no conflicts
				const new_filters = [];
				if (global.programme) new_filters.push([target_doctype, 'programme', '=', global.programme]);
				if (global.academic_year) new_filters.push([target_doctype, 'academic_year', '=', global.academic_year]);
				if (global.assigned_verifier) new_filters.push([target_doctype, 'assigned_verifier', '=', global.assigned_verifier]);
				
				// Keep non-conflicting filters
				filters.forEach(f => {
					if (!['programme', 'academic_year', 'assigned_verifier'].includes(f[1])) {
						new_filters.push(f);
					}
				});
				return new_filters;
			}
		}
		return filters;
	};

	// 2. Dashboard Integration Logic
	let filter_check_interval = setInterval(() => {
		const route = frappe.get_route();
		const dashboard_name = (route && route[0] === 'dashboard-view') ? route[1] : null;
		
		if (dashboard_name === 'Document Verifier') {
			// Role Check
			const allowed_roles = ['PACE Admission Manager', 'System Manager', 'Document Verifier', 'Administrator'];
			const has_role = frappe.user_roles.some(role => allowed_roles.includes(role));
			if (!has_role) {
				if (!$('.pace-auth-error').length) {
					frappe.show_alert({ message: __('Unauthorized Access to this Dashboard.'), indicator: 'red' });
					$('<div class="pace-auth-error"></div>').appendTo('body');
					frappe.set_route('dashboard-view', 'PACE');
				}
				return;
			}

			let dashboard = frappe.dashboard;
			if (!dashboard && cur_page && cur_page.page.dashboard) {
				dashboard = cur_page.page.dashboard;
			}

			if (dashboard && !dashboard.$verifier_filter_bar) {
				render_verifier_filters(dashboard);
			}
		}
	}, 500);

	function render_verifier_filters(dashboard) {
		if ($('.pace-verifier-filter-bar').length) return;

		const $target = dashboard.container || $('.dashboard-graph');
		if (!$target || !$target.length) return;

		dashboard.$verifier_filter_bar = $(`
			<div class="pace-verifier-filter-bar shadow-sm px-4 py-3 mb-4" style="background: #ffffff; border-radius: 12px; border: 1px solid #edf2f7; display: flex; flex-wrap: wrap; gap: 15px; align-items: flex-end; width: 100%; z-index: 101;">
			</div>
		`).prependTo($target);

		if (!frappe._pace_verifier_filters) frappe._pace_verifier_filters = {};

		const is_verifier_only = frappe.user_roles.includes("Document Verifier") && 
								!frappe.user_roles.includes("PACE Manager") && 
								!frappe.user_roles.includes("System Manager") &&
								!frappe.user_roles.includes("Admission Admin") &&
								!frappe.user_roles.includes("PACE Admission Manager");

		const config = [
			{ label: __('Academic Year'), fieldname: 'academic_year', fieldtype: 'Link', options: 'Academic Year', default: frappe.defaults.get_user_default("academic_year") },
			{ label: __('Programme'), fieldname: 'programme', fieldtype: 'Link', options: 'PACE Programme' },
			{ 
				label: __('Document Verifier'), 
				fieldname: 'assigned_verifier', 
				fieldtype: is_verifier_only ? 'Data' : 'Link', 
				options: 'User',
				read_only: is_verifier_only ? 1 : 0,
				get_query: () => {
					return {
						query: 'slcm.pace.page.pace_admin_dashboard.pace_admin_dashboard.get_verifier_users_for_link'
					};
				}
			}
		];

		config.forEach(f => {
			const $wrapper = $(`<div style="min-width: 200px; flex: 1; ${f.hidden ? 'display: none;' : ''}"></div>`).appendTo(dashboard.$verifier_filter_bar);
			
			// Set initial value for verifier if restricted
			if (f.fieldname === 'assigned_verifier' && is_verifier_only) {
				frappe._pace_verifier_filters[f.fieldname] = frappe.session.user;
			}

			const ctrl = frappe.ui.form.make_control({
				df: {
					...f,
					onchange: () => {
						frappe._pace_verifier_filters[f.fieldname] = ctrl.get_value();
					}
				},
				parent: $wrapper,
				render_input: true
			});

			if (f.default) {
				ctrl.set_value(f.default);
				frappe._pace_verifier_filters[f.fieldname] = f.default;
			} else if (f.fieldname === 'assigned_verifier' && is_verifier_only) {
				ctrl.set_value(frappe.session.user);
			}

			$wrapper.find('.frappe-control').css('margin-bottom', '0');
		});

		$(`<button class="btn btn-primary btn-sm px-4" style="height: 38px; border-radius: 8px; font-weight: 600; background: #1a202c; border: none; display: flex; align-items: center; gap: 8px;">
			<i class="fa fa-play" style="font-size: 10px;"></i> ${__('Go')}
		</button>`).appendTo(dashboard.$verifier_filter_bar).on('click', () => {
			refresh_widgets(dashboard);
		});

		$(`<button class="btn btn-default btn-sm px-3" style="height: 38px; border-radius: 8px; border: 1px solid #e2e8f0; color: #4a5568; background: #fff; display: flex; align-items: center; gap: 8px; margin-left: auto;">
			<i class="fa fa-refresh" style="font-size: 12px;"></i> ${__('Reset')}
		</button>`).appendTo(dashboard.$verifier_filter_bar).on('click', () => {
			dashboard.$verifier_filter_bar.find('.form-control').val('').trigger('change');
			frappe._pace_verifier_filters = {};
			refresh_widgets(dashboard);
		});
	}

	function refresh_widgets(dashboard) {
		let d = dashboard || frappe.dashboard;
		if (!d) return;

		// Refresh Cards
		if (d.number_card_group) {
			d.number_card_group.widgets_list.forEach(w => {
				if (w.refresh) w.refresh();
			});
		}

		// Refresh Charts
		if (d.chart_group) {
			d.chart_group.widgets_list.forEach(w => {
				if (w.refresh) w.refresh();
			});
		}
		
		frappe.show_alert({ message: __('Dashboard Refreshed'), indicator: 'blue' });
	}
})();
