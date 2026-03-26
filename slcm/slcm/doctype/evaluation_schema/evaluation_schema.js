// Copyright (c) 2026, CU and contributors
// For license information, please see license.txt

frappe.ui.form.on('Evaluation Schema', {
	setup(frm) {
		frm._ep_components = null;
		frm._ep_atypes = null;
	},

	refresh(frm) {
		_hide_flat_sections(frm);
		_ensure_dyn_area(frm);
		_load_and_render(frm);
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Customize Form'), () => {
				frappe.set_route('Form', 'Customize Form', 'Evaluation Schema');
			});
		}
	},

	total_marks(frm) {
		frm.$wrapper.find('#es-dynamic-sections .es-assess-eq').each(function () {
			// individual sections update via effective_max_marks; this updates nothing extra
		});
	}
});

frappe.ui.form.on('Evaluation Schema Component', {
	component(frm) {
		_load_and_render(frm);
	},

	label(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.component) return;
		const ci = (frm._ep_components || []).find(c => c.name === row.component);
		const lbl = row.label || (ci ? ci.component_name : row.component);
		frm.$wrapper.find(`.es-sub-section[data-comp="${row.component}"] .es-sect-title`)
			.text(`${lbl} | ${lbl}`);
	},

	effective_max_marks(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row.component) {
			frm.$wrapper.find(`.es-sub-section[data-comp="${row.component}"] .es-assess-eq`)
				.text(row.effective_max_marks || 0);
			// Recheck color after target changes
			const $sec = frm.$wrapper.find(`.es-sub-section[data-comp="${row.component}"]`);
			if ($sec.length) _upd_assess_sum($sec);
		}
	},

	schema_components_remove(frm) {
		_load_and_render(frm);
	}
});

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
		$(`<div id="es-dynamic-sections" style="padding:0 15px 10px;"></div>`).insertAfter($comp_sec);
	} else {
		frm.$wrapper.find('.form-layout').append(
			`<div id="es-dynamic-sections" style="padding:0 15px 10px;"></div>`
		);
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
		const lbl = cr.label || (ci ? ci.component_name : cr.component);

		if (ctype === 'Re Exam' || ctype === 'Makeup') {
			_render_reexam_sec(frm, $area, cr.component, lbl, ctype);
		} else {
			_render_assess_sec(frm, $area, cr.component, lbl, ctype, cr.effective_max_marks || 0);
		}
	});
}

/* ── Badge helper ─────────────────────────────────── */

function _badge(ctype) {
	const colors = {
		'Custom': '#28a745', 'Assessment': '#28a745',
		'Re Exam': '#e74c3c', 'Makeup': '#e67e22', 'Default Assessment': '#6c757d'
	};
	const bg = colors[ctype] || '#28a745';
	return `<span style="background:${bg};color:#fff;font-size:10px;padding:2px 8px;border-radius:10px;margin-left:6px;">${ctype || 'Custom'}</span>`;
}

/* ── Assessment section (Custom / Internal / External) ── */

function _render_assess_sec(frm, $area, comp, lbl, ctype, eff_marks) {
	const $sec = $(`
		<div class="es-sub-section" data-comp="${comp}"
			style="margin-bottom:16px;border:1px solid #e0e0e0;border-radius:5px;overflow:hidden;">
			<div style="display:flex;justify-content:space-between;align-items:center;
					padding:9px 14px;background:#f7f8fa;border-bottom:1px solid #e0e0e0;">
				<span class="es-sect-title" style="font-weight:600;font-size:13px;">
					${lbl} | ${lbl} ${_badge(ctype)}
				</span>
				<button class="btn btn-xs btn-default es-add-row">+ Add Assessment</button>
			</div>
			<div style="overflow-x:auto;">
				<table class="table table-bordered"
					style="margin:0;font-size:12px;min-width:750px;">
					<thead style="background:#f3f4f6;">
						<tr>
							<th>Assessment Type</th>
							<th>Label</th>
							<th>Effective Marks</th>
							<th>Maximum Marks</th>
							<th>Min Marks</th>
							<th>Passing Marks</th>
							<th style="text-align:center;">Pass/Fail</th>
							<th>Weightage</th>
							<th>Enrollment</th>
							<th></th>
						</tr>
					</thead>
					<tbody class="es-tbody"></tbody>
				</table>
			</div>
			<div class="es-sum-bar" style="padding:6px 14px;font-size:11px;color:#666;
					background:#fafafa;border-top:1px solid #eee;transition:all 0.25s;">
				<b class="es-sum">0</b>
				&nbsp;— Sum of effective marks must equal component marks =
				<b class="es-assess-eq">${eff_marks}</b>
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
				<select name="at" style="width:130px;font-size:11px;padding:2px;">
					<option value="">Select</option>${at_opts}
				</select>
			</td>
			<td><input name="lbl" value="${_esc(data.label || '')}"
				style="width:90px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="eff" type="number" value="${data.effective_marks || ''}" readonly
				style="width:75px;font-size:11px;background:#f5f5f5;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="max" type="number" value="${data.maximum_marks || ''}"
				style="width:75px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="min" type="number" value="${data.minimum_marks || 0}"
				style="width:65px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="pass" type="number" value="${data.passing_marks || 0}"
				style="width:65px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td style="text-align:center;">
				<input type="checkbox" name="pfail" ${data.consider_for_pass_fail ? 'checked' : ''}/>
			</td>
			<td>
				<input name="wt" type="number" value="${data.weightage !== undefined ? data.weightage : 100}"
					style="width:55px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/> %
			</td>
			<td>
				<select name="enroll" style="width:70px;font-size:11px;padding:2px;">
					<option value="Auto" ${(data.enrollment || 'Auto') === 'Auto' ? 'selected' : ''}>Auto</option>
					<option value="Manual" ${data.enrollment === 'Manual' ? 'selected' : ''}>Manual</option>
				</select>
			</td>
			<td>
				<button class="btn btn-xs es-del" style="color:#c00;padding:1px 6px;">×</button>
			</td>
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
			r.component          = comp;
			r.assessment_type    = $row.find('[name=at]').val();
			r.label              = $row.find('[name=lbl]').val();
			r.effective_marks    = eff;
			r.maximum_marks      = max;
			r.minimum_marks      = parseFloat($row.find('[name=min]').val()) || 0;
			r.passing_marks      = parseFloat($row.find('[name=pass]').val()) || 0;
			r.consider_for_pass_fail = $row.find('[name=pfail]').is(':checked') ? 1 : 0;
			r.weightage          = wt;
			r.enrollment         = $row.find('[name=enroll]').val();
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
	$sec.find('.es-sum').text(t);
	const eq = parseFloat($sec.find('.es-assess-eq').text()) || 0;
	const $bar = $sec.find('.es-sum-bar');
	if (eq === 0 && t === 0) {
		$bar.css({ background: '#fafafa', color: '#666', borderTopColor: '#eee' });
	} else if (t === eq) {
		$bar.css({ background: '#d1fae5', color: '#065f46', borderTopColor: '#6ee7b7' });
	} else {
		$bar.css({ background: '#fee2e2', color: '#991b1b', borderTopColor: '#fca5a5' });
	}
}

/* ── Re-Exam section ─────────────────────────────── */

function _render_reexam_sec(frm, $area, comp, lbl, ctype) {
	const bg = ctype === 'Makeup' ? '#e67e22' : '#e74c3c';
	const $sec = $(`
		<div class="es-sub-section" data-comp="${comp}"
			style="margin-bottom:16px;border:1px solid #e0e0e0;border-radius:5px;overflow:hidden;">
			<div style="display:flex;justify-content:space-between;align-items:center;
					padding:9px 14px;background:#f7f8fa;border-bottom:1px solid #e0e0e0;">
				<span class="es-sect-title" style="font-weight:600;font-size:13px;">
					${lbl} | ${lbl}
					<span style="background:${bg};color:#fff;font-size:10px;padding:2px 8px;
						border-radius:10px;margin-left:6px;">${ctype}</span>
				</span>
				<button class="btn btn-xs btn-default es-add-row">+ Add</button>
			</div>
			<div style="overflow-x:auto;">
				<table class="table table-bordered"
					style="margin:0;font-size:12px;min-width:550px;">
					<thead style="background:#f3f4f6;">
						<tr>
							<th>Assessment Type</th>
							<th>Label</th>
							<th>Maximum Marks</th>
							<th>Min Marks</th>
							<th>Passing Marks</th>
							<th>Enrollment</th>
							<th></th>
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
	const sub_opts = (frm._ep_atypes || []).map(a =>
		`<option value="${a.name}" ${(data.substitute_for || '') === a.name ? 'selected' : ''}>${a.type_name || a.name}</option>`
	).join('');

	const show_sub = data.substitute_for ? '' : 'display:none;';
	const sub_lbl  = data.substitute_for ? 'Hide Substitution Settings' : 'Show Substitution Settings';

	const $main = $(`
		<tr data-fn="${fn}">
			<td>
				<select name="at" style="width:130px;font-size:11px;padding:2px;">
					<option value="">Select</option>${at_opts}
				</select>
			</td>
			<td><input name="lbl" value="${_esc(data.label || '')}"
				style="width:90px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="max" type="number" value="${data.maximum_marks || ''}"
				style="width:80px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="min" type="number" value="${data.minimum_marks || 0}"
				style="width:70px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td><input name="pass" type="number" value="${data.passing_marks || 0}"
				style="width:70px;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/></td>
			<td>
				<select name="enroll" style="width:70px;font-size:11px;padding:2px;">
					<option value="Auto" ${(data.enrollment || 'Manual') === 'Auto' ? 'selected' : ''}>Auto</option>
					<option value="Manual" ${(data.enrollment || 'Manual') === 'Manual' ? 'selected' : ''}>Manual</option>
				</select>
			</td>
			<td>
				<button class="btn btn-xs es-del" style="color:#c00;padding:1px 6px;">×</button>
			</td>
		</tr>
	`);

	const $subst = $(`
		<tr data-fn="${fn}-s" class="es-subst-row">
			<td colspan="7" style="padding:5px 10px;background:#fafafa;">
				<a class="es-subst-toggle" href="#"
					style="font-size:11px;color:#5e64ff;text-decoration:none;">${sub_lbl}</a>
				<div class="es-subst-body" style="${show_sub}margin-top:6px;
					display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
					<div>
						<label style="font-size:11px;display:block;margin-bottom:2px;">Substitute For</label>
						<select name="sub_for" style="width:100%;font-size:11px;padding:2px;">
							<option value="">Select</option>${sub_opts}
						</select>
					</div>
					<div>
						<label style="font-size:11px;display:block;margin-bottom:2px;">Weightage</label>
						<input name="sub_wt" type="number" value="${data.substitute_weightage || 100}"
							style="width:80%;font-size:11px;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/> %
					</div>
					<div>
						<label style="font-size:11px;display:block;margin-bottom:2px;">Effective Marks</label>
						<input name="eff" value="${data.effective_marks || ''}" readonly
							style="width:80%;font-size:11px;background:#f5f5f5;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/>
					</div>
					<div>
						<label style="font-size:11px;display:block;margin-bottom:2px;">Substitute Effective Marks</label>
						<input name="sub_eff" value="${data.effective_marks || ''}" readonly
							style="width:80%;font-size:11px;background:#f5f5f5;border:1px solid #d1d5db;border-radius:3px;padding:2px 4px;"/>
					</div>
				</div>
				<div style="font-size:10px;color:#999;margin-top:3px;">
					Substitute exam effective marks must be ≤ effective maximum marks of assessment
				</div>
			</td>
		</tr>
	`);

	$sec.find('.es-tbody').append($main).append($subst);

	$subst.on('click', '.es-subst-toggle', (e) => {
		e.preventDefault();
		const $body = $subst.find('.es-subst-body');
		$body.toggle();
		$subst.find('.es-subst-toggle')
			.text($body.is(':visible') ? 'Hide Substitution Settings' : 'Show Substitution Settings');
	});

	const sync = () => {
		const r = (frm.doc.reexam_configs || []).find(x => x.name === fn);
		if (!r) return;
		r.component          = comp;
		r.assessment_type    = $main.find('[name=at]').val();
		r.label              = $main.find('[name=lbl]').val();
		r.maximum_marks      = parseFloat($main.find('[name=max]').val()) || 0;
		r.minimum_marks      = parseFloat($main.find('[name=min]').val()) || 0;
		r.passing_marks      = parseFloat($main.find('[name=pass]').val()) || 0;
		r.enrollment         = $main.find('[name=enroll]').val();
		r.substitute_for     = $subst.find('[name=sub_for]').val() || null;
		r.substitute_weightage = parseFloat($subst.find('[name=sub_wt]').val()) || 100;
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
