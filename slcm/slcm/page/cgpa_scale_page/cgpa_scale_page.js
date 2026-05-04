// CGPA Percentage Scale management page
frappe.pages["cgpa-scale-page"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("CGPA Percentage Scale"),
		single_column: true,
	});

	// ── State ──────────────────────────────────────────────────────────────────
	let rows = [];          // [{cgpa, percentage}, ...]
	let dirty = false;

	// ── CSS ────────────────────────────────────────────────────────────────────
	if (!document.getElementById("cps-styles")) {
		const style = document.createElement("style");
		style.id = "cps-styles";
		style.textContent = `
			.cps-wrap { padding: 20px 24px 60px; background: #f7f8fa; min-height: 100%; }

			.cps-toolbar {
				display: flex; align-items: center; gap: 10px;
				flex-wrap: wrap; margin-bottom: 18px;
			}
			.cps-btn {
				padding: 7px 16px; border-radius: 6px; font-size: 13px;
				font-weight: 600; cursor: pointer; border: 1.5px solid transparent;
				display: inline-flex; align-items: center; gap: 6px;
				transition: background 0.15s, box-shadow 0.15s;
			}
			.cps-btn-primary  { background:#4f46e5; color:#fff; border-color:#4f46e5; }
			.cps-btn-primary:hover  { background:#4338ca; }
			.cps-btn-outline  { background:#fff; color:#374151; border-color:#d1d5db; }
			.cps-btn-outline:hover  { background:#f3f4f6; }
			.cps-btn-green    { background:#16a34a; color:#fff; border-color:#16a34a; }
			.cps-btn-green:hover    { background:#15803d; }
			.cps-btn-red      { background:#dc2626; color:#fff; border-color:#dc2626; }
			.cps-btn-red:hover      { background:#b91c1c; }

			.cps-info {
				background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px;
				padding:12px 16px; margin-bottom:16px; font-size:13px; color:#1e40af;
			}

			.cps-card {
				background:#fff; border:1px solid #e4e7ea; border-radius:10px;
				box-shadow:0 1px 4px rgba(0,0,0,0.04); overflow:hidden;
			}

			.cps-search-row {
				display:flex; align-items:center; gap:10px;
				padding:12px 16px; border-bottom:1px solid #e4e7ea;
			}
			.cps-search { padding:7px 12px; border:1px solid #d1d5db; border-radius:6px; font-size:13px; width:200px; }

			.cps-table-wrap { overflow-y: auto; max-height: 60vh; }
			.cps-table { width:100%; border-collapse:collapse; font-size:13px; }
			.cps-table thead th {
				background:#f8fafc; border-bottom:2px solid #e2e8f0;
				padding:10px 16px; text-align:left; font-weight:700;
				color:#374151; position:sticky; top:0; z-index:1;
			}
			.cps-table tbody tr:hover { background:#f0f9ff; }
			.cps-table tbody td { padding:6px 16px; border-bottom:1px solid #f1f5f9; }
			.cps-table input[type=number] {
				width:100px; padding:4px 8px; border:1px solid #d1d5db;
				border-radius:4px; font-size:13px;
			}
			.cps-table input[type=number]:focus { outline:none; border-color:#6366f1; }

			.cps-add-row { padding:10px 16px; border-top:1px solid #e4e7ea; }
			.cps-status { font-size:12px; color:#6b7280; margin-left:auto; }
			.cps-dirty  { color:#d97706; font-weight:600; }
		`;
		document.head.appendChild(style);
	}

	// ── Render shell ──────────────────────────────────────────────────────────
	$(wrapper).find(".page-content").html(`
		<div class="cps-wrap">
			<div class="cps-info">
				Enter CGPA → Final Percentage mappings below. When generating
				<strong>Cumulative Percentage</strong> in Term Results, the system looks up
				the student's CGPA in this table. Use <em>Pre-fill from Standard Formula</em>
				to auto-populate all values (CGPA 0–7 in 0.01 steps), then edit as needed.
			</div>

			<div class="cps-toolbar">
				<button class="cps-btn cps-btn-outline" id="cps-back-btn">
					<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
					Back to Term Results
				</button>
				<div style="width:1px;height:22px;background:#e2e8f0;margin:0 4px;"></div>
				<button class="cps-btn cps-btn-green" id="cps-prefill-btn">
					<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
					Pre-fill from Standard Formula
				</button>
				<button class="cps-btn cps-btn-primary" id="cps-save-btn">
					<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
					Save Scale
				</button>
				<button class="cps-btn cps-btn-outline" id="cps-add-btn">
					+ Add Row
				</button>
				<span class="cps-status" id="cps-status">Loading…</span>
			</div>

			<div class="cps-card">
				<div class="cps-search-row">
					<label style="font-size:13px;font-weight:600;color:#374151;">Filter:</label>
					<input type="number" class="cps-search" id="cps-filter" placeholder="Search CGPA…" step="0.01">
					<span id="cps-count" style="font-size:12px;color:#6b7280;margin-left:auto;"></span>
				</div>
				<div class="cps-table-wrap">
					<table class="cps-table">
						<thead>
							<tr>
								<th style="width:160px;">CGPA</th>
								<th>Final Percentage</th>
								<th style="width:60px;"></th>
							</tr>
						</thead>
						<tbody id="cps-tbody"></tbody>
					</table>
				</div>
			</div>
		</div>
	`);

	// ── Helpers ───────────────────────────────────────────────────────────────
	function setStatus(msg, isDirty) {
		const el = document.getElementById("cps-status");
		el.textContent = msg;
		el.className = "cps-status" + (isDirty ? " cps-dirty" : "");
		dirty = !!isDirty;
	}

	function renderTable(filter) {
		const tbody = document.getElementById("cps-tbody");
		const filterVal = parseFloat(filter);
		const visible = isNaN(filterVal)
			? rows
			: rows.filter(r => String(r.cgpa).startsWith(String(filter)));

		document.getElementById("cps-count").textContent =
			`${visible.length} of ${rows.length} entries`;

		tbody.innerHTML = visible.map((r, vi) => {
			const ri = rows.indexOf(r);
			return `<tr data-idx="${ri}">
				<td><input type="number" step="0.01" min="0" max="7" class="cps-cgpa" data-idx="${ri}" value="${r.cgpa}"></td>
				<td><input type="number" step="0.01" min="0" max="100" class="cps-pct" data-idx="${ri}" value="${r.percentage}"></td>
				<td><button class="cps-btn cps-btn-red cps-del" data-idx="${ri}"
					style="padding:3px 8px;font-size:11px;">✕</button></td>
			</tr>`;
		}).join("");
	}

	// ── Load data ─────────────────────────────────────────────────────────────
	function loadScale() {
		setStatus("Loading…", false);
		frappe.call({
			method: "slcm.slcm.page.cgpa_scale_page.cgpa_scale_page.get_scale",
			callback(r) {
				rows = (r.message || []).map(x => ({
					cgpa: parseFloat(x.cgpa),
					percentage: parseFloat(x.percentage),
				}));
				renderTable($("#cps-filter").val());
				setStatus(`${rows.length} entries loaded`, false);
			},
		});
	}

	// ── Events ────────────────────────────────────────────────────────────────

	// Back to Term Results
	$(wrapper).on("click", "#cps-back-btn", function () {
		frappe.set_route("term-result");
	});

	// Filter
	$(wrapper).on("input", "#cps-filter", function () {
		renderTable($(this).val());
	});

	// Inline edit — update rows[] on change
	$(wrapper).on("change", ".cps-cgpa", function () {
		const idx = parseInt($(this).data("idx"));
		rows[idx].cgpa = parseFloat($(this).val()) || 0;
		setStatus("Unsaved changes", true);
	});
	$(wrapper).on("change", ".cps-pct", function () {
		const idx = parseInt($(this).data("idx"));
		rows[idx].percentage = parseFloat($(this).val()) || 0;
		setStatus("Unsaved changes", true);
	});

	// Delete row
	$(wrapper).on("click", ".cps-del", function () {
		const idx = parseInt($(this).data("idx"));
		rows.splice(idx, 1);
		renderTable($("#cps-filter").val());
		setStatus("Unsaved changes", true);
	});

	// Add row
	$(wrapper).on("click", "#cps-add-btn", function () {
		rows.push({ cgpa: 0, percentage: 0 });
		renderTable($("#cps-filter").val());
		// scroll to bottom
		document.querySelector(".cps-table-wrap").scrollTop = 999999;
		setStatus("Unsaved changes", true);
	});

	// Pre-fill
	$(wrapper).on("click", "#cps-prefill-btn", function () {
		frappe.confirm(
			__("This will replace all existing entries with standard formula values (CGPA 0–7 in 0.01 steps). Continue?"),
			function () {
				frappe.call({
					method: "slcm.slcm.page.cgpa_scale_page.cgpa_scale_page.populate_scale",
					freeze: true,
					freeze_message: "Generating scale entries…",
					callback(r) {
						if (r.message) {
							frappe.show_alert({ message: `${r.message.populated} entries created`, indicator: "green" });
							loadScale();
						}
					},
				});
			}
		);
	});

	// Save
	$(wrapper).on("click", "#cps-save-btn", function () {
		// sort by CGPA before saving
		rows.sort((a, b) => a.cgpa - b.cgpa);
		frappe.call({
			method: "slcm.slcm.page.cgpa_scale_page.cgpa_scale_page.save_scale",
			args: { data: JSON.stringify(rows) },
			freeze: true,
			freeze_message: "Saving…",
			callback(r) {
				if (r.message) {
					frappe.show_alert({ message: `${r.message.saved} entries saved`, indicator: "green" });
					setStatus(`${r.message.saved} entries saved`, false);
					renderTable($("#cps-filter").val());
				}
			},
		});
	});

	loadScale();
};
