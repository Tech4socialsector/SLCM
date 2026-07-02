// Copyright (c) 2026, TFSS and contributors
// SLCM Record Drilldown — generic, card-agnostic detail browser.
//
// This page works for ANY Number Card, including ones an admin adds via the
// Workspace UI with zero code changes: it resolves document_type + filters
// live from the Number Card record (see slcm_record_drilldown.py) rather than
// relying on a hardcoded module/dimension map. Deliberately NOT a List View —
// renders a bespoke table and opens every record in a brand new Desk tab.
'use strict';

frappe.pages['slcm-record-drilldown'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Record Drilldown',
		single_column: true,
	});
	new SLCMRecordDrilldown(wrapper);
};

const SRD_METHOD = 'slcm.slcm.page.slcm_record_drilldown.slcm_record_drilldown';

// NLSIU brand palette — maroon #7B1C1C · gold #C9922A · navy #2b2e4a
const SRD_PALETTE = {
	primary:  '#7B1C1C',
	primaryXl:'#FAE0E0',
	gold:     '#C9922A',
	goldXl:   '#F5E6C8',
};

// Opens a URL in a new tab via a synthetic <a target="_blank"> click rather
// than window.open() — browsers can silently block window.open() once any
// object lookup runs between the click event and the call, whereas a real
// anchor click is always trusted as user-initiated.
const srd_open_in_new_tab = (url) => {
	if (!url) return;
	const a = document.createElement('a');
	a.href = url;
	a.target = '_blank';
	a.rel = 'noopener';
	document.body.appendChild(a);
	a.click();
	a.remove();
};

class SLCMRecordDrilldown {
	constructor(wrapper) {
		this.$wrapper = $(wrapper);
		this.$body    = this.$wrapper.find('.page-content');

		// Route: /app/slcm-record-drilldown/<number_card_name>
		// Query string carries the already-resolved filters (Number Card's own
		// filters_json merged with the dashboard's active filters) as JSON, so
		// this page never has to re-derive filter logic that already lives
		// server-side in get_workspace_dashboard_details / merge_filters_for_doctype.
		const route = frappe.get_route();
		this.number_card = decodeURIComponent(route[1] || '');

		const search_params = new URLSearchParams(window.location.search);
		try {
			this.resolved_filters = JSON.parse(search_params.get('filters') || '[]');
		} catch {
			this.resolved_filters = [];
		}
		this.card_label = search_params.get('label') || '';

		this.page_no    = 1;
		this.page_size  = 25;
		this.search_q   = '';
		this.document_type = null;
		this.columns    = [];
		this.title_field = 'name';

		this._inject_styles();
		this._build_skeleton();
		this._bind_events();
		this._load();
	}

	// ── Styles ───────────────────────────────────────────────────────────────
	_inject_styles() {
		if ($('#srd-styles').length) return;
		$(`<style id="srd-styles">
		.srd-page { padding: 18px 24px 60px; background:#FAF7F2; min-height:100vh; }
		.srd-header { display:flex; align-items:center; gap:14px; margin-bottom:18px; }
		.srd-header-icon {
			width:46px; height:46px; border-radius:12px; flex-shrink:0;
			background:linear-gradient(135deg,${SRD_PALETTE.primary},${SRD_PALETTE.gold});
			display:flex; align-items:center; justify-content:center;
			color:#fff; font-size:20px; box-shadow:0 4px 14px rgba(123,28,28,.35);
		}
		.srd-title { font-size:20px; font-weight:800; color:#1a0a0a; letter-spacing:-.3px; }
		.srd-breadcrumb { font-size:12px; color:#9ca0b8; margin-top:2px; }
		.srd-toolbar {
			display:flex; align-items:center; gap:10px; margin-bottom:16px;
			background:#fff; border:1px solid #E8DDD0; border-radius:10px; padding:12px 16px;
			box-shadow:0 1px 4px rgba(43,46,74,.06);
		}
		.srd-search-wrap { position:relative; flex:1; max-width:360px; }
		.srd-search-input {
			width:100%; padding:7px 12px 7px 30px; border:1.5px solid #E8DDD0;
			border-radius:8px; font-size:13px; outline:none;
		}
		.srd-search-input:focus { border-color:${SRD_PALETTE.primary}; }
		.srd-search-icon { position:absolute; left:10px; top:50%; transform:translateY(-50%); color:#9ca0b8; }
		.srd-count { margin-left:auto; font-size:12px; color:#5c607a; }
		.srd-btn {
			padding:7px 14px; border-radius:7px; font-size:12px; font-weight:600;
			border:1px solid #E8DDD0; background:#fff; color:#2b2e4a; cursor:pointer; transition:all .2s ease;
		}
		.srd-btn:hover { background:${SRD_PALETTE.primary}; color:#fff; border-color:${SRD_PALETTE.primary}; }
		.srd-table-wrap {
			background:#fff; border:1px solid #E8DDD0; border-radius:12px; overflow:hidden;
			box-shadow:0 1px 4px rgba(43,46,74,.06);
		}
		.srd-table { width:100%; border-collapse:collapse; font-size:13px; }
		.srd-table thead tr { background:${SRD_PALETTE.goldXl}; border-bottom:2px solid #E8DDD0; }
		.srd-table thead th {
			padding:10px 14px; text-align:left; font-size:11px; font-weight:700;
			text-transform:uppercase; letter-spacing:.5px; color:${SRD_PALETTE.primary}; white-space:nowrap;
		}
		.srd-table tbody tr { border-bottom:1px solid #F0EAE0; cursor:pointer; transition:background .15s; }
		.srd-table tbody tr:hover { background:#FAF3EA; }
		.srd-table tbody td { padding:10px 14px; color:#2b2e4a; }
		.srd-table tbody td:first-child { font-weight:600; color:#1a0a0a; }
		.srd-pagination {
			display:flex; align-items:center; justify-content:space-between;
			padding:12px 16px; font-size:12px; color:#5c607a; border-top:1px solid #E8DDD0;
		}
		.srd-page-btns { display:flex; gap:6px; }
		.srd-empty, .srd-loading {
			display:flex; flex-direction:column; align-items:center; justify-content:center;
			padding:60px 20px; color:#9ca0b8;
		}
		.srd-empty-icon { font-size:34px; margin-bottom:10px; opacity:.6; }

		/* ── Ad-hoc filter bar (generic — built from the doctype's own fields) ── */
		.srd-filter-bar {
			display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap;
			background:#fff; border:1px solid #E8DDD0; border-left:4px solid ${SRD_PALETTE.primary};
			border-radius:12px; padding:14px 18px; margin-bottom:14px;
			box-shadow:0 1px 4px rgba(43,46,74,.08);
		}
		.srd-filter-group { display:flex; flex-direction:column; gap:4px; flex:1; min-width:170px; }
		.srd-filter-label {
			font-size:10px; font-weight:700; text-transform:uppercase;
			letter-spacing:.6px; color:#5c607a;
		}
		.srd-filter-actions { display:flex; gap:8px; align-items:flex-end; padding-bottom:1px; }
		.srd-btn-primary { background:${SRD_PALETTE.primary}; color:#fff; border-color:${SRD_PALETTE.primary}; }
		.srd-btn-primary:hover { background:#5C1414; }

		/* ── Multiselect dropdown (mirrors the workspace dashboard widget) ── */
		.srd-ms-wrap { position:relative; }
		.srd-ms-trigger {
			display:flex; align-items:center; justify-content:space-between;
			gap:6px; padding:6px 10px; min-height:32px;
			background:#fff; border:1px solid #E8DDD0; border-radius:8px; cursor:pointer;
			font-size:12px; color:#2b2e4a; transition:all .2s ease;
			user-select:none; white-space:nowrap; overflow:hidden;
		}
		.srd-ms-trigger:hover { border-color:${SRD_PALETTE.primary}; }
		.srd-ms-trigger.open  { border-color:${SRD_PALETTE.primary}; box-shadow:0 0 0 2px ${SRD_PALETTE.primaryXl}; }
		.srd-ms-trigger-text  { flex:1; overflow:hidden; text-overflow:ellipsis; }
		.srd-ms-trigger-count {
			background:${SRD_PALETTE.primary}; color:#fff; border-radius:10px;
			padding:1px 7px; font-size:10px; font-weight:700; flex-shrink:0;
		}
		.srd-ms-trigger-arrow { color:#9ca0b8; font-size:10px; flex-shrink:0; transition:transform .18s; }
		.srd-ms-trigger.open .srd-ms-trigger-arrow { transform:rotate(180deg); }
		.srd-ms-dropdown {
			position:absolute; top:calc(100% + 4px); left:0; min-width:100%; max-width:280px;
			background:#fff; border:1px solid #E8DDD0; border-radius:8px;
			box-shadow:0 8px 32px rgba(43,46,74,.18); z-index:500; display:none; overflow:hidden;
		}
		.srd-ms-dropdown.open { display:block; }
		.srd-ms-search { padding:8px 10px; border-bottom:1px solid #E8DDD0; }
		.srd-ms-search input {
			width:100%; padding:4px 8px; font-size:12px;
			border:1px solid #E8DDD0; border-radius:6px; background:#FDF9F4; outline:none;
		}
		.srd-ms-search input:focus { border-color:${SRD_PALETTE.primary}; }
		.srd-ms-actions { display:flex; gap:8px; padding:5px 10px; border-bottom:1px solid #E8DDD0; }
		.srd-ms-action-btn {
			font-size:10px; font-weight:600; color:${SRD_PALETTE.gold};
			cursor:pointer; text-decoration:underline; background:none; border:none; padding:0;
		}
		.srd-ms-action-btn:hover { color:${SRD_PALETTE.primary}; }
		.srd-ms-list { max-height:200px; overflow-y:auto; padding:4px 0; }
		.srd-ms-list::-webkit-scrollbar { width:4px; }
		.srd-ms-list::-webkit-scrollbar-thumb { background:#E8DDD0; border-radius:2px; }
		.srd-ms-item {
			display:flex; align-items:center; gap:8px; padding:6px 10px;
			cursor:pointer; font-size:12px; color:#2b2e4a; transition:background .12s;
		}
		.srd-ms-item:hover { background:#FDF9F4; }
		.srd-ms-item input[type=checkbox] { accent-color:${SRD_PALETTE.primary}; width:14px; height:14px; flex-shrink:0; }
		.srd-ms-item label { cursor:pointer; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
		.srd-ms-empty { padding:10px; font-size:12px; color:#9ca0b8; text-align:center; }
		</style>`).appendTo('head');
	}

	// ── Skeleton ─────────────────────────────────────────────────────────────
	_build_skeleton() {
		this.$body.html(`
		<div class="srd-page">
			<div class="srd-header">
				<div class="srd-header-icon">📊</div>
				<div>
					<div class="srd-title" id="srd-title">Loading…</div>
					<div class="srd-breadcrumb" id="srd-breadcrumb"></div>
				</div>
			</div>
			<div class="srd-filter-bar" id="srd-filter-bar" style="display:none">
				<div id="srd-filter-fields" style="display:flex; gap:14px; flex-wrap:wrap; flex:1;"></div>
				<div class="srd-filter-actions">
					<button class="srd-btn srd-btn-primary" id="srd-apply-filters">Apply</button>
					<button class="srd-btn" id="srd-reset-filters">Reset</button>
				</div>
			</div>
			<div class="srd-toolbar">
				<div class="srd-search-wrap">
					<span class="srd-search-icon">🔍</span>
					<input type="text" id="srd-search" class="srd-search-input" placeholder="Search in results…">
				</div>
				<button class="srd-btn" id="srd-export">⬇ Export CSV</button>
				<span class="srd-count" id="srd-count"></span>
			</div>
			<div id="srd-content">
				<div class="srd-loading"><div class="srd-empty-icon">⏳</div>Loading records…</div>
			</div>
		</div>`);
	}

	// ── Events ───────────────────────────────────────────────────────────────
	_bind_events() {
		let debounce_timer = null;
		this.$body.on('input', '#srd-search', (e) => {
			clearTimeout(debounce_timer);
			const q = e.target.value;
			debounce_timer = setTimeout(() => {
				this.search_q = q;
				this._load_page(1);
			}, 250);
		});

		this.$body.on('click', '#srd-export', () => this._export_csv());

		this.$body.on('click', '#srd-apply-filters', () => this._load_page(1));
		this.$body.on('click', '#srd-reset-filters', () => {
			Object.values(this._filter_widgets || {}).forEach(w => w.reset());
			this._load_page(1);
		});

		// Row click → open the document in a NEW Desk tab. Never frappe.set_route()
		// here — that would navigate this drilldown tab instead of opening a new one.
		this.$body.on('click', 'tbody tr[data-id]', function () {
			const id = $(this).data('id');
			const dt = $(this).data('dt');
			if (dt && id) {
				srd_open_in_new_tab(`/app/${frappe.router.slug(dt)}/${encodeURIComponent(id)}`);
			}
		});
	}

	// ── Reusable multiselect dropdown widget (mirrors the workspace dashboard) ──
	// options: [{value, label}, ...]
	_make_multiselect(container_id, options, placeholder) {
		const uid = container_id.replace(/-/g, '_');

		const render = (opts) => {
			const items_html = opts.map((opt, i) => `
				<div class="srd-ms-item" data-val="${frappe.utils.escape_html(opt.value)}">
					<input type="checkbox" id="${uid}_cb_${i}" value="${frappe.utils.escape_html(opt.value)}">
					<label for="${uid}_cb_${i}">${frappe.utils.escape_html(opt.label)}</label>
				</div>`).join('') || `<div class="srd-ms-empty">No options</div>`;

			$('#' + container_id).html(`
				<div class="srd-ms-wrap" id="${uid}_wrap">
					<div class="srd-ms-trigger" id="${uid}_trigger">
						<span class="srd-ms-trigger-text" id="${uid}_label">${frappe.utils.escape_html(placeholder)}</span>
						<span class="srd-ms-trigger-arrow">▼</span>
					</div>
					<div class="srd-ms-dropdown" id="${uid}_dropdown">
						<div class="srd-ms-search"><input type="text" placeholder="Search…" id="${uid}_search"></div>
						<div class="srd-ms-actions">
							<button class="srd-ms-action-btn" id="${uid}_all">Select all</button>
							<button class="srd-ms-action-btn" id="${uid}_none">Clear</button>
						</div>
						<div class="srd-ms-list" id="${uid}_list">${items_html}</div>
					</div>
				</div>`);
		};

		render(options);

		const update_label = () => {
			const checked = $(`#${uid}_list input:checked`).map((_, el) => el.value).get();
			const $lbl = $(`#${uid}_label`);
			const $trigger = $(`#${uid}_trigger`);
			$trigger.find('.srd-ms-trigger-count').remove();
			if (!checked.length) {
				$lbl.text(placeholder);
			} else if (checked.length === 1) {
				const opt = options.find(o => o.value === checked[0]);
				$lbl.text(opt ? opt.label : checked[0]);
			} else {
				$lbl.text(`${checked.length} selected`);
				$trigger.prepend(`<span class="srd-ms-trigger-count" style="order:-1">${checked.length}</span>`);
			}
		};

		$(document).on('click', `#${uid}_trigger`, function (e) {
			e.stopPropagation();
			const $dd = $(`#${uid}_dropdown`);
			const isOpen = $dd.hasClass('open');
			$('.srd-ms-dropdown.open').removeClass('open');
			$('.srd-ms-trigger.open').removeClass('open');
			if (!isOpen) {
				$dd.addClass('open');
				$(`#${uid}_trigger`).addClass('open');
				$(`#${uid}_search`).val('').trigger('input').focus();
			}
		});

		$(document).on('input', `#${uid}_search`, function () {
			const q = this.value.toLowerCase();
			$(`#${uid}_list .srd-ms-item`).each(function () {
				const label = $(this).find('label').text().toLowerCase();
				$(this).toggle(label.includes(q));
			});
		});

		$(document).on('click', `#${uid}_all`, function (e) {
			e.stopPropagation();
			$(`#${uid}_list .srd-ms-item:visible input`).prop('checked', true);
			update_label();
		});
		$(document).on('click', `#${uid}_none`, function (e) {
			e.stopPropagation();
			$(`#${uid}_list input`).prop('checked', false);
			update_label();
		});

		$(document).on('change', `#${uid}_list input[type=checkbox]`, () => update_label());

		$(document).on('click.srd_ms', function (e) {
			if (!$(e.target).closest(`#${uid}_wrap`).length) {
				$(`#${uid}_dropdown`).removeClass('open');
				$(`#${uid}_trigger`).removeClass('open');
			}
		});

		return {
			get_values() {
				const vals = $(`#${uid}_list input:checked`).map((_, el) => el.value).get();
				return vals.length ? vals : null;
			},
			reset() {
				$(`#${uid}_list input`).prop('checked', false);
				update_label();
			},
		};
	}

	// ── Ad-hoc filters — built generically from the doctype's own Select/Link
	// fields, so any doctype gets a usable filter bar with zero bespoke code.
	_load_filter_fields() {
		frappe.call({
			method: `${SRD_METHOD}.get_filterable_fields`,
			args: { document_type: this.document_type },
			callback: (r) => {
				const fields = (r.message && r.message.fields) || [];
				this._filter_field_defs = fields;
				this._filter_widgets = {};

				if (!fields.length) return;

				const $container = $('#srd-filter-fields');
				$container.html(fields.map(f => `
					<div class="srd-filter-group">
						<div class="srd-filter-label">${frappe.utils.escape_html(f.label)}</div>
						<div id="srd-f-${f.fieldname}"></div>
					</div>`).join(''));

				fields.forEach(f => {
					this._filter_widgets[f.fieldname] = this._make_multiselect(
						`srd-f-${f.fieldname}`, f.options || [], `All ${f.label}`
					);
				});

				$('#srd-filter-bar').show();
			},
		});
	}

	// Extra ad-hoc filters chosen in the filter bar, layered on top of the
	// Number Card's own resolved_filters (never replacing them).
	_extra_filters() {
		const extra = [];
		Object.entries(this._filter_widgets || {}).forEach(([fieldname, widget]) => {
			const vals = widget.get_values();
			if (vals) extra.push([this.document_type, fieldname, "in", vals]);
		});
		return extra;
	}

	_effective_filters() {
		return [...(this.resolved_filters || []), ...this._extra_filters()];
	}

	// ── Resolve the Number Card → doctype + columns, then load page 1 ───────
	_load() {
		if (!this.number_card) {
			this._render_error('No Number Card specified for this drilldown.');
			return;
		}

		frappe.call({
			method: `${SRD_METHOD}.get_card_meta`,
			args: { number_card: this.number_card },
			callback: (r) => {
				if (r.exc || !r.message) {
					this._render_error('Unable to resolve this Number Card. It may have been deleted.');
					return;
				}
				const meta = r.message;
				this.document_type = meta.document_type;
				this.columns       = meta.columns;
				this.title_field   = meta.title_field;

				const label = this.card_label || meta.label;
				$('#srd-title').text(label);
				$('#srd-breadcrumb').text(`${this.document_type} · ${label}`);
				frappe.set_route_title && frappe.set_route_title(label);

				this._load_filter_fields();
				this._load_page(1);
			},
			error: () => this._render_error('Failed to load this drilldown. Check permissions or try again.'),
		});
	}

	// ── Data fetching (fully generic — works for any doctype) ──────────────
	_load_page(page) {
		this.page_no = page;
		$('#srd-content').html('<div class="srd-loading"><div class="srd-empty-icon">⏳</div>Loading records…</div>');

		frappe.call({
			method: `${SRD_METHOD}.get_records`,
			args: {
				document_type: this.document_type,
				filters: this._effective_filters(),
				columns: this.columns,
				search: this.search_q || undefined,
				page: this.page_no,
				page_size: this.page_size,
			},
			callback: (r) => {
				if (r.exc) {
					this._render_error('Failed to load records. Check permissions or try again.');
					return;
				}
				this._render(r.message || { rows: [], total: 0, columns: [] });
			},
			error: () => this._render_error('A network or server error occurred.'),
		});
	}

	// ── Rendering (custom layout — not a List View) ─────────────────────────
	_render(data) {
		const { rows, total, columns } = data;

		$('#srd-count').text(`${total || 0} total record${total === 1 ? '' : 's'}`);

		if (!rows.length) {
			$('#srd-content').html(`
				<div class="srd-empty">
					<div class="srd-empty-icon">📭</div>
					No records found${this.search_q ? ' for this search' : ''}.
				</div>`);
			return;
		}

		const head_html = columns.map(c =>
			`<th>${frappe.utils.escape_html(c.replace(/_/g, ' ').replace(/\b\w/g, s => s.toUpperCase()))}</th>`
		).join('');

		const body_html = rows.map(row => {
			const attrs = `data-dt="${frappe.utils.escape_html(this.document_type)}" data-id="${frappe.utils.escape_html(String(row.name))}"`;
			const cells = columns.map(c => {
				const val = row[c];
				return `<td>${val == null || val === '' ? '—' : frappe.utils.escape_html(String(val))}</td>`;
			}).join('');
			return `<tr ${attrs}>${cells}</tr>`;
		}).join('');

		const total_pages = Math.max(1, Math.ceil((total || 0) / this.page_size));
		const prev_dis = this.page_no <= 1 ? 'disabled' : '';
		const next_dis = this.page_no >= total_pages ? 'disabled' : '';

		$('#srd-content').html(`
			<div class="srd-table-wrap">
				<table class="srd-table">
					<thead><tr>${head_html}</tr></thead>
					<tbody>${body_html}</tbody>
				</table>
				<div class="srd-pagination">
					<span>Page ${this.page_no} of ${total_pages}</span>
					<div class="srd-page-btns">
						<button class="srd-btn" id="srd-prev" ${prev_dis}>← Previous</button>
						<button class="srd-btn" id="srd-next" ${next_dis}>Next →</button>
					</div>
				</div>
			</div>`);

		$('#srd-prev').on('click', () => this._load_page(this.page_no - 1));
		$('#srd-next').on('click', () => this._load_page(this.page_no + 1));
	}

	_render_error(message) {
		$('#srd-content').html(`
			<div class="srd-empty">
				<div class="srd-empty-icon">⚠️</div>
				${frappe.utils.escape_html(message)}
			</div>`);
	}

	// ── Export ───────────────────────────────────────────────────────────────
	_export_csv() {
		frappe.call({
			method: `${SRD_METHOD}.get_records`,
			args: {
				document_type: this.document_type,
				filters: this._effective_filters(),
				columns: this.columns,
				search: this.search_q || undefined,
				page: 1,
				page_size: 10000,
			},
			callback: (r) => {
				if (!r.message || !r.message.rows.length) {
					frappe.show_alert({ message: 'No data to export', indicator: 'orange' });
					return;
				}
				const { rows, columns } = r.message;
				const csv_rows = [
					columns.join(','),
					...rows.map(row => columns.map(c => `"${String(row[c] ?? '').replace(/"/g, '""')}"`).join(',')),
				];
				const blob = new Blob([csv_rows.join('\n')], { type: 'text/csv' });
				const url  = URL.createObjectURL(blob);
				const a    = document.createElement('a');
				a.href = url;
				a.download = `slcm_${this.document_type}_${this.number_card}.csv`.replace(/\s+/g, '_');
				a.click();
				URL.revokeObjectURL(url);
			},
		});
	}
}
