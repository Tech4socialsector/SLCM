// Copyright (c) 2026, CU and contributors
// For license information, please see license.txt

frappe.ui.form.on('Evaluation Schema', {
	setup(frm) {
		frm._ep_components = null;
		frm._ep_atypes = null;
	},

	refresh(frm) {
		_inject_styles();
		_hide_flat_sections(frm);
		_ensure_dyn_area(frm);
		_load_and_render(frm);
	},

	total_marks(frm) {}
});

frappe.ui.form.on('Evaluation Schema Component', {
	component(frm) { _load_and_render(frm); },

	label(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.component) return;
		const ci = (frm._ep_components || []).find(c => c.name === row.component);
		const comp_name = ci ? ci.component_name : row.component;
		const lbl = row.label || comp_name;
		const ctype = _comp_type(frm, row.component);
		const title = (ctype === 'Re Exam' || ctype === 'Makeup')
			? `${comp_name} | ${lbl}`
			: lbl;
		frm.$wrapper.find(`.es-sub-section[data-comp="${row.component}"] .es-sect-title`).text(title);
	},

	effective_max_marks(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row.component) {
			frm.$wrapper.find(`.es-sub-section[data-comp="${row.component}"] .es-assess-eq`).text(row.effective_max_marks || 0);
			const $sec = frm.$wrapper.find(`.es-sub-section[data-comp="${row.component}"]`);
			if ($sec.length) _upd_assess_sum($sec);
		}
	},

	schema_components_remove(frm) { _load_and_render(frm); }
});

/* ── Styles ───────────────────────────────────────── */

function _inject_styles() {
	if (document.getElementById('es-form-styles')) return;
	const s = document.createElement('style');
	s.id = 'es-form-styles';
	s.textContent = `
		#es-dynamic-sections {
			padding: 4px 0 16px;
		}
		#es-dynamic-sections .es-sub-section {
			margin-bottom: 20px;
			border: 1px solid #e2e8f0;
			border-radius: 8px;
			overflow: hidden;
			background: #fff;
			box-shadow: 0 1px 4px rgba(0,0,0,0.06);
		}
		#es-dynamic-sections .es-card-hdr {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 12px 18px;
			background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
			border-bottom: 1px solid #e2e8f0;
		}
		#es-dynamic-sections .es-hdr-left {
			display: flex;
			align-items: center;
			gap: 0;
		}
		#es-dynamic-sections .es-sect-title {
			font-weight: 700;
			font-size: 13.5px;
			color: #1e293b;
			letter-spacing: 0.01em;
		}
		#es-dynamic-sections .es-badge {
			display: inline-block;
			font-size: 10px;
			padding: 2px 9px;
			border-radius: 12px;
			margin-left: 8px;
			font-weight: 600;
			vertical-align: middle;
			letter-spacing: 0.03em;
		}
		#es-dynamic-sections .es-add-btn {
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
		#es-dynamic-sections .es-add-btn:hover {
			background: #6366f1;
			color: #fff;
		}
		#es-dynamic-sections .es-tbl-wrap { overflow-x: auto; }
		#es-dynamic-sections table.es-tbl {
			width: 100%;
			margin: 0;
			border-collapse: collapse;
			font-size: 12.5px;
		}
		#es-dynamic-sections table.es-tbl th {
			background: #f8fafc;
			padding: 9px 12px;
			font-weight: 600;
			color: #64748b;
			font-size: 10.5px;
			text-transform: uppercase;
			letter-spacing: 0.06em;
			border-bottom: 2px solid #e2e8f0;
			white-space: nowrap;
		}
		#es-dynamic-sections table.es-tbl td {
			padding: 8px 10px;
			border-bottom: 1px solid #f1f5f9;
			vertical-align: middle;
		}
		#es-dynamic-sections table.es-tbl tr:last-child td { border-bottom: none; }
		#es-dynamic-sections table.es-tbl tbody tr:hover > td { background: #fafbff; }
		#es-dynamic-sections .es-inp {
			width: 100%;
			min-width: 56px;
			border: 1px solid #d1d5db;
			border-radius: 5px;
			padding: 5px 8px;
			font-size: 12px;
			color: #1f2937;
			background: #fff;
			box-sizing: border-box;
			transition: border-color 0.15s, box-shadow 0.15s;
		}
		#es-dynamic-sections .es-inp:focus {
			outline: none;
			border-color: #6366f1;
			box-shadow: 0 0 0 2px rgba(99,102,241,0.14);
		}
		#es-dynamic-sections .es-inp[readonly] {
			background: #f1f5f9;
			color: #64748b;
			cursor: default;
		}
		#es-dynamic-sections .es-del-btn {
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
		#es-dynamic-sections .es-del-btn:hover { opacity: 1; background: #fee2e2; }
		#es-dynamic-sections .es-sum-bar {
			padding: 9px 18px;
			font-size: 12px;
			border-top: 2px solid #e2e8f0;
			transition: all 0.25s;
			display: flex;
			align-items: center;
			gap: 5px;
			font-weight: 500;
		}
		#es-dynamic-sections .es-subst-toggle-bar {
			padding: 8px 16px;
			cursor: pointer;
			display: flex;
			align-items: center;
			gap: 5px;
			font-size: 12px;
			color: #6366f1;
			font-weight: 600;
			user-select: none;
			border-top: 1px solid #f1f5f9;
			background: #fafbff;
			transition: background 0.15s;
		}
		#es-dynamic-sections .es-subst-toggle-bar:hover { background: #eff0ff; }
		#es-dynamic-sections .es-subst-body {
			padding: 14px 16px 16px;
			background: #fafbff;
			border-top: 1px solid #e0e7ff;
		}
		#es-dynamic-sections .es-subst-grid {
			display: grid;
			grid-template-columns: 2fr 1fr 1fr 1fr;
			gap: 14px;
			margin-bottom: 12px;
		}
		#es-dynamic-sections .es-sf-label {
			display: block;
			font-size: 10.5px;
			font-weight: 700;
			color: #94a3b8;
			text-transform: uppercase;
			letter-spacing: 0.07em;
			margin-bottom: 5px;
		}
		#es-dynamic-sections .es-subst-note {
			font-size: 11px;
			color: #94a3b8;
			line-height: 1.6;
			padding-top: 10px;
			border-top: 1px solid #e0e7ff;
		}
		#es-dynamic-sections .es-subst-note strong {
			color: #64748b;
		}
		#es-dynamic-sections .es-empty-row td {
			text-align: center;
			color: #94a3b8;
			font-style: italic;
			padding: 16px;
		}
	`;
	document.head.appendChild(s);
}

/* ── Private helpers ──────────────────────────────── */

function _hide_flat_sections(frm) {
	frm.toggle_display(
		['section_break_assessments', 'assessment_configs', 'section_break_reexam', 'reexam_configs'],
		false
	);
}

function _ensure_dyn_area(frm) {
	if (frm.$wrapper.find('#es-dynamic-sections').length) return;
	const $comp_sec = frm.fields_dict['schema_components'].$wrapper.closest('.form-section');
	if ($comp_sec.length) {
		$(`<div id="es-dynamic-sections"></div>`).insertAfter($comp_sec);
	} else {
		frm.$wrapper.find('.form-layout').append(`<div id="es-dynamic-sections"></div>`);
	}
}

function _load_and_render(frm) {
	const need_c = !frm._ep_components;
	const need_a = !frm._ep_atypes;
	if (!need_c && !need_a) { _render(frm); return; }

	const calls = [];
	if (need_c) calls.push(new Promise(res => frappe.call({
		method: 'slcm.slcm.page.examination_planner.examination_planner.get_components',
		callback: r => { frm._ep_components = r.message || []; res(); }
	})));
	if (need_a) calls.push(new Promise(res => frappe.call({
		method: 'slcm.slcm.page.examination_planner.examination_planner.get_assessment_types',
		callback: r => { frm._ep_atypes = r.message || []; res(); }
	})));
	Promise.all(calls).then(() => _render(frm));
}

function _comp_type(frm, name) {
	const c = (frm._ep_components || []).find(x => x.name === name);
	return c ? (c.component_type || 'Custom') : 'Custom';
}

function _render(frm) {
	const $area = frm.$wrapper.find('#es-dynamic-sections');
	if (!$area.length) return;
	$area.empty();

	(frm.doc.schema_components || []).filter(r => r.component).forEach(cr => {
		const ctype = _comp_type(frm, cr.component);
		const ci = (frm._ep_components || []).find(c => c.name === cr.component);
		const comp_name = ci ? ci.component_name : cr.component;
		const lbl = cr.label || comp_name;

		if (ctype === 'Re Exam' || ctype === 'Makeup') {
			_render_reexam_sec(frm, $area, cr.component, lbl, ctype, comp_name);
		} else {
			_render_assess_sec(frm, $area, cr.component, lbl, ctype, cr.effective_max_marks || 0);
		}
	});
}

/* ── Badge helper ─────────────────────────────────── */

function _badge(ctype) {
	const map = {
		'Custom':             ['#16a34a', '#dcfce7'],
		'Assessment':         ['#2563eb', '#dbeafe'],
		'Re Exam':            ['#dc2626', '#fee2e2'],
		'Makeup':             ['#d97706', '#fef3c7'],
		'Default Assessment': ['#6b7280', '#f3f4f6'],
	};
	const [color, bg] = map[ctype] || map['Custom'];
	return `<span class="es-badge" style="background:${bg};color:${color};">${ctype || 'Custom'}</span>`;
}

/* ── Assessment section ───────────────────────────── */

function _render_assess_sec(frm, $area, comp, lbl, ctype, eff_marks) {
	const $sec = $(`
		<div class="es-sub-section" data-comp="${comp}">
			<div class="es-card-hdr">
				<div class="es-hdr-left">
					<span class="es-sect-title">${_esc(lbl)}</span>
					${_badge(ctype)}
				</div>
				<button class="es-add-btn es-add-row">+ Add Assessment</button>
			</div>
			<div class="es-tbl-wrap">
				<table class="es-tbl">
					<thead>
						<tr>
							<th style="min-width:130px;">Assessment Type</th>
							<th style="min-width:100px;">Label</th>
							<th style="min-width:90px;">Effective Marks</th>
							<th style="min-width:90px;">Maximum Marks</th>
							<th style="min-width:75px;">Min Marks</th>
							<th style="min-width:90px;">Passing Marks</th>
							<th style="min-width:70px;text-align:center;">Pass/Fail</th>
							<th style="min-width:90px;">Weightage</th>
							<th style="min-width:90px;">Enrollment</th>
							<th style="width:36px;"></th>
						</tr>
					</thead>
					<tbody class="es-tbody"></tbody>
				</table>
			</div>
			<div class="es-sum-bar" style="background:#f8fafc;color:#64748b;border-top-color:#e2e8f0;">
				<span>Sum of effective marks:</span>
				<b class="es-sum">0</b>
				<span style="color:#94a3b8;">/</span>
				<b class="es-assess-eq">${eff_marks}</b>
				<span style="color:#94a3b8;font-size:11px;margin-left:4px;">(component marks)</span>
			</div>
		</div>
	`);
	$area.append($sec);

	const existing = (frm.doc.assessment_configs || []).filter(r => r.component === comp);
	(existing.length ? existing : [{}]).forEach(r => _add_assess_row(frm, $sec, comp, r));
	_upd_assess_sum($sec);

	$sec.on('click', '.es-add-row', () => _add_assess_row(frm, $sec, comp, {}));
}

function _add_assess_row(frm, $sec, comp, data) {
	let frow = data.name
		? (frm.doc.assessment_configs || []).find(r => r.name === data.name)
		: null;
	if (!frow) {
		frow = frappe.model.add_child(frm.doc, 'Schema Assessment Config', 'assessment_configs');
		frow.component = comp;
	}
	const fn = frow.name;

	const at_opts = (frm._ep_atypes || []).map(a =>
		`<option value="${a.name}" ${(data.assessment_type || '') === a.name ? 'selected' : ''}>${a.type_name || a.name}</option>`
	).join('');

	const $row = $(`
		<tr data-fn="${fn}">
			<td>
				<select name="at" class="es-inp" style="min-width:120px;">
					<option value="">— Select —</option>${at_opts}
				</select>
			</td>
			<td><input name="lbl" class="es-inp" value="${_esc(data.label || '')}" placeholder="Label"/></td>
			<td><input name="eff" type="number" class="es-inp" value="${data.effective_marks || ''}" readonly placeholder="Auto"/></td>
			<td><input name="max" type="number" class="es-inp" value="${data.maximum_marks || ''}" placeholder="0"/></td>
			<td><input name="min" type="number" class="es-inp" value="${data.minimum_marks || 0}" placeholder="0"/></td>
			<td><input name="pass" type="number" class="es-inp" value="${data.passing_marks || 0}" placeholder="0"/></td>
			<td style="text-align:center;">
				<input type="checkbox" name="pfail" ${data.consider_for_pass_fail ? 'checked' : ''}
					style="width:16px;height:16px;cursor:pointer;accent-color:#6366f1;"/>
			</td>
			<td>
				<div style="display:flex;align-items:center;gap:3px;">
					<input name="wt" type="number" class="es-inp" value="${data.weightage !== undefined ? data.weightage : 100}" placeholder="100"/>
					<span style="color:#94a3b8;font-size:11px;">%</span>
				</div>
			</td>
			<td>
				<select name="enroll" class="es-inp">
					<option value="Auto" ${(data.enrollment || 'Auto') === 'Auto' ? 'selected' : ''}>Auto</option>
					<option value="Manual" ${data.enrollment === 'Manual' ? 'selected' : ''}>Manual</option>
				</select>
			</td>
			<td><button class="es-del-btn es-del" title="Remove row">×</button></td>
		</tr>
	`);
	$sec.find('.es-tbody').append($row);

	const sync = () => {
		const wt  = parseFloat($row.find('[name=wt]').val()) || 0;
		const max = parseFloat($row.find('[name=max]').val()) || 0;
		const eff = Math.round((wt / 100) * max * 100) / 100;
		$row.find('[name=eff]').val(eff || '');
		const r = (frm.doc.assessment_configs || []).find(x => x.name === fn);
		if (r) {
			r.component               = comp;
			r.assessment_type         = $row.find('[name=at]').val();
			r.label                   = $row.find('[name=lbl]').val();
			r.effective_marks         = eff;
			r.maximum_marks           = max;
			r.minimum_marks           = parseFloat($row.find('[name=min]').val()) || 0;
			r.passing_marks           = parseFloat($row.find('[name=pass]').val()) || 0;
			r.consider_for_pass_fail  = $row.find('[name=pfail]').is(':checked') ? 1 : 0;
			r.weightage               = wt;
			r.enrollment              = $row.find('[name=enroll]').val();
		}
		_upd_assess_sum($sec);
		frm.dirty();
	};

	$row.find('input, select').on('change input', sync);
	$row.on('click', '.es-del', () => {
		frm.doc.assessment_configs = (frm.doc.assessment_configs || []).filter(x => x.name !== fn);
		$row.remove();
		_upd_assess_sum($sec);
		frm.dirty();
	});
}

function _upd_assess_sum($sec) {
	let t = 0;
	$sec.find('.es-tbody tr').each(function () {
		t += parseFloat($(this).find('[name=eff]').val()) || 0;
	});
	t = Math.round(t * 100) / 100;
	$sec.find('.es-sum').text(t);
	const eq = parseFloat($sec.find('.es-assess-eq').text()) || 0;
	const $bar = $sec.find('.es-sum-bar');
	if (eq === 0 && t === 0) {
		$bar.css({ background: '#f8fafc', color: '#64748b', borderTopColor: '#e2e8f0' });
	} else if (t === eq) {
		$bar.css({ background: '#f0fdf4', color: '#15803d', borderTopColor: '#86efac' });
	} else {
		$bar.css({ background: '#fff1f2', color: '#be123c', borderTopColor: '#fda4af' });
	}
}

/* ── Re-Exam section ─────────────────────────────── */

function _render_reexam_sec(frm, $area, comp, lbl, ctype, comp_name) {
	const $sec = $(`
		<div class="es-sub-section" data-comp="${comp}">
			<div class="es-card-hdr">
				<div class="es-hdr-left">
					<span class="es-sect-title">${_esc(comp_name || comp)} | ${_esc(lbl)}</span>
					${_badge(ctype)}
				</div>
				<button class="es-add-btn es-add-row">+ Add</button>
			</div>
			<div class="es-tbl-wrap">
				<table class="es-tbl">
					<thead>
						<tr>
							<th style="min-width:130px;">Assessment Type</th>
							<th style="min-width:100px;">Label</th>
							<th style="min-width:100px;">Maximum Marks</th>
							<th style="min-width:80px;">Min Marks</th>
							<th style="min-width:100px;">Passing Marks</th>
							<th style="min-width:90px;">Enrollment</th>
							<th style="width:36px;"></th>
						</tr>
					</thead>
					<tbody class="es-tbody"></tbody>
				</table>
			</div>
		</div>
	`);
	$area.append($sec);

	const existing = (frm.doc.reexam_configs || []).filter(r => r.component === comp);
	(existing.length ? existing : [{}]).forEach(r => _add_reexam_row(frm, $sec, comp, r));

	$sec.on('click', '.es-add-row', () => _add_reexam_row(frm, $sec, comp, {}));
}

function _add_reexam_row(frm, $sec, comp, data) {
	let frow = data.name
		? (frm.doc.reexam_configs || []).find(r => r.name === data.name)
		: null;
	if (!frow) {
		frow = frappe.model.add_child(frm.doc, 'Schema Reexam Config', 'reexam_configs');
		frow.component = comp;
	}
	const fn = frow.name;

	const at_opts = (frm._ep_atypes || []).map(a =>
		`<option value="${a.name}" ${(data.assessment_type || '') === a.name ? 'selected' : ''}>${a.type_name || a.name}</option>`
	).join('');

	const _non_reexam = (frm.doc.schema_components || []).filter(cr => {
		const _ct = _comp_type(frm, cr.component);
		return _ct !== 'Re Exam' && _ct !== 'Makeup';
	});
	const sub_opts = _non_reexam.map(cr => {
		const _ci = (frm._ep_components || []).find(c => c.name === cr.component);
		const _disp = cr.label || (_ci ? _ci.component_name : cr.component);
		return `<option value="${cr.component}" ${(data.substitute_for || '') === cr.component ? 'selected' : ''}>${_disp}</option>`;
	}).join('');

	const show_sub = data.substitute_for ? '' : 'display:none;';
	const sub_lbl  = data.substitute_for ? 'Hide Substitution Settings ▲' : 'Show Substitution Settings ▼';

	const $main = $(`
		<tr data-fn="${fn}">
			<td>
				<select name="at" class="es-inp" style="min-width:120px;">
					<option value="">— Select —</option>${at_opts}
				</select>
			</td>
			<td><input name="lbl" class="es-inp" value="${_esc(data.label || '')}" placeholder="Label"/></td>
			<td><input name="max" type="number" class="es-inp" value="${data.maximum_marks || ''}" placeholder="0"/></td>
			<td><input name="min" type="number" class="es-inp" value="${data.minimum_marks || 0}" placeholder="0"/></td>
			<td><input name="pass" type="number" class="es-inp" value="${data.passing_marks || 0}" placeholder="0"/></td>
			<td>
				<select name="enroll" class="es-inp">
					<option value="Auto" ${(data.enrollment || 'Manual') === 'Auto' ? 'selected' : ''}>Auto</option>
					<option value="Manual" ${(data.enrollment || 'Manual') === 'Manual' ? 'selected' : ''}>Manual</option>
				</select>
			</td>
			<td><button class="es-del-btn es-del" title="Remove row">×</button></td>
		</tr>
	`);

	const $subst = $(`
		<tr data-fn="${fn}-s" class="es-subst-row">
			<td colspan="7" style="padding:0;">
				<div class="es-subst-toggle-bar es-subst-toggle">${sub_lbl}</div>
				<div class="es-subst-body" style="${show_sub}">
					<div class="es-subst-grid">
						<div>
							<span class="es-sf-label">Substitute For</span>
							<select name="sub_for" class="es-inp">
								<option value="">— Select Component —</option>${sub_opts}
							</select>
						</div>
						<div>
							<span class="es-sf-label">Weightage</span>
							<div style="display:flex;align-items:center;gap:4px;">
								<input name="sub_wt" type="number" class="es-inp" value="${data.substitute_weightage || 100}"/>
								<span style="color:#94a3b8;font-size:11px;white-space:nowrap;">%</span>
							</div>
						</div>
						<div>
							<span class="es-sf-label">Effective Marks</span>
							<input name="eff" class="es-inp" value="${data.effective_marks || ''}" readonly placeholder="Auto"/>
						</div>
						<div>
							<span class="es-sf-label">Substitute Effective Marks</span>
							<input name="sub_eff" class="es-inp" value="${data.effective_marks || ''}" readonly placeholder="Auto"/>
						</div>
					</div>
					<div class="es-subst-note">
						<strong>Note:</strong>
						Substitute exam effective marks must be ≤ the effective maximum marks of assessment.<br>
						If a student is enrolled for this component, marks will be distributed as per the above schema.
					</div>
				</div>
			</td>
		</tr>
	`);

	$sec.find('.es-tbody').append($main).append($subst);

	$subst.on('click', '.es-subst-toggle', () => {
		const $body = $subst.find('.es-subst-body');
		$body.toggle();
		$subst.find('.es-subst-toggle').text(
			$body.is(':visible') ? 'Hide Substitution Settings ▲' : 'Show Substitution Settings ▼'
		);
	});

	const sync = () => {
		const r = (frm.doc.reexam_configs || []).find(x => x.name === fn);
		if (!r) return;
		r.component            = comp;
		r.assessment_type      = $main.find('[name=at]').val();
		r.label                = $main.find('[name=lbl]').val();
		r.maximum_marks        = parseFloat($main.find('[name=max]').val()) || 0;
		r.minimum_marks        = parseFloat($main.find('[name=min]').val()) || 0;
		r.passing_marks        = parseFloat($main.find('[name=pass]').val()) || 0;
		r.enrollment           = $main.find('[name=enroll]').val();
		r.substitute_for       = $subst.find('[name=sub_for]').val() || null;
		r.substitute_weightage = parseFloat($subst.find('[name=sub_wt]').val()) || 100;
		const _sub_cr = (frm.doc.schema_components || []).find(c => c.component === r.substitute_for);
		const _sub_eff_max = _sub_cr ? (_sub_cr.effective_max_marks || 0) : 0;
		const _eff = r.substitute_for
			? Math.round((r.substitute_weightage / 100) * _sub_eff_max * 100) / 100
			: 0;
		r.effective_marks = _eff;
		$subst.find('[name=eff]').val(_eff || '');
		$subst.find('[name=sub_eff]').val(_eff || '');
		frm.dirty();
	};

	$main.find('input, select').on('change input', sync);
	$subst.find('input, select').on('change input', sync);

	$main.on('click', '.es-del', () => {
		frm.doc.reexam_configs = (frm.doc.reexam_configs || []).filter(x => x.name !== fn);
		$main.remove();
		$subst.remove();
		frm.dirty();
	});
}

/* ── Utility ─────────────────────────────────────── */

function _esc(s) {
	if (!s) return '';
	return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
