frappe.pages['examination-result'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Course Results',
		single_column: true,
	});

	// ── State ────────────────────────────────────────────────────────────────
	var state = {
		exam_plan: null,
		department: null,
		course: null,
		overview: null,
		page_num: 1,
		page_length: 20,
		search_query: '',
		exam_types: [],
		popup_timeout: null,
	};

	// ── Render shell ─────────────────────────────────────────────────────────
	var $body = $(page.main);

	$body.html(`
		<div style="padding:16px 20px;">

			<!-- Filter bar -->
			<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:16px;">
				<div style="min-width:200px;flex:1;">
					<label style="display:block;font-size:12px;color:#6c757d;margin-bottom:4px;font-weight:500;">Exam Plan</label>
					<select class="form-control" id="er-exam-plan">
						<option value="">-- Select Exam Plan --</option>
					</select>
				</div>
				<div style="min-width:180px;flex:1;">
					<label style="display:block;font-size:12px;color:#6c757d;margin-bottom:4px;font-weight:500;">Department</label>
					<select class="form-control" id="er-department" disabled>
						<option value="">-- Select Department --</option>
					</select>
				</div>
				<div style="min-width:200px;flex:1;">
					<label style="display:block;font-size:12px;color:#6c757d;margin-bottom:4px;font-weight:500;">Course</label>
					<select class="form-control" id="er-course" disabled>
						<option value="">-- Select Course --</option>
					</select>
				</div>
			</div>

			<!-- Course info panel -->
			<div id="er-overview" style="display:none;margin-bottom:16px;"></div>

			<!-- Search + pagination -->
			<div id="er-list-controls" style="display:none;margin-bottom:10px;">
				<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
					<input type="text" class="form-control" id="er-search"
						placeholder="Search by Registration ID or Name…"
						style="max-width:280px;">
					<div style="margin-left:auto;display:flex;align-items:center;gap:8px;">
						<span id="er-pag-info" style="color:#6c757d;font-size:13px;"></span>
						<button class="btn btn-default btn-sm" id="er-prev">&#8249; Prev</button>
						<button class="btn btn-default btn-sm" id="er-next">Next &#8250;</button>
					</div>
				</div>
			</div>

			<!-- Marks table -->
			<div id="er-table-wrap" style="display:none;overflow-x:auto;"></div>

			<!-- Hover popup -->
			<div id="er-popup" style="
				display:none;position:fixed;z-index:9999;
				background:#fff;border:1px solid #d1d8dd;border-radius:6px;
				box-shadow:0 4px 16px rgba(0,0,0,.15);padding:14px 18px;
				min-width:260px;max-width:340px;pointer-events:none;font-size:13px;">
			</div>
		</div>
	`);

	// Cache refs
	var $ep   = $body.find('#er-exam-plan');
	var $dept = $body.find('#er-department');
	var $crs  = $body.find('#er-course');
	var $ov   = $body.find('#er-overview');
	var $lc   = $body.find('#er-list-controls');
	var $tw   = $body.find('#er-table-wrap');
	var $srch = $body.find('#er-search');
	var $prev = $body.find('#er-prev');
	var $next = $body.find('#er-next');
	var $pi   = $body.find('#er-pag-info');
	var $pop  = $body.find('#er-popup');

	// ── Page action buttons ───────────────────────────────────────────────────
	page.add_inner_button('Sync Students', function () {
		if (!state.course) { frappe.msgprint('Select a course first.'); return; }
		frappe.msgprint('Sync Students — coming soon.');
	});

	page.add_inner_button('Lock Course', function () {
		if (!state.course) { frappe.msgprint('Select a course first.'); return; }
		frappe.confirm('Lock this course? Faculty will lose edit access.', function () {
			frappe.call({
				method: 'slcm.slcm.page.examination_result.examination_result.save_access_settings',
				args: {
					exam_plan: state.exam_plan,
					courses:   JSON.stringify([state.course]),
					settings:  JSON.stringify({ edit_access: 0 }),
				},
				callback: function () {
					frappe.show_alert({ message: 'Course locked.', indicator: 'orange' });
					load_overview();
				},
			});
		});
	});

	page.add_inner_button('Result Moderation', function () {
		frappe.msgprint('Result Moderation — coming soon.');
	});

	// ── Events ───────────────────────────────────────────────────────────────
	$ep.on('change', function () {
		state.exam_plan  = $(this).val();
		state.department = null;
		state.course     = null;
		reset_dept();
		reset_course();
		hide_detail();
		if (state.exam_plan) load_departments();
	});

	$dept.on('change', function () {
		state.department = $(this).val();
		state.course     = null;
		reset_course();
		hide_detail();
		if (state.department) load_courses();
	});

	$crs.on('change', function () {
		state.course   = $(this).val();
		state.page_num = 1;
		hide_detail();
		if (state.course) {
			load_overview();
			load_students();
		}
	});

	$srch.on('input', frappe.utils.debounce(function () {
		state.search_query = $srch.val().trim();
		state.page_num     = 1;
		if (state.course) load_students();
	}, 400));

	$prev.on('click', function () {
		if (state.page_num > 1) { state.page_num--; load_students(); }
	});
	$next.on('click', function () {
		state.page_num++; load_students();
	});

	// ── Data loaders ─────────────────────────────────────────────────────────
	function load_exam_plans() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_exam_plans',
			callback: function (r) {
				$ep.find('option:not(:first)').remove();
				(r.message || []).forEach(function (p) {
					$ep.append('<option value="' + p.name + '">' +
						frappe.utils.escape_html(p.exam_name) + ' (' + p.name + ')</option>');
				});
			},
		});
	}

	function load_departments() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_departments',
			callback: function (r) {
				$dept.find('option:not(:first)').remove();
				(r.message || []).forEach(function (d) {
					$dept.append('<option value="' + d.name + '">' +
						frappe.utils.escape_html(d.department_name) + '</option>');
				});
				$dept.prop('disabled', false);
			},
		});
	}

	function load_courses() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_courses_by_department',
			args: { exam_plan: state.exam_plan, department: state.department },
			callback: function (r) {
				$crs.find('option:not(:first)').remove();
				(r.message || []).forEach(function (c) {
					$crs.append('<option value="' + c.name + '">' +
						frappe.utils.escape_html(c.course_name) +
						' [' + frappe.utils.escape_html(c.course_code || '') + ']</option>');
				});
				$crs.prop('disabled', false);
			},
		});
	}

	function load_overview() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_course_overview',
			args: { exam_plan: state.exam_plan, course: state.course },
			callback: function (r) {
				state.overview = r.message || {};
				render_overview();
				$lc.show();
			},
		});
	}

	function load_students() {
		if (!state.course) return;
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_course_students_with_marks',
			args: {
				exam_plan:   state.exam_plan,
				course:      state.course,
				search:      state.search_query,
				page:        state.page_num,
				page_length: state.page_length,
			},
			callback: function (r) {
				var data      = r.message || {};
				state.exam_types = data.exam_types || [];
				render_students(data.students || [], data.total || 0);
			},
		});
	}

	// ── Renderers ─────────────────────────────────────────────────────────────
	function render_overview() {
		var o = state.overview;
		if (!o) return;

		var lock_badge = o.status === 'LOCKED'
			? '<span class="badge" style="background:#dc3545;color:#fff;padding:3px 8px;font-size:11px;">LOCKED</span>'
			: '<span class="badge" style="background:#28a745;color:#fff;padding:3px 8px;font-size:11px;">UNLOCKED</span>';

		function on_off(val, yes, no) {
			return val
				? '<span style="color:#28a745;font-weight:600;">' + (yes || 'On') + '</span>'
				: '<span style="color:#6c757d;">' + (no || 'Off') + '</span>';
		}

		function info_row(label, value) {
			return '<div><span style="font-size:11px;color:#6c757d;text-transform:uppercase;' +
				'letter-spacing:.5px;">' + label + '</span>' +
				'<div style="font-size:14px;margin-top:2px;">' + value + '</div></div>';
		}

		$ov.html(
			'<div style="background:#fff;border:1px solid #d1d8dd;border-radius:8px;padding:16px 20px;">' +
			'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">' +
			'<h5 style="margin:0;font-size:15px;font-weight:600;">' +
				frappe.utils.escape_html(o.course_name) +
				' <span style="color:#6c757d;font-weight:400;">[' +
				frappe.utils.escape_html(o.course_code || '') + ']</span></h5>' +
			lock_badge + '</div>' +
			'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px 24px;">' +
				info_row('Students', o.student_count) +
				info_row('Credits', o.credit_value || '—') +
				info_row('Evaluation Schema', frappe.utils.escape_html(o.evaluation_schema || '—')) +
				info_row('Grade Schema', frappe.utils.escape_html(o.grade_schema || '—')) +
				info_row('View Access', on_off(o.view_access, 'Enabled', 'Disabled')) +
				info_row('Edit Access', on_off(o.edit_access, 'Enabled', 'Disabled')) +
				info_row('Auto Grade', on_off(o.auto_generate_grade_access, 'Enabled', 'Disabled')) +
				info_row('Student Masking', on_off(o.mask_student_info, 'On', 'Off')) +
			'</div></div>'
		).show();
	}

	function render_students(students, total) {
		var types = state.exam_types;

		// Header row 1: exam type names
		var th1 = '<th rowspan="2" style="vertical-align:middle;background:#f4f5f7;">Student</th>' +
			'<th rowspan="2" style="vertical-align:middle;background:#f4f5f7;">Status</th>';
		types.forEach(function (t) {
			th1 += '<th colspan="3" style="text-align:center;background:#f4f5f7;border-bottom:2px solid #dee2e6;">' +
				frappe.utils.escape_html(t.type_name || t.exam_type) + '</th>';
		});
		th1 += '<th rowspan="2" style="vertical-align:middle;background:#f4f5f7;text-align:center;">Total</th>';

		// Header row 2: sub-columns
		var th2 = '';
		types.forEach(function () {
			th2 += '<th style="font-size:11px;color:#6c757d;white-space:nowrap;">Marks</th>' +
				'<th style="font-size:11px;color:#6c757d;white-space:nowrap;">Reval.</th>' +
				'<th style="font-size:11px;color:#6c757d;white-space:nowrap;">Moderated</th>';
		});

		// Rows
		var rows = '';
		students.forEach(function (s) {
			var color = s.account_status === 'Blocked' ? '#dc3545' :
				s.student_status === 'Dropped' ? '#fd7e14' : '#28a745';
			var marks = '';
			types.forEach(function () {
				marks += '<td style="text-align:center;">—</td><td style="text-align:center;">—</td><td style="text-align:center;">—</td>';
			});
			rows += '<tr class="er-student-row" data-student="' +
				frappe.utils.escape_html(s.student || '') + '" style="cursor:default;">' +
				'<td style="white-space:nowrap;"><span style="font-weight:500;">' +
				frappe.utils.escape_html(s.registration_id || s.student || '') + '</span><br>' +
				'<span style="font-size:11px;color:#6c757d;">' +
				frappe.utils.escape_html(s.student_name || '') + '</span></td>' +
				'<td><span style="color:' + color + ';font-size:12px;font-weight:500;">' +
				frappe.utils.escape_html(s.student_status || 'Active') + '</span></td>' +
				marks +
				'<td style="text-align:center;font-weight:600;">—</td></tr>';
		});

		if (!students.length) {
			rows = '<tr><td colspan="' + (4 + types.length * 3) + '" ' +
				'style="text-align:center;padding:40px;color:#6c757d;">No students found.</td></tr>';
		}

		$tw.html(
			'<table class="table table-bordered" ' +
			'style="border-collapse:collapse;min-width:100%;font-size:13px;">' +
			'<thead><tr>' + th1 + '</tr><tr style="background:#fafbfc;">' + th2 + '</tr></thead>' +
			'<tbody>' + rows + '</tbody></table>'
		).show();

		// Pagination
		var from = (state.page_num - 1) * state.page_length + 1;
		var to   = Math.min(state.page_num * state.page_length, total);
		$pi.text(total ? (from + '–' + to + ' of ' + total) : '0 students');
		$prev.prop('disabled', state.page_num <= 1);
		$next.prop('disabled', to >= total);

		bind_hover();
	}

	// ── Hover popup ───────────────────────────────────────────────────────────
	function bind_hover() {
		$tw.find('.er-student-row')
			.on('mouseenter', function (e) {
				var student = $(this).data('student');
				clearTimeout(state.popup_timeout);
				state.popup_timeout = setTimeout(function () {
					show_popup(student, e.clientX, e.clientY);
				}, 300);
			})
			.on('mouseleave', function () {
				clearTimeout(state.popup_timeout);
				$pop.hide();
			})
			.on('mousemove', function (e) {
				var left = e.clientX + 356 > window.innerWidth ? e.clientX - 356 : e.clientX + 16;
				$pop.css({ top: e.clientY + 8, left: left });
			});
	}

	function show_popup(student, x, y) {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_student_profile',
			args: { student: student },
			callback: function (r) {
				var s    = r.message || {};
				var name = [s.first_name, s.last_name].filter(Boolean).join(' ') || student;

				function prow(label, val) {
					if (!val) return '';
					return '<div style="display:flex;gap:8px;margin-bottom:4px;">' +
						'<span style="color:#6c757d;min-width:85px;">' + label + '</span>' +
						'<span style="font-weight:500;">' + frappe.utils.escape_html(String(val)) + '</span></div>';
				}

				$pop.html(
					'<div style="font-weight:600;font-size:14px;margin-bottom:8px;">' +
					frappe.utils.escape_html(name) + '</div>' +
					prow('Reg. ID',    s.registration_id) +
					prow('Email',      s.official_email_id || s.email) +
					prow('Phone',      s.phone) +
					prow('Programme',  s.cohort_name || s.programme) +
					prow('Batch',      s.batch_year) +
					prow('Intake',     s.intake) +
					prow('Department', s.department) +
					prow('Status',     s.student_status) +
					prow('Account',    s.account_status)
				);
				var left = x + 356 > window.innerWidth ? x - 356 : x + 16;
				$pop.css({ top: y + 8, left: left }).show();
			},
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────
	function reset_dept() {
		$dept.val('').prop('disabled', true).find('option:not(:first)').remove();
	}

	function reset_course() {
		$crs.val('').prop('disabled', true).find('option:not(:first)').remove();
	}

	function hide_detail() {
		$ov.hide().empty();
		$lc.hide();
		$tw.hide().empty();
		$pop.hide();
		$pi.text('');
	}

	// ── Boot ─────────────────────────────────────────────────────────────────
	load_exam_plans();
};
