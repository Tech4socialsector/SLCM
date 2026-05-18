// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on('Grading Schema', {
	refresh(frm) {
		_gs_inject_styles();
		_gs_hide_native(frm);
		_gs_ensure_area(frm);
		_gs_render(frm);
	}
});

/* ── Styles ───────────────────────────────────────── */
function _gs_inject_styles() {
	if (document.getElementById('gs-form-styles')) return;
	const s = document.createElement('style');
	s.id = 'gs-form-styles';
	s.textContent = `
		#gs-dynamic-sections { padding: 4px 0 16px; }

		#gs-dynamic-sections .gs-card {
			margin-bottom: 20px;
			border: 1px solid #e2e8f0;
			border-radius: 8px;
			overflow: hidden;
			background: #fff;
			box-shadow: 0 1px 4px rgba(0,0,0,0.06);
		}
		#gs-dynamic-sections .gs-card-hdr {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 12px 18px;
			background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
			border-bottom: 1px solid #e2e8f0;
		}
		#gs-dynamic-sections .gs-hdr-title {
			font-weight: 700;
			font-size: 13.5px;
			color: #1e293b;
			display: flex;
			align-items: center;
			gap: 6px;
		}
		#gs-dynamic-sections .gs-info-icon {
			color: #94a3b8;
			font-size: 13px;
			cursor: help;
		}
		#gs-dynamic-sections .gs-hdr-actions {
			display: flex;
			align-items: center;
			gap: 8px;
		}

		#gs-dynamic-sections .gs-tbl-wrap { overflow-x: auto; }
		#gs-dynamic-sections table.gs-tbl {
			width: 100%;
			margin: 0;
			border-collapse: collapse;
			font-size: 12.5px;
		}
		#gs-dynamic-sections table.gs-tbl th {
			background: #f8fafc;
			padding: 8px 12px;
			font-weight: 600;
			color: #64748b;
			font-size: 10.5px;
			text-transform: uppercase;
			letter-spacing: 0.06em;
			border-bottom: 2px solid #e2e8f0;
			white-space: nowrap;
		}
		#gs-dynamic-sections table.gs-tbl th.gs-range-hdr { text-align: center; }
		#gs-dynamic-sections table.gs-tbl th.gs-sub-hdr {
			font-size: 9.5px;
			color: #94a3b8;
			font-weight: 500;
			letter-spacing: 0.03em;
			text-transform: none;
			background: #fafbfc;
			padding-top: 4px;
			padding-bottom: 6px;
			border-bottom: 1px solid #e2e8f0;
		}
		#gs-dynamic-sections table.gs-tbl td {
			padding: 7px 8px;
			border-bottom: 1px solid #f1f5f9;
			vertical-align: middle;
		}
		#gs-dynamic-sections table.gs-tbl tr:last-child td { border-bottom: none; }
		#gs-dynamic-sections table.gs-tbl tbody tr:hover > td { background: #fafbff; }

		#gs-dynamic-sections .gs-inp {
			width: 100%;
			border: 1px solid #d1d5db;
			border-radius: 5px;
			padding: 5px 8px;
			font-size: 12px;
			color: #1f2937;
			background: #fff;
			box-sizing: border-box;
			transition: border-color 0.15s, box-shadow 0.15s;
		}
		#gs-dynamic-sections .gs-inp:focus {
			outline: none;
			border-color: #6366f1;
			box-shadow: 0 0 0 2px rgba(99,102,241,0.14);
		}
		#gs-dynamic-sections .gs-op-sel {
			border: 1px solid #e0e7ff;
			border-radius: 4px;
			padding: 4px 6px;
			font-size: 11.5px;
			font-weight: 700;
			color: #6366f1;
			background: #eef2ff;
			cursor: pointer;
			min-width: 38px;
			flex-shrink: 0;
			text-align: center;
		}
		#gs-dynamic-sections .gs-op-sel:focus { outline: none; border-color: #6366f1; }
		#gs-dynamic-sections .gs-range-cell {
			display: flex;
			align-items: center;
			gap: 5px;
		}

		#gs-dynamic-sections .gs-add-btn {
			font-size: 12px;
			font-weight: 500;
			padding: 5px 14px;
			border: 1px solid #6366f1;
			border-radius: 5px;
			background: #fff;
			color: #6366f1;
			cursor: pointer;
			transition: all 0.15s;
		}
		#gs-dynamic-sections .gs-add-btn:hover { background: #6366f1; color: #fff; }
		#gs-dynamic-sections .gs-dup-btn {
			font-size: 12px;
			font-weight: 500;
			padding: 5px 12px;
			border: 1px solid #e2e8f0;
			border-radius: 5px;
			background: #fff;
			color: #475569;
			cursor: pointer;
			display: flex;
			align-items: center;
			gap: 5px;
			transition: all 0.15s;
		}
		#gs-dynamic-sections .gs-dup-btn:hover { background: #f8fafc; border-color: #94a3b8; }
		#gs-dynamic-sections .gs-del-btn {
			background: none;
			border: none;
			color: #ef4444;
			cursor: pointer;
			font-size: 17px;
			line-height: 1;
			padding: 2px 7px;
			border-radius: 4px;
			opacity: 0.55;
			transition: all 0.15s;
		}
		#gs-dynamic-sections .gs-del-btn:hover { opacity: 1; background: #fee2e2; }

		/* Toggle switch */
		#gs-dynamic-sections .gs-toggle-wrap {
			display: inline-flex;
			align-items: center;
			gap: 0;
			cursor: pointer;
			margin: 0;
		}
		#gs-dynamic-sections .gs-toggle-inp { display: none !important; }
		#gs-dynamic-sections .gs-toggle-track {
			width: 40px; height: 22px;
			background: #d1d5db;
			border-radius: 11px;
			position: relative;
			transition: background 0.2s;
			flex-shrink: 0;
		}
		#gs-dynamic-sections .gs-toggle-track::after {
			content: '';
			position: absolute;
			top: 3px; left: 3px;
			width: 16px; height: 16px;
			background: #fff;
			border-radius: 50%;
			transition: left 0.2s;
			box-shadow: 0 1px 3px rgba(0,0,0,0.22);
		}
		#gs-dynamic-sections .gs-toggle-inp:checked + .gs-toggle-track { background: #22c55e; }
		#gs-dynamic-sections .gs-toggle-inp:checked + .gs-toggle-track::after { left: 21px; }

		#gs-dynamic-sections .gs-reexam-body { border-top: 1px solid #e2e8f0; }
		#gs-dynamic-sections .gs-reexam-actions {
			display: flex;
			justify-content: flex-end;
			gap: 8px;
			padding: 10px 16px;
			border-bottom: 1px solid #f1f5f9;
			background: #fafbfc;
		}

		/* Eligibility Criteria */
		#gs-dynamic-sections .gs-criteria-section {
			padding: 12px 16px;
			border-bottom: 1px solid #e2e8f0;
			background: #f8fafc;
		}
		#gs-dynamic-sections .gs-criteria-label {
			font-size: 11.5px;
			font-weight: 600;
			color: #475569;
			text-transform: uppercase;
			letter-spacing: 0.06em;
			margin-bottom: 8px;
		}
		#gs-dynamic-sections .gs-criteria-tags {
			display: flex;
			flex-wrap: wrap;
			gap: 6px;
			margin-bottom: 8px;
			min-height: 28px;
		}
		#gs-dynamic-sections .gs-criteria-tag {
			display: inline-flex;
			align-items: center;
			gap: 5px;
			background: #eef2ff;
			border: 1px solid #c7d2fe;
			border-radius: 20px;
			padding: 3px 10px 3px 12px;
			font-size: 12px;
			font-weight: 500;
			color: #4338ca;
		}
		#gs-dynamic-sections .gs-criteria-tag-del {
			background: none;
			border: none;
			cursor: pointer;
			color: #818cf8;
			font-size: 15px;
			line-height: 1;
			padding: 0;
			display: flex;
			align-items: center;
			transition: color 0.12s;
		}
		#gs-dynamic-sections .gs-criteria-tag-del:hover { color: #ef4444; }
		#gs-dynamic-sections .gs-criteria-input-row {
			display: flex;
			gap: 6px;
			align-items: center;
		}
		#gs-dynamic-sections .gs-criteria-inp {
			border: 1px solid #d1d5db;
			border-radius: 5px;
			padding: 5px 10px;
			font-size: 12px;
			color: #1f2937;
			background: #fff;
			width: 160px;
			transition: border-color 0.15s, box-shadow 0.15s;
		}
		#gs-dynamic-sections .gs-criteria-inp:focus {
			outline: none;
			border-color: #6366f1;
			box-shadow: 0 0 0 2px rgba(99,102,241,0.14);
		}
		#gs-dynamic-sections .gs-criteria-add-btn {
			font-size: 12px;
			font-weight: 500;
			padding: 5px 12px;
			border: 1px solid #6366f1;
			border-radius: 5px;
			background: #fff;
			color: #6366f1;
			cursor: pointer;
			transition: all 0.15s;
			white-space: nowrap;
		}
		#gs-dynamic-sections .gs-criteria-add-btn:hover { background: #6366f1; color: #fff; }
	`;
	document.head.appendChild(s);
}

/* ── Helpers ──────────────────────────────────────── */
function _gs_hide_native(frm) {
	frm.toggle_display(
		['section_break_grades', 'grades', 'use_reexam_composition', 'section_break_reexam', 'reexam_eligibility_criteria', 'reexam_grades'],
		false
	);
}

function _gs_ensure_area(frm) {
	if (frm.$wrapper.find('#gs-dynamic-sections').length) return;
	const $ref = frm.fields_dict['grades']
		? frm.fields_dict['grades'].$wrapper.closest('.form-section')
		: null;
	const $area = $('<div id="gs-dynamic-sections"></div>');
	if ($ref && $ref.length) {
		$area.insertAfter($ref);
	} else {
		frm.$wrapper.find('.form-layout').append($area);
	}
}

function _gs_render(frm) {
	const $area = frm.$wrapper.find('#gs-dynamic-sections');
	$area.empty();
	_gs_render_regular(frm, $area);
	_gs_render_reexam(frm, $area);
}

/* ── Shared thead HTML ────────────────────────────── */
function _gs_thead_html() {
	return `
		<thead>
			<tr>
				<th style="min-width:90px;">Grade</th>
				<th style="min-width:160px;">Qualitative Meaning</th>
				<th colspan="2" class="gs-range-hdr" style="min-width:240px;">Marks Range</th>
				<th style="min-width:80px;">Grade Point</th>
				<th style="min-width:60px;text-align:center;">Failed</th>
				<th style="min-width:110px;text-align:center;">Consider for SGPA</th>
				<th style="width:36px;"></th>
			</tr>
			<tr>
				<th class="gs-sub-hdr"></th>
				<th class="gs-sub-hdr"></th>
				<th class="gs-sub-hdr" style="min-width:110px;">From</th>
				<th class="gs-sub-hdr" style="min-width:110px;">To</th>
				<th class="gs-sub-hdr"></th>
				<th class="gs-sub-hdr"></th>
				<th class="gs-sub-hdr"></th>
				<th class="gs-sub-hdr"></th>
			</tr>
		</thead>
	`;
}

/* ── Regular Section ──────────────────────────────── */
function _gs_render_regular(frm, $area) {
	const $sec = $(`
		<div class="gs-card">
			<div class="gs-card-hdr">
				<div class="gs-hdr-title">
					Regular/Makeup Exam Composition
					<span class="gs-info-icon" title="Defines how marks map to grades for regular and makeup examinations">ⓘ</span>
				</div>
				<div class="gs-hdr-actions">
					<button class="gs-add-btn gs-add-row">+ Add New</button>
				</div>
			</div>
			<div class="gs-tbl-wrap">
				<table class="gs-tbl">
					${_gs_thead_html()}
					<tbody class="gs-tbody"></tbody>
				</table>
			</div>
		</div>
	`);
	$area.append($sec);

	const $tbody = $sec.find('.gs-tbody');
	const rows = frm.doc.grades || [];
	(rows.length ? rows : [{}]).forEach(r => _gs_add_grade_row(frm, $tbody, 'grades', r));

	$sec.on('click', '.gs-add-row', () => _gs_add_grade_row(frm, $tbody, 'grades', {}));
}

/* ── Re-Exam Section ──────────────────────────────── */
function _gs_render_reexam(frm, $area) {
	const use_reexam = !!frm.doc.use_reexam_composition;

	const $sec = $(`
		<div class="gs-card">
			<div class="gs-card-hdr">
				<div class="gs-hdr-title">
					Re Exam Composition
					<span class="gs-info-icon" title="Define a separate grade composition for re-examinations">ⓘ</span>
				</div>
				<div class="gs-hdr-actions">
					<label class="gs-toggle-wrap" title="Enable Re Exam Composition">
						<input type="checkbox" class="gs-toggle-inp gs-reexam-chk" ${use_reexam ? 'checked' : ''}/>
						<span class="gs-toggle-track"></span>
					</label>
				</div>
			</div>
			<div class="gs-reexam-body" style="${use_reexam ? '' : 'display:none;'}"></div>
		</div>
	`);
	$area.append($sec);

	const $body = $sec.find('.gs-reexam-body');
	if (use_reexam) _gs_build_reexam_body(frm, $body);

	$sec.on('change', '.gs-reexam-chk', function () {
		const checked = $(this).is(':checked');
		frm.doc.use_reexam_composition = checked ? 1 : 0;
		if (checked) {
			$body.show();
			if (!$body.find('table').length) _gs_build_reexam_body(frm, $body);
		} else {
			$body.hide();
		}
		frm.dirty();
	});
}

function _gs_build_reexam_body(frm, $body) {
	const $inner = $(`
		<div>
			<div class="gs-criteria-section">
				<div class="gs-criteria-label">
					Eligible for Re Exam
					<span class="gs-info-icon" title="Grades that make a student eligible for re-examination enrollment" style="font-weight:400;text-transform:none;letter-spacing:0;">ⓘ</span>
				</div>
				<div class="gs-criteria-tags"></div>
				<div class="gs-criteria-input-row">
					<input type="text" class="gs-criteria-inp" placeholder="e.g. Fail, Absent, FA…"/>
					<button class="gs-criteria-add-btn">+ Add Criteria</button>
				</div>
			</div>
			<div class="gs-reexam-actions">
				<button class="gs-dup-btn gs-do-dup">
					<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
					</svg>
					Duplicate Regular
				</button>
				<button class="gs-add-btn gs-add-row">+ Add New</button>
			</div>
			<div class="gs-tbl-wrap">
				<table class="gs-tbl">
					${_gs_thead_html()}
					<tbody class="gs-tbody"></tbody>
				</table>
			</div>
		</div>
	`);
	$body.append($inner);

	// Render existing criteria tags
	const $tags = $inner.find('.gs-criteria-tags');
	(frm.doc.reexam_eligibility_criteria || []).forEach(r => _gs_add_criteria_tag(frm, $tags, r.name, r.criteria));

	// Add criteria on button click or Enter
	const $inp = $inner.find('.gs-criteria-inp');
	const doAdd = () => {
		const raw = $inp.val().trim();
		if (!raw) return;
		const val = format_superscript_subscript(raw);
		const child = frappe.model.add_child(frm.doc, 'Grading Schema Reexam Criteria', 'reexam_eligibility_criteria');
		child.criteria = val;
		_gs_add_criteria_tag(frm, $tags, child.name, val);
		$inp.val('');
		frm.dirty();
	};
	$inner.find('.gs-criteria-add-btn').on('click', doAdd);
	$inp.on('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); doAdd(); } });

	const $tbody = $inner.find('.gs-tbody');
	const rows = frm.doc.reexam_grades || [];
	(rows.length ? rows : [{}]).forEach(r => _gs_add_grade_row(frm, $tbody, 'reexam_grades', r));

	$inner.on('click', '.gs-add-row', () => _gs_add_grade_row(frm, $tbody, 'reexam_grades', {}));
	$inner.on('click', '.gs-do-dup', () => _gs_dup_regular(frm, $tbody));
}

function _gs_add_criteria_tag(frm, $tags, childName, value) {
	const $tag = $(`
		<span class="gs-criteria-tag" data-name="${_esc_gs(childName)}">
			${_esc_gs(value)}
			<button class="gs-criteria-tag-del" title="Remove">×</button>
		</span>
	`);
	$tag.find('.gs-criteria-tag-del').on('click', () => {
		frm.doc.reexam_eligibility_criteria = (frm.doc.reexam_eligibility_criteria || []).filter(r => r.name !== childName);
		$tag.remove();
		frm.dirty();
	});
	$tags.append($tag);
}

/* ── Grade Row ────────────────────────────────────── */
function _gs_add_grade_row(frm, $tbody, field, data) {
	let frow = data.name ? (frm.doc[field] || []).find(r => r.name === data.name) : null;
	if (!frow) {
		frow = frappe.model.add_child(frm.doc, 'Grading Schema Component', field);
	}
	const fn = frow.name;

	const from_op = data.from_operator || frow.from_operator || '>=';
	const to_op   = data.to_operator   || frow.to_operator   || '<';
	const consider_sgpa = (data.consider_for_sgpa !== undefined && data.consider_for_sgpa !== null)
		? data.consider_for_sgpa : (frow.consider_for_sgpa !== undefined ? frow.consider_for_sgpa : 1);

	// Immediately write provided data into the doc row so Frappe validation sees it
	if (data.grade !== undefined)               frow.grade               = data.grade;
	if (data.qualitative_meaning !== undefined) frow.qualitative_meaning = data.qualitative_meaning;
	frow.from_operator = from_op;
	if (data.marks_from !== undefined && data.marks_from !== null) frow.marks_from = data.marks_from;
	frow.to_operator   = to_op;
	if (data.marks_to !== undefined && data.marks_to !== null)     frow.marks_to   = data.marks_to;
	if (data.grade_point !== undefined && data.grade_point !== null) frow.grade_point = data.grade_point;
	if (data.failed !== undefined)              frow.failed              = data.failed;
	frow.consider_for_sgpa = consider_sgpa;

	const $row = $(`
		<tr data-fn="${fn}">
			<td style="min-width:90px;">
				<input name="grade" class="gs-inp" value="${_esc_gs(data.grade || frow.grade || '')}" placeholder="e.g. A+"/>
			</td>
			<td style="min-width:150px;">
				<input name="qual" class="gs-inp" value="${_esc_gs(data.qualitative_meaning || frow.qualitative_meaning || '')}" placeholder="Qualitative Meaning"/>
			</td>
			<td style="min-width:120px;">
				<div class="gs-range-cell">
					<select name="from_op" class="gs-op-sel">
						<option value=">=" ${from_op === '>=' ? 'selected' : ''}>&gt;=</option>
						<option value=">"  ${from_op === '>'  ? 'selected' : ''}>&gt;</option>
					</select>
					<input name="marks_from" type="number" class="gs-inp"
						value="${data.marks_from !== undefined && data.marks_from !== null ? data.marks_from : (frow.marks_from || '')}"
						placeholder="0"/>
				</div>
			</td>
			<td style="min-width:120px;">
				<div class="gs-range-cell">
					<select name="to_op" class="gs-op-sel">
						<option value="<=" ${to_op === '<=' ? 'selected' : ''}>&lt;=</option>
						<option value="<"  ${to_op === '<'  ? 'selected' : ''}>&lt;</option>
					</select>
					<input name="marks_to" type="number" class="gs-inp"
						value="${data.marks_to !== undefined && data.marks_to !== null ? data.marks_to : (frow.marks_to || '')}"
						placeholder="0"/>
				</div>
			</td>
			<td style="min-width:80px;">
				<input name="grade_point" type="number" class="gs-inp"
					value="${data.grade_point !== undefined && data.grade_point !== null ? data.grade_point : (frow.grade_point || '')}"
					placeholder="0"/>
			</td>
			<td style="text-align:center;min-width:60px;">
				<input type="checkbox" name="failed" ${(data.failed || frow.failed) ? 'checked' : ''}
					style="width:16px;height:16px;cursor:pointer;accent-color:#ef4444;"/>
			</td>
			<td style="text-align:center;min-width:100px;">
				<input type="checkbox" name="consider_for_sgpa" ${consider_sgpa ? 'checked' : ''}
					style="width:16px;height:16px;cursor:pointer;accent-color:#6366f1;"/>
			</td>
			<td style="width:36px;">
				<button class="gs-del-btn gs-del" title="Remove row">×</button>
			</td>
		</tr>
	`);
	$tbody.append($row);

	const sync = () => {
		const raw_grade = $row.find('[name=grade]').val();
		const fmt = format_superscript_subscript(raw_grade || '');
		if (fmt !== raw_grade) $row.find('[name=grade]').val(fmt);

		const r = (frm.doc[field] || []).find(x => x.name === fn);
		if (!r) return;
		r.grade               = $row.find('[name=grade]').val();
		r.qualitative_meaning = $row.find('[name=qual]').val();
		r.from_operator       = $row.find('[name=from_op]').val();
		r.marks_from          = parseFloat($row.find('[name=marks_from]').val()) || 0;
		r.to_operator         = $row.find('[name=to_op]').val();
		r.marks_to            = parseFloat($row.find('[name=marks_to]').val()) || 0;
		r.grade_point         = parseFloat($row.find('[name=grade_point]').val()) || 0;
		r.failed              = $row.find('[name=failed]').is(':checked') ? 1 : 0;
		r.consider_for_sgpa   = $row.find('[name=consider_for_sgpa]').is(':checked') ? 1 : 0;
		frm.dirty();
	};

	$row.find('input, select').on('change input', sync);
	$row.on('click', '.gs-del', () => {
		frm.doc[field] = (frm.doc[field] || []).filter(x => x.name !== fn);
		$row.remove();
		frm.dirty();
	});
}

/* ── Duplicate Regular → Re Exam ─────────────────── */
function _gs_dup_regular(frm, $tbody) {
	frm.doc.reexam_grades = [];
	$tbody.empty();
	const src = frm.doc.grades || [];
	(src.length ? src : [{}]).forEach(r => {
		_gs_add_grade_row(frm, $tbody, 'reexam_grades', {
			grade:               r.grade,
			qualitative_meaning: r.qualitative_meaning,
			from_operator:       r.from_operator || '>=',
			marks_from:          r.marks_from,
			to_operator:         r.to_operator || '<',
			marks_to:            r.marks_to,
			grade_point:         r.grade_point,
			failed:              r.failed,
			consider_for_sgpa:   r.consider_for_sgpa !== undefined ? r.consider_for_sgpa : 1,
		});
	});
	frm.dirty();
}

/* ── Utility ─────────────────────────────────────── */
function _esc_gs(s) {
	if (!s) return '';
	return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function format_superscript_subscript(text) {
	const sup_map = {
		'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
		'5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
		'+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
		'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ',
		'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ',
		'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ',
		'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
		'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ'
	};
	const sub_map = {
		'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
		'5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
		'+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
		'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
		'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
		'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
		'v': 'ᵥ', 'x': 'ₓ'
	};

	text = text.replace(/<sup>(.*?)<\/sup>/gi, (m, p1) => Array.from(p1).map(c => sup_map[c] || c).join(''));
	text = text.replace(/<sub>(.*?)<\/sub>/gi, (m, p1) => Array.from(p1).map(c => sub_map[c] || c).join(''));
	text = text.replace(/([A-Z0-9a-z])\+/g, '$1⁺');
	text = text.replace(/([A-Z0-9a-z])-/g, '$1⁻');

	let result = '';
	for (let i = 0; i < text.length; i++) {
		if (text[i] === '^' && i + 1 < text.length && sup_map[text[i + 1]]) {
			result += sup_map[text[i + 1]]; i++;
		} else if (text[i] === '_' && i + 1 < text.length && sub_map[text[i + 1]]) {
			result += sub_map[text[i + 1]]; i++;
		} else {
			result += text[i];
		}
	}
	return result;
}
