// Copyright (c) 2026, CU and contributors
// For license information, please see license.txt

frappe.ui.form.on('Exam Plan', {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('View Courses to Map Schema'), () => {
				_csm_open(frm.doc.name, frm.doc.exam_name || frm.doc.name);
			});
		}
	}
});

/* ── Styles ───────────────────────────────────────── */
function _csm_inject_styles() {
	if (document.getElementById('csm-styles')) return;
	const s = document.createElement('style');
	s.id = 'csm-styles';
	s.textContent = `
		.csm-overlay {
			position: fixed; top: 0; left: 0; right: 0; bottom: 0;
			background: #f1f5f9; z-index: 9999;
			overflow-y: auto; display: flex; flex-direction: column;
		}
		.csm-topbar {
			background: #fff;
			border-bottom: 1px solid #e2e8f0;
			padding: 0 24px;
			display: flex; align-items: center; gap: 16px;
			height: 52px;
			position: sticky; top: 0; z-index: 10;
			box-shadow: 0 1px 4px rgba(0,0,0,0.05);
		}
		.csm-back-btn {
			background: none; border: none; cursor: pointer;
			color: #6366f1; font-weight: 600; font-size: 13px;
			padding: 5px 10px; border-radius: 5px;
			display: flex; align-items: center; gap: 5px;
			transition: background 0.15s; white-space: nowrap;
			flex-shrink: 0;
		}
		.csm-back-btn:hover { background: #eef2ff; }
		.csm-breadcrumb {
			font-size: 12.5px; color: #94a3b8;
			display: flex; align-items: center; gap: 5px;
		}
		.csm-breadcrumb span { color: #64748b; }
		.csm-breadcrumb strong { color: #1e293b; }
		.csm-breadcrumb .csm-sep { color: #cbd5e1; }
		.csm-main {
			flex: 1; padding: 24px;
			max-width: 1400px; width: 100%; margin: 0 auto;
		}
		.csm-toolbar {
			display: flex; justify-content: space-between; align-items: center;
			margin-bottom: 14px; gap: 12px;
		}
		.csm-search-wrap { flex: 1; max-width: 520px; position: relative; }
		.csm-search-wrap::before {
			content: '🔍'; position: absolute; left: 11px; top: 50%;
			transform: translateY(-50%); font-size: 13px; pointer-events: none;
		}
		.csm-search {
			width: 100%;
			border: 1px solid #d1d5db; border-radius: 6px;
			padding: 8px 14px 8px 34px; font-size: 13px;
			transition: border-color 0.15s, box-shadow 0.15s;
			box-sizing: border-box;
		}
		.csm-search:focus {
			outline: none; border-color: #6366f1;
			box-shadow: 0 0 0 2px rgba(99,102,241,0.12);
		}
		.csm-btn-group { display: flex; gap: 8px; }
		.csm-btn-map {
			padding: 8px 20px; font-size: 13px; font-weight: 600;
			background: #1e293b; color: #fff; border: none;
			border-radius: 6px; cursor: pointer; transition: background 0.15s;
		}
		.csm-btn-map:hover { background: #334155; }
		.csm-btn-unmap {
			padding: 8px 20px; font-size: 13px; font-weight: 600;
			background: #fff; color: #64748b;
			border: 1px solid #d1d5db; border-radius: 6px;
			cursor: pointer; transition: all 0.15s;
		}
		.csm-btn-unmap:hover { background: #fef2f2; color: #dc2626; border-color: #fca5a5; }
		.csm-count-bar {
			font-size: 12px; color: #64748b;
			margin-bottom: 10px; font-weight: 500;
		}
		.csm-card {
			background: #fff; border-radius: 8px;
			border: 1px solid #e2e8f0;
			box-shadow: 0 1px 4px rgba(0,0,0,0.04);
			overflow: hidden;
		}
		.csm-tbl-wrap { overflow-x: auto; }
		table.csm-tbl {
			width: 100%; border-collapse: collapse; font-size: 13px;
		}
		table.csm-tbl th {
			background: #f8fafc; padding: 11px 14px;
			font-size: 11px; font-weight: 700; color: #64748b;
			text-transform: uppercase; letter-spacing: 0.06em;
			border-bottom: 2px solid #e2e8f0; white-space: nowrap;
			text-align: left;
		}
		table.csm-tbl td {
			padding: 11px 14px; border-bottom: 1px solid #f1f5f9;
			vertical-align: middle; color: #374151;
		}
		table.csm-tbl tr:last-child td { border-bottom: none; }
		table.csm-tbl tbody tr:hover > td { background: #fafbff; }
		table.csm-tbl input[type=checkbox] {
			width: 15px; height: 15px; cursor: pointer; accent-color: #6366f1;
		}
		.csm-course-name { font-weight: 600; color: #1e293b; font-size: 13px; }
		.csm-course-code { font-size: 11px; color: #94a3b8; margin-top: 2px; }
		.csm-badge {
			display: inline-block; font-size: 11.5px;
			padding: 3px 10px; border-radius: 12px; font-weight: 500;
			max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
			vertical-align: middle;
		}
		.csm-badge-eval { background: #dbeafe; color: #1d4ed8; }
		.csm-badge-grade { background: #dcfce7; color: #15803d; }
		.csm-dash { color: #cbd5e1; }
		.csm-empty {
			text-align: center; padding: 48px 16px;
			color: #94a3b8; font-size: 13px;
		}
		.csm-loading { text-align: center; padding: 32px; color: #94a3b8; }
	`;
	document.head.appendChild(s);
}

/* ── Open overlay ─────────────────────────────────── */
function _csm_open(exam_plan, exam_name) {
	_csm_inject_styles();
	$('#csm-overlay').remove();

	const $ov = $(`
		<div class="csm-overlay" id="csm-overlay">
			<div class="csm-topbar">
				<button class="csm-back-btn">&#8592; Back</button>
				<div class="csm-breadcrumb">
					<span>Examination Management</span>
					<span class="csm-sep">/</span>
					<span>Exam Plan</span>
					<span class="csm-sep">/</span>
					<strong>${_esc(exam_name)}</strong>
					<span class="csm-sep">/</span>
					<span>Course Schema</span>
				</div>
			</div>
			<div class="csm-main">
				<div class="csm-toolbar">
					<div class="csm-search-wrap">
						<input type="text" class="csm-search" placeholder="Search by Course Name or Course Code..."/>
					</div>
					<div class="csm-btn-group">
						<button class="csm-btn-map csm-do-map">Map Schema</button>
						<button class="csm-btn-unmap csm-do-unmap">Unmap Schema</button>
					</div>
				</div>
				<div class="csm-count-bar">Loading courses…</div>
				<div class="csm-card">
					<div class="csm-tbl-wrap">
						<table class="csm-tbl">
							<thead>
								<tr>
									<th style="width:40px;"><input type="checkbox" class="csm-chk-all"/></th>
									<th>Course Name</th>
									<th>Credits</th>
									<th>Department</th>
									<th>Enrolled Students</th>
									<th>Evaluation Schema</th>
									<th>Max Marks</th>
									<th>Grade Schema</th>
								</tr>
							</thead>
							<tbody class="csm-tbody">
								<tr><td colspan="8" class="csm-loading">Loading…</td></tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>
	`);

	$('body').append($ov);

	// Back button
	$ov.find('.csm-back-btn').on('click', () => $ov.remove());

	// Select all
	$ov.find('.csm-chk-all').on('change', function () {
		$ov.find('.csm-chk-row').prop('checked', $(this).is(':checked'));
	});

	// Search with debounce
	let _timer = null;
	$ov.find('.csm-search').on('input', function () {
		clearTimeout(_timer);
		_timer = setTimeout(() => _csm_load(exam_plan, $(this).val().trim(), $ov), 400);
	});

	// Map Schema
	$ov.find('.csm-do-map').on('click', () => {
		const sel = _csm_selected($ov);
		if (!sel.length) { frappe.msgprint(__('Select at least one course.')); return; }
		_csm_map_dialog(exam_plan, sel, $ov);
	});

	// Unmap Schema
	$ov.find('.csm-do-unmap').on('click', () => {
		const sel = _csm_selected($ov);
		if (!sel.length) { frappe.msgprint(__('Select at least one course.')); return; }
		frappe.confirm(
			__('Remove schema mapping from {0} selected course(s)?', [sel.length]),
			() => _csm_unmap(exam_plan, sel, $ov)
		);
	});

	_csm_load(exam_plan, '', $ov);
}

/* ── Load & render ────────────────────────────────── */
function _csm_load(exam_plan, search, $ov) {
	$ov.find('.csm-tbody').html('<tr><td colspan="8" class="csm-loading">Loading…</td></tr>');
	frappe.call({
		method: 'slcm.slcm.page.examination_planner.examination_planner.get_courses_for_plan',
		args: { exam_plan, search },
		callback: r => {
			const courses = r.message || [];
			$ov.find('.csm-count-bar').text(`Course Name (${courses.length})`);
			$ov.find('.csm-chk-all').prop('checked', false);
			_csm_render(courses, $ov);
		}
	});
}

function _csm_render(courses, $ov) {
	const $tbody = $ov.find('.csm-tbody');
	if (!courses.length) {
		$tbody.html('<tr><td colspan="8" class="csm-empty">No courses found.</td></tr>');
		return;
	}
	$tbody.empty();
	courses.forEach(c => {
		const ev = c.evaluation_schema
			? `<span class="csm-badge csm-badge-eval" title="${_esc(c.evaluation_schema)}">${_esc(c.evaluation_schema)}</span>`
			: '<span class="csm-dash">--</span>';
		const gr = c.grade_schema
			? `<span class="csm-badge csm-badge-grade" title="${_esc(c.grade_schema)}">${_esc(c.grade_schema)}</span>`
			: '<span class="csm-dash">--</span>';
		$tbody.append(`
			<tr data-course="${_esc(c.name)}">
				<td><input type="checkbox" class="csm-chk-row" data-course="${_esc(c.name)}"/></td>
				<td>
					<div class="csm-course-name">${_esc(c.course_name || c.name)}</div>
					${c.course_code ? `<div class="csm-course-code">${_esc(c.course_code)}</div>` : ''}
				</td>
				<td>${c.credit_value != null ? c.credit_value : '<span class="csm-dash">--</span>'}</td>
				<td>${c.department_name ? _esc(c.department_name) : '<span class="csm-dash">--</span>'}</td>
				<td><span class="csm-dash">--</span></td>
				<td>${ev}</td>
				<td>${c.max_marks !== '' && c.max_marks != null ? c.max_marks : '<span class="csm-dash">--</span>'}</td>
				<td>${gr}</td>
			</tr>
		`);
	});
}

function _csm_selected($ov) {
	const sel = [];
	$ov.find('.csm-chk-row:checked').each(function () { sel.push($(this).data('course')); });
	return sel;
}

/* ── Map dialog ───────────────────────────────────── */
function _csm_map_dialog(exam_plan, selected, $ov) {
	const d = new frappe.ui.Dialog({
		title: __('Map Schema — {0} Course(s)', [selected.length]),
		size: 'small',
		fields: [
			{
				fieldname: 'evaluation_schema',
				fieldtype: 'Link',
				label: __('Evaluation Schema'),
				options: 'Evaluation Schema',
			},
			{
				fieldname: 'grade_schema',
				fieldtype: 'Link',
				label: __('Grade Schema'),
				options: 'Grading Schema',
			},
		],
		primary_action_label: __('Apply'),
		primary_action(values) {
			if (!values.evaluation_schema && !values.grade_schema) {
				frappe.msgprint(__('Please select at least one schema.'));
				return;
			}
			const assignments = selected.map(course => ({
				course,
				evaluation_schema: values.evaluation_schema || null,
				grade_schema: values.grade_schema || null,
			}));
			frappe.call({
				method: 'slcm.slcm.page.examination_planner.examination_planner.save_course_schema',
				args: { exam_plan, assignments: JSON.stringify(assignments) },
				callback: () => {
					d.hide();
					frappe.show_alert({ message: __('Schema mapped successfully.'), indicator: 'green' });
					_csm_load(exam_plan, $ov.find('.csm-search').val().trim(), $ov);
				}
			});
		}
	});
	d.show();
}

/* ── Unmap ────────────────────────────────────────── */
function _csm_unmap(exam_plan, selected, $ov) {
	frappe.call({
		method: 'slcm.slcm.page.examination_planner.examination_planner.unmap_course_schema',
		args: { exam_plan, courses: JSON.stringify(selected) },
		callback: () => {
			frappe.show_alert({ message: __('Schema unmapped.'), indicator: 'green' });
			_csm_load(exam_plan, $ov.find('.csm-search').val().trim(), $ov);
		}
	});
}

/* ── Utility ─────────────────────────────────────── */
function _esc(s) {
	if (!s) return '';
	return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
