// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.pages["transcript-management-page"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Transcript Management"),
		single_column: true,
	});

	const _origWrapper = wrapper;

	// ── State ──────────────────────────────────────────────────────────────────
	const state = {
		search:         "",
		programme:      "",
		course:         "",
		academic_year:  "",
		batch:          "",
		student_status: "",
		department:     "",
		page:           1,
		page_length:    50,
		total:          0,
		sort_by:        "registration_id",
		sort_order:     "asc",
		loading:        false,
		selected:       new Set(),
		filter_options: null,
		_prog_labels:   {},
		_dept_labels:   {},
	};

	// ── Inject CSS ─────────────────────────────────────────────────────────────
	if (!document.getElementById("tm-styles")) {
		const style = document.createElement("style");
		style.id = "tm-styles";
		style.textContent = `
			@keyframes tm-spin { to { transform: rotate(360deg); } }

			/* Layout */
			.tm-wrap { padding: 20px 24px 80px; background: #f7f8fa; min-height: 100%; }

			/* ── Stats bar ── */
			.tm-stats-bar {
				display: flex;
				gap: 12px;
				margin-bottom: 16px;
				flex-wrap: wrap;
			}
			.tm-stat-card {
				flex: 1;
				min-width: 150px;
				background: #fff;
				border: 1px solid #e4e7ea;
				border-radius: 10px;
				padding: 14px 16px;
				display: flex;
				align-items: center;
				gap: 12px;
				box-shadow: 0 1px 4px rgba(0,0,0,0.04);
				transition: box-shadow 0.15s;
			}
			.tm-stat-card:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.08); }
			.tm-stat-icon {
				width: 40px; height: 40px;
				border-radius: 10px;
				display: flex; align-items: center; justify-content: center;
				flex-shrink: 0;
			}
			.tm-stat-icon-total    { background: #eff3ff; color: #3b5bdb; }
			.tm-stat-icon-interim  { background: #fff3cd; color: #b45309; }
			.tm-stat-icon-final    { background: #e6f4ea; color: #1a7a36; }
			.tm-stat-icon-pending  { background: #fdecea; color: #c84630; }
			.tm-stat-body { flex: 1; min-width: 0; }
			.tm-stat-value {
				font-size: 22px; font-weight: 700; color: #1a1a2e; line-height: 1;
				transition: color 0.2s;
			}
			.tm-stat-label { font-size: 11px; color: #888; margin-top: 3px; font-weight: 500; }

			/* ── Toolbar ── */
			.tm-toolbar {
				display: flex;
				align-items: center;
				gap: 10px;
				flex-wrap: wrap;
				margin-bottom: 16px;
			}
			.tm-search-box {
				flex: 1;
				min-width: 260px;
				max-width: 420px;
				position: relative;
			}
			.tm-search-box svg {
				position: absolute; left: 11px; top: 50%;
				transform: translateY(-50%); pointer-events: none;
			}
			.tm-search-input {
				width: 100%; padding: 8px 12px 8px 34px;
				border: 1px solid #d1d8dd; border-radius: 6px;
				font-size: 13px; outline: none; box-sizing: border-box;
				background: #fff; color: #333;
				transition: border-color 0.15s, box-shadow 0.15s;
				height: 34px;
			}
			.tm-search-input:focus {
				border-color: #c84630;
				box-shadow: 0 0 0 3px rgba(200,70,48,0.1);
			}
			.tm-search-input::placeholder { color: #aab; }

			/* Action buttons group */
			.tm-actions { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

			/* Base button reset */
			.tm-btn {
				display: inline-flex; align-items: center; gap: 6px;
				padding: 0 14px; height: 34px;
				font-size: 13px; font-weight: 600; border-radius: 6px;
				cursor: pointer;
				transition: background 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s;
				white-space: nowrap; border: 1.5px solid transparent; line-height: 1;
			}
			.tm-btn:focus { outline: none; }

			/* Outline / ghost variant */
			.tm-btn-outline {
				background: #fff; border-color: #c84630; color: #c84630;
			}
			.tm-btn-outline:hover {
				background: #c84630; color: #fff;
				box-shadow: 0 2px 8px rgba(200,70,48,0.2);
			}
			.tm-btn-outline:hover svg { stroke: #fff; }

			/* Primary filled */
			.tm-btn-primary { background: #c84630; border-color: #c84630; color: #fff; }
			.tm-btn-primary:hover {
				background: #a83828; border-color: #a83828;
				box-shadow: 0 2px 8px rgba(200,70,48,0.3);
			}

			/* Default/neutral */
			.tm-btn-default { background: #fff; border-color: #d1d8dd; color: #444; }
			.tm-btn-default:hover {
				border-color: #c84630; color: #c84630; background: #fff8f7;
			}

			/* Split button group */
			.tm-split-group { display: inline-flex; }
			.tm-split-group .tm-btn { border-radius: 0; }
			.tm-split-group .tm-btn:first-child { border-radius: 6px 0 0 6px; border-right: none; }
			.tm-split-group .tm-btn:last-child  { border-radius: 0 6px 6px 0; padding: 0 10px; border-left: 1px solid rgba(255,255,255,0.3); }
			.tm-split-group .tm-btn-outline:last-child { border-left-color: rgba(200,70,48,0.4); }

			/* Dropdown */
			.tm-dropdown { position: relative; display: inline-flex; }
			.tm-dropdown-menu {
				display: none; position: absolute;
				top: calc(100% + 4px); right: 0; z-index: 1050;
				background: #fff; border: 1px solid #e0e4e8;
				border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,0.12);
				min-width: 220px; padding: 6px 0;
				list-style: none; margin: 0;
			}
			.tm-dropdown-menu.open { display: block; }
			.tm-dropdown-menu li a {
				display: flex; align-items: center; gap: 8px;
				padding: 8px 16px; font-size: 13px; color: #333;
				text-decoration: none; transition: background 0.1s;
			}
			.tm-dropdown-menu li a:hover { background: #fdf5f5; color: #c84630; }
			.tm-dropdown-menu .tm-divider { height: 1px; background: #f0f1f3; margin: 4px 0; }
			.tm-dropdown-menu .tm-menu-label {
				padding: 6px 16px 4px; font-size: 10px; font-weight: 700;
				text-transform: uppercase; letter-spacing: 0.06em; color: #aaa;
			}

			/* Icon button */
			.tm-icon-btn {
				width: 34px; height: 34px; padding: 0; border-radius: 6px;
				background: #fff; border: 1.5px solid #d1d8dd; cursor: pointer;
				display: inline-flex; align-items: center; justify-content: center;
				transition: border-color 0.15s, background 0.15s; color: #666;
			}
			.tm-icon-btn:hover { border-color: #c84630; color: #c84630; background: #fff8f7; }
			.tm-icon-btn:focus { outline: none; }

			/* Filter badge on button */
			.tm-filter-badge {
				display: inline-flex; align-items: center; justify-content: center;
				background: #c84630; color: #fff; border-radius: 50%;
				font-size: 10px; font-weight: 700; width: 16px; height: 16px; margin-left: 2px;
			}

			/* Filter panel */
			.tm-filter-panel {
				background: #fff; border: 1px solid #e4e7ea; border-radius: 8px;
				padding: 18px 20px 16px; margin-bottom: 16px;
				box-shadow: 0 2px 8px rgba(0,0,0,0.04);
			}
			.tm-filter-panel-title {
				font-size: 11px; font-weight: 700; text-transform: uppercase;
				letter-spacing: 0.06em; color: #888; margin-bottom: 14px;
			}
			.tm-filter-grid {
				display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 14px;
			}
			.tm-filter-field label {
				display: block; font-size: 11px; font-weight: 600;
				color: #555; margin-bottom: 5px; letter-spacing: 0.02em;
			}
			.tm-filter-select {
				width: 100%; padding: 7px 10px; border: 1px solid #d1d8dd;
				border-radius: 5px; font-size: 13px; background: #fafbfc; color: #333;
				outline: none; transition: border-color 0.15s, box-shadow 0.15s;
				height: 34px; cursor: pointer; appearance: auto;
			}
			.tm-filter-select:focus {
				border-color: #c84630; box-shadow: 0 0 0 3px rgba(200,70,48,0.1); background: #fff;
			}
			.tm-filter-actions {
				margin-top: 16px; display: flex; gap: 8px; align-items: center;
				border-top: 1px solid #f0f1f3; padding-top: 14px;
			}

			/* Active filter tags */
			.tm-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
			.tm-tag {
				display: inline-flex; align-items: center; gap: 4px;
				padding: 3px 6px 3px 10px; background: #fff0ee;
				border: 1px solid #fcc; border-radius: 20px;
				font-size: 11px; color: #c84630; font-weight: 500;
			}
			.tm-tag-remove {
				background: none; border: none; padding: 0 2px; line-height: 1;
				cursor: pointer; color: #e08070; font-size: 12px;
				display: inline-flex; align-items: center; border-radius: 50%;
				transition: color 0.1s, background 0.1s;
			}
			.tm-tag-remove:hover { color: #c84630; background: rgba(200,70,48,0.1); }

			/* Table card */
			.tm-table-card {
				background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
				overflow: hidden; box-shadow: 0 1px 6px rgba(0,0,0,0.05);
			}

			/* DataTables top bar */
			.tm-dt-topbar {
				display: flex; align-items: center; justify-content: space-between;
				padding: 10px 14px; border-bottom: 1px solid #dee2e6;
				background: #f8f9fa;
			}
			.tm-dt-entries {
				font-size: 12px; color: #555;
				display: flex; align-items: center; gap: 6px;
			}
			.tm-dt-select {
				padding: 2px 6px; border: 1px solid #ced4da; border-radius: 3px;
				font-size: 12px; background: #fff; cursor: pointer;
				height: 26px; color: #333;
			}
			.tm-dt-topbar-right { font-size: 12px; color: #888; }

			/* DataTables bottom bar */
			.tm-dt-bottombar {
				display: flex; align-items: center; justify-content: space-between;
				padding: 10px 14px; border-top: 1px solid #dee2e6;
				background: #f8f9fa; flex-wrap: wrap; gap: 8px;
			}
			.tm-page-info { font-size: 12px; color: #6c757d; }
			.tm-page-controls { display: flex; align-items: center; }
			.tm-page-btn {
				padding: 0 10px; height: 28px;
				border: 1px solid #dee2e6; border-right: none;
				background: #fff; font-size: 12px; font-weight: 500;
				color: #495057; cursor: pointer; transition: all 0.12s;
				display: inline-flex; align-items: center;
			}
			.tm-page-btn:first-child { border-radius: 3px 0 0 3px; }
			.tm-page-btn:last-child  { border-right: 1px solid #dee2e6; border-radius: 0 3px 3px 0; }
			.tm-page-btn:hover:not(:disabled) { background: #e9ecef; color: #c84630; border-color: #c84630; z-index: 1; }
			.tm-page-btn:disabled { opacity: 0.45; cursor: not-allowed; background: #f8f9fa; }
			.tm-page-num {
				padding: 0 10px; height: 28px;
				border: 1px solid #dee2e6; border-right: none;
				background: #fff; font-size: 12px; color: #495057;
				cursor: pointer; display: inline-flex; align-items: center;
				transition: all 0.12s;
			}
			.tm-page-num:hover { background: #e9ecef; color: #c84630; }
			.tm-page-num.active {
				background: #c84630; color: #fff; border-color: #c84630;
				font-weight: 700; z-index: 1; position: relative;
			}
			.tm-page-ellipsis {
				padding: 0 8px; height: 28px;
				border: 1px solid #dee2e6; border-right: none;
				background: #fff; font-size: 12px; color: #aaa;
				display: inline-flex; align-items: center;
			}

			/* DataTables table */
			.tm-table { width: 100%; border-collapse: collapse; margin: 0; }
			.tm-table thead tr { background: #f2f4f6; }
			.tm-table thead th {
				font-size: 11px; font-weight: 700; text-transform: uppercase;
				letter-spacing: 0.04em; color: #495057;
				padding: 9px 12px; white-space: nowrap;
				border-bottom: 2px solid #dee2e6;
				border-right: 1px solid #e4e7ea;
			}
			.tm-table thead th:last-child { border-right: none; }
			.tm-table thead th.tm-col-accent { color: #c84630; }
			.tm-table thead th.tm-sortable { cursor: pointer; user-select: none; }
			.tm-table thead th.tm-sortable:hover { background: #e8eaed; }
			.tm-table tbody tr { transition: background 0.08s; }
			.tm-table tbody tr:nth-child(even) { background: #f9fafb; }
			.tm-table tbody tr:hover { background: #fff3f0 !important; }
			.tm-table tbody td {
				padding: 9px 12px; vertical-align: middle;
				border-bottom: 1px solid #e9ecef;
				border-right: 1px solid #e9ecef;
			}
			.tm-table tbody td:last-child { border-right: none; }
			.tm-table tbody tr:last-child td { border-bottom: none; }

			/* Sort indicator */
			.tm-sort-icon { font-size: 10px; color: #ccc; margin-left: 3px; }
			.tm-sort-icon.asc  { color: #c84630; }
			.tm-sort-icon.desc { color: #c84630; }

			/* Avatar */
			.tm-avatar {
				width: 36px; height: 36px; border-radius: 50%;
				object-fit: cover; flex-shrink: 0; border: 2px solid #f0f0f0;
			}
			.tm-avatar-initials {
				width: 36px; height: 36px; border-radius: 50%;
				display: inline-flex; align-items: center; justify-content: center;
				background: linear-gradient(135deg, #c84630, #e06040);
				color: #fff; font-weight: 700; font-size: 14px; flex-shrink: 0;
			}

			/* Student name link */
			.tm-student-link {
				font-weight: 600; color: #c84630; font-size: 13px; text-decoration: none;
			}
			.tm-student-link:hover { text-decoration: underline; }

			/* Transcript interactive badges */
			.tm-badge {
				display: inline-flex; align-items: center; gap: 4px;
				padding: 3px 10px; border-radius: 20px;
				font-size: 11px; font-weight: 600; white-space: nowrap;
			}
			.tm-badge-generated {
				background: #e6f4ea; color: #1a7a36; border: 1px solid #b7dfc5;
				cursor: pointer; transition: box-shadow 0.12s, background 0.12s;
			}
			.tm-badge-generated:hover {
				background: #d0edda; box-shadow: 0 2px 8px rgba(26,122,54,0.2);
			}
			.tm-badge-revoked {
				background: #fdecea; color: #c0392b; border: 1px solid #f5c0bb;
				cursor: pointer; transition: box-shadow 0.12s;
			}
			.tm-badge-revoked:hover {
				background: #fad7d4; box-shadow: 0 2px 8px rgba(192,57,43,0.15);
			}
			.tm-badge-pending { background: #fff3cd; color: #856404; border: 1px solid #ffe69c; }
			.tm-badge-na { color: #ccc; font-weight: 400; }

			/* Clickable "generate" dash badge */
			.tm-gen-badge {
				display: inline-flex; align-items: center; gap: 4px;
				padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 500;
				border: 1.5px dashed #d1d8dd; color: #bbb;
				background: none; cursor: pointer;
				transition: border-color 0.15s, color 0.15s, background 0.15s;
				white-space: nowrap;
			}
			.tm-gen-badge:hover {
				border-color: #c84630; color: #c84630; background: #fff0ee;
			}

			/* Student status pill */
			.tm-status-pill {
				display: inline-block; padding: 2px 8px; border-radius: 20px;
				font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
			}
			.tm-status-active    { background: #e6f4ea; color: #1a7a36; }
			.tm-status-inactive  { background: #f0f1f3; color: #666; }
			.tm-status-graduated { background: #e8f0fe; color: #1a5ccb; }
			.tm-status-dropped   { background: #fdecea; color: #c0392b; }
			.tm-status-alumni    { background: #fef3e6; color: #b45309; }
			.tm-status-dormant   { background: #f5effe; color: #6b21a8; }

			/* (pagination styles moved to DataTables bottom bar section above) */

			/* Loading spinner */
			.tm-spinner {
				width: 28px; height: 28px;
				border: 3px solid #f0f0f0; border-top-color: #c84630;
				border-radius: 50%; animation: tm-spin 0.8s linear infinite;
				margin: 0 auto 10px;
			}

			/* Checkbox styling */
			.tm-checkbox { width: 15px; height: 15px; cursor: pointer; accent-color: #c84630; }

			/* ── Selection action bar (fixed at bottom) ── */
			.tm-sel-bar {
				position: fixed; bottom: 0; left: 0; right: 0;
				background: #1e2a3a; color: #fff;
				padding: 0 28px;
				display: flex; align-items: center; gap: 10px;
				z-index: 1100;
				height: 56px;
				box-shadow: 0 -4px 20px rgba(0,0,0,0.22);
				transform: translateY(100%);
				transition: transform 0.22s cubic-bezier(.4,0,.2,1);
			}
			.tm-sel-bar.tm-sel-bar--visible { transform: translateY(0); }
			.tm-sel-count {
				font-weight: 700; font-size: 13px; color: #fff;
				background: rgba(255,255,255,0.12);
				padding: 4px 12px; border-radius: 20px; margin-right: 4px;
			}
			.tm-sel-label { font-size: 13px; color: rgba(255,255,255,0.7); }
			.tm-sel-divider { width: 1px; height: 24px; background: rgba(255,255,255,0.15); margin: 0 4px; }
			.tm-sel-action {
				display: inline-flex; align-items: center; gap: 6px;
				padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600;
				cursor: pointer; border: 1.5px solid transparent; transition: all 0.15s;
				white-space: nowrap;
			}
			.tm-sel-interim {
				background: rgba(251,191,36,0.15); color: #fbbf24;
				border-color: rgba(251,191,36,0.3);
			}
			.tm-sel-interim:hover { background: rgba(251,191,36,0.25); }
			.tm-sel-final {
				background: rgba(59,130,246,0.15); color: #60a5fa;
				border-color: rgba(59,130,246,0.3);
			}
			.tm-sel-final:hover { background: rgba(59,130,246,0.25); }
			.tm-sel-year {
				background: rgba(16,185,129,0.15); color: #34d399;
				border-color: rgba(16,185,129,0.3);
			}
			.tm-sel-year:hover { background: rgba(16,185,129,0.25); }
			.tm-sel-clear {
				margin-left: auto;
				background: none; border: 1.5px solid rgba(255,255,255,0.2);
				color: rgba(255,255,255,0.6); padding: 5px 12px; border-radius: 6px;
				font-size: 12px; cursor: pointer; transition: all 0.15s;
			}
			.tm-sel-clear:hover { border-color: rgba(255,255,255,0.5); color: #fff; }
		`;
		document.head.appendChild(style);
	}

	// ── Build page HTML ────────────────────────────────────────────────────────
	$(wrapper).find(".page-content").html(`
		<div class="tm-wrap">

			<!-- Toolbar -->
			<div class="tm-toolbar">
				<div class="tm-search-box">
					<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
						fill="none" stroke="#999" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
						<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
					</svg>
					<input id="tm-search" type="text" class="tm-search-input"
						placeholder="${__("Search by Student Name, Registration ID, Email")}" />
				</div>

				<div class="tm-actions">
					<!-- Filter button -->
					<button id="tm-filter-btn" class="tm-btn tm-btn-outline">
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
						</svg>
						${__("Filter")}
						<span id="tm-filter-count" class="tm-filter-badge" style="display:none;">0</span>
					</button>

					<!-- Generate split dropdown -->
					<div class="tm-dropdown" id="tm-gen-dropdown">
						<div class="tm-split-group">
							<button type="button" class="tm-btn tm-btn-primary" id="tm-gen-quick-btn"
								title="${__("Generate for selected students")}">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
									fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
									<polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/>
									<polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/>
								</svg>
								${__("Generate")}
							</button>
							<button type="button" class="tm-btn tm-btn-primary" id="tm-gen-caret-btn"
								title="${__("More generate options")}">
								<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
									fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
									<polyline points="6 9 12 15 18 9"/>
								</svg>
							</button>
						</div>
						<ul class="tm-dropdown-menu" id="tm-gen-menu">
							<li class="tm-menu-label">${__("Selected Students")}</li>
							<li><a id="tm-gen-interim" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
								${__("Generate Interim Transcript")}
							</a></li>
							<li><a id="tm-gen-final" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="8 17 10 19 14 15"/></svg>
								${__("Generate Final Transcript")}
							</a></li>
							<li class="tm-divider"></li>
							<li class="tm-menu-label">${__("All Filtered Students")}</li>
							<li><a id="tm-gen-all-interim" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
								${__("Interim – All Filtered")}
							</a></li>
							<li><a id="tm-gen-all-final" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/><polyline points="8 11 10 13 14 9"/></svg>
								${__("Final – All Filtered")}
							</a></li>
						</ul>
					</div>

					<!-- Download split dropdown -->
					<div class="tm-dropdown" id="tm-dl-dropdown">
						<div class="tm-split-group">
							<button type="button" class="tm-btn tm-btn-outline" id="tm-dl-quick-btn"
								title="${__("Download for selected student")}">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
									fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
									<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
									<polyline points="7 10 12 15 17 10"/>
									<line x1="12" y1="15" x2="12" y2="3"/>
								</svg>
								${__("Download")}
							</button>
							<button type="button" class="tm-btn tm-btn-outline" id="tm-dl-caret-btn">
								<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
									fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
									<polyline points="6 9 12 15 18 9"/>
								</svg>
							</button>
						</div>
						<ul class="tm-dropdown-menu" id="tm-dl-menu">
							<li class="tm-menu-label">${__("Download Transcript")}</li>
							<li><a id="tm-dl-interim" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
								${__("Download Interim Transcript")}
							</a></li>
							<li><a id="tm-dl-final" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
								${__("Download Final Transcript")}
							</a></li>
						</ul>
					</div>

					<!-- Year-based transcript actions -->
					<div class="tm-dropdown" id="tm-year-dropdown">
						<button type="button" class="tm-btn tm-btn-outline" id="tm-year-btn"
							title="${__("Year-based transcript options")}">
							<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
								fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
								<polyline points="14 2 14 8 20 8"/>
								<line x1="8" y1="13" x2="16" y2="13"/>
								<line x1="8" y1="17" x2="14" y2="17"/>
							</svg>
							${__("Year-Based")}
							<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
								fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
								<polyline points="6 9 12 15 18 9"/>
							</svg>
						</button>
						<ul class="tm-dropdown-menu" id="tm-year-menu">
							<li class="tm-menu-label">${__("Year-Based Transcript")}</li>
							<li><a id="tm-dl-year-based" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
								${__("Download Year-Based Transcript")}
							</a></li>
							<li><a id="tm-customize-year-based" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
								${__("Customize Year-Based Layout")}
							</a></li>
							<li class="tm-menu-label" style="margin-top:6px;">${__("Compact Format")}</li>
							<li><a id="tm-dl-compact" href="#">
								<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
								${__("Download Compact Transcript")}
							</a></li>
						</ul>
					</div>

					<!-- Templates / Settings -->
					<button id="tm-settings-btn" class="tm-btn tm-btn-default"
						title="${__("Transcript Templates")}">
						<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
							<rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
						</svg>
						${__("Templates")}
					</button>
				</div>
			</div>

			<!-- Stats Bar -->
			<div class="tm-stats-bar">
				<div class="tm-stat-card">
					<div class="tm-stat-icon tm-stat-icon-total">
						<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
							<circle cx="9" cy="7" r="4"/>
							<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
							<path d="M16 3.13a4 4 0 0 1 0 7.75"/>
						</svg>
					</div>
					<div class="tm-stat-body">
						<div class="tm-stat-value" id="tm-stat-total">—</div>
						<div class="tm-stat-label">${__("Total Students")}</div>
					</div>
				</div>
				<div class="tm-stat-card">
					<div class="tm-stat-icon tm-stat-icon-interim">
						<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
							<polyline points="14 2 14 8 20 8"/>
							<line x1="8" y1="13" x2="16" y2="13"/>
							<line x1="8" y1="17" x2="14" y2="17"/>
						</svg>
					</div>
					<div class="tm-stat-body">
						<div class="tm-stat-value" id="tm-stat-interim">—</div>
						<div class="tm-stat-label">${__("Interim Generated")}</div>
					</div>
				</div>
				<div class="tm-stat-card">
					<div class="tm-stat-icon tm-stat-icon-final">
						<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
							<polyline points="14 2 14 8 20 8"/>
							<polyline points="8 17 10 19 14 15"/>
						</svg>
					</div>
					<div class="tm-stat-body">
						<div class="tm-stat-value" id="tm-stat-final">—</div>
						<div class="tm-stat-label">${__("Final Generated")}</div>
					</div>
				</div>
				<div class="tm-stat-card">
					<div class="tm-stat-icon tm-stat-icon-pending">
						<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<circle cx="12" cy="12" r="10"/>
							<polyline points="12 6 12 12 16 14"/>
						</svg>
					</div>
					<div class="tm-stat-body">
						<div class="tm-stat-value" id="tm-stat-pending">—</div>
						<div class="tm-stat-label">${__("Pending Final")}</div>
					</div>
				</div>
			</div>

			<!-- Filter Panel -->
			<div id="tm-filter-panel" class="tm-filter-panel" style="display:none;">
				<div class="tm-filter-panel-title">${__("Filter Students")}</div>
				<div class="tm-filter-grid">
					<div class="tm-filter-field">
						<label>${__("Programme")}</label>
						<select id="tm-f-programme" class="tm-filter-select tm-filter-sel">
							<option value="">${__("All Programmes")}</option>
						</select>
					</div>
					<div class="tm-filter-field">
						<label>${__("Department")}</label>
						<select id="tm-f-department" class="tm-filter-select tm-filter-sel">
							<option value="">${__("All Departments")}</option>
						</select>
					</div>
					<div class="tm-filter-field">
						<label>${__("Course")}</label>
						<select id="tm-f-course" class="tm-filter-select tm-filter-sel">
							<option value="">${__("All Courses")}</option>
						</select>
					</div>
					<div class="tm-filter-field">
						<label>${__("Academic Year")}</label>
						<select id="tm-f-academic-year" class="tm-filter-select tm-filter-sel">
							<option value="">${__("All Years")}</option>
						</select>
					</div>
					<div class="tm-filter-field">
						<label>${__("Batch")}</label>
						<select id="tm-f-batch" class="tm-filter-select tm-filter-sel">
							<option value="">${__("All Batches")}</option>
						</select>
					</div>
					<div class="tm-filter-field">
						<label>${__("Academic Status")}</label>
						<select id="tm-f-status" class="tm-filter-select tm-filter-sel">
							<option value="">${__("All Statuses")}</option>
						</select>
					</div>
				</div>
				<div class="tm-filter-actions">
					<button id="tm-apply-filter" class="tm-btn tm-btn-primary">
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="20 6 9 17 4 12"/>
						</svg>
						${__("Apply Filters")}
					</button>
					<button id="tm-clear-filter" class="tm-btn tm-btn-default">
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
						</svg>
						${__("Clear All")}
					</button>
				</div>
			</div>

			<!-- Active Filter Tags -->
			<div id="tm-active-tags" class="tm-tags"></div>

			<!-- DataTable Card -->
			<div class="tm-table-card">

				<!-- Top bar: show-entries selector -->
				<div class="tm-dt-topbar">
					<div class="tm-dt-entries">
						${__("Show")}
						<select id="tm-page-length" class="tm-dt-select">
							<option value="10">10</option>
							<option value="25">25</option>
							<option value="50" selected>50</option>
							<option value="100">100</option>
						</select>
						${__("entries")}
					</div>
					<div class="tm-dt-topbar-right" id="tm-count-badge"></div>
				</div>

				<table class="tm-table">
					<thead>
						<tr>
							<th style="width:38px; padding:9px 12px;">
								<input type="checkbox" id="tm-select-all" class="tm-checkbox"
									title="${__("Select / deselect all on this page")}" />
							</th>
							<th class="tm-sortable" data-sort="student_name" style="min-width:180px;">
								${__("Student")}
								<span class="tm-sort-icon" data-col="student_name">↕</span>
							</th>
							<th style="min-width:140px;">${__("Learning Pathway(s)")}</th>
							<th class="tm-sortable" data-sort="registration_id" style="min-width:110px;">
								${__("Reg. ID")}
								<span class="tm-sort-icon" data-col="registration_id">↓</span>
							</th>
							<th style="text-align:center; width:90px;">${__("Credits")}</th>
							<th class="tm-sortable tm-col-accent" data-sort="cgpa" style="text-align:center; width:80px;">
								${__("CGPA")}
								<span class="tm-sort-icon" data-col="cgpa">↕</span>
							</th>
							<th class="tm-col-accent" style="text-align:center; width:120px;">${__("Interim")}</th>
							<th style="text-align:center; width:120px;">${__("Final")}</th>
						</tr>
					</thead>
					<tbody id="tm-tbody">
						<tr>
							<td colspan="8" style="text-align:center; padding:48px; color:#aaa;">
								<div class="tm-spinner"></div>
								${__("Loading students...")}
							</td>
						</tr>
					</tbody>
				</table>

				<!-- Bottom bar: info + page navigation -->
				<div class="tm-dt-bottombar">
					<span id="tm-page-info" class="tm-page-info"></span>
					<div class="tm-page-controls" id="tm-page-controls"></div>
				</div>

			</div>

		</div>

		<!-- Selection Action Bar (fixed bottom) -->
		<div id="tm-sel-bar" class="tm-sel-bar">
			<span id="tm-sel-count" class="tm-sel-count">0</span>
			<span class="tm-sel-label">${__("selected")}</span>
			<div class="tm-sel-divider"></div>
			<button id="tm-sel-gen-interim" class="tm-sel-action tm-sel-interim">
				<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
				${__("Generate Interim")}
			</button>
			<button id="tm-sel-gen-final" class="tm-sel-action tm-sel-final">
				<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="8 17 10 19 14 15"/></svg>
				${__("Generate Final")}
			</button>
			<button id="tm-sel-year" class="tm-sel-action tm-sel-year">
				<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
				${__("Year-Based PDF")}
			</button>
			<button id="tm-sel-clear" class="tm-sel-clear">✕ ${__("Clear selection")}</button>
		</div>
	`);

	// ── Dropdown close-on-outside-click ───────────────────────────────────────
	$(document).on("click.tm", function (e) {
		if (!$(e.target).closest("#tm-gen-dropdown, #tm-dl-dropdown, #tm-year-dropdown").length) {
			$(wrapper).find(".tm-dropdown-menu").removeClass("open");
		}
	});

	// ── Event Bindings ─────────────────────────────────────────────────────────

	// Search debounce
	let searchTimer;
	$(wrapper).on("input", "#tm-search", function () {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			state.search = $(this).val().trim();
			state.page = 1;
			load_students();
		}, 350);
	});

	// Filter panel toggle
	$(wrapper).on("click", "#tm-filter-btn", function () {
		$(wrapper).find("#tm-filter-panel").slideToggle(180);
	});

	// Generate caret → open dropdown
	$(wrapper).on("click", "#tm-gen-caret-btn", function (e) {
		e.stopPropagation();
		$(wrapper).find("#tm-dl-menu, #tm-year-menu").removeClass("open");
		$(wrapper).find("#tm-gen-menu").toggleClass("open");
	});
	// Generate main button → quick shortcut (interim for selection)
	$(wrapper).on("click", "#tm-gen-quick-btn", function () {
		$(wrapper).find("#tm-gen-menu").removeClass("open");
		handle_generate("Interim", false);
	});

	// Download caret
	$(wrapper).on("click", "#tm-dl-caret-btn", function (e) {
		e.stopPropagation();
		$(wrapper).find("#tm-gen-menu, #tm-year-menu").removeClass("open");
		$(wrapper).find("#tm-dl-menu").toggleClass("open");
	});
	// Download main button → quick shortcut (final)
	$(wrapper).on("click", "#tm-dl-quick-btn", function () {
		$(wrapper).find("#tm-dl-menu").removeClass("open");
		handle_download("Final");
	});

	// Year-based menu
	$(wrapper).on("click", "#tm-year-btn", function (e) {
		e.stopPropagation();
		$(wrapper).find("#tm-gen-menu, #tm-dl-menu").removeClass("open");
		$(wrapper).find("#tm-year-menu").toggleClass("open");
	});

	// Apply filters
	$(wrapper).on("click", "#tm-apply-filter", function () {
		state.programme      = $(wrapper).find("#tm-f-programme").val();
		state.department     = $(wrapper).find("#tm-f-department").val();
		state.course         = $(wrapper).find("#tm-f-course").val();
		state.academic_year  = $(wrapper).find("#tm-f-academic-year").val();
		state.batch          = $(wrapper).find("#tm-f-batch").val();
		state.student_status = $(wrapper).find("#tm-f-status").val();
		state.page = 1;
		render_active_tags();
		update_filter_count_badge();
		load_students();
	});

	// Clear filters
	$(wrapper).on("click", "#tm-clear-filter", function () {
		$(wrapper).find(".tm-filter-sel").val("");
		state.programme = state.department = state.course =
		state.academic_year = state.batch = state.student_status = "";
		state.page = 1;
		render_active_tags();
		update_filter_count_badge();
		load_students();
	});

	// Select all (current page)
	$(wrapper).on("change", "#tm-select-all", function () {
		const checked = $(this).is(":checked");
		$(wrapper).find(".tm-row-check").prop("checked", checked).each(function () {
			const sid = $(this).data("student");
			if (checked) state.selected.add(sid);
			else         state.selected.delete(sid);
		});
		update_selection_bar();
	});

	// Row checkboxes
	$(wrapper).on("change", ".tm-row-check", function () {
		const sid = $(this).data("student");
		if ($(this).is(":checked")) state.selected.add(sid);
		else                        state.selected.delete(sid);
		const total = $(wrapper).find(".tm-row-check").length;
		const sel   = $(wrapper).find(".tm-row-check:checked").length;
		$(wrapper).find("#tm-select-all")
			.prop("indeterminate", sel > 0 && sel < total)
			.prop("checked", sel === total && total > 0);
		update_selection_bar();
	});

	// Generate actions
	$(wrapper).on("click", "#tm-gen-interim",     function (e) { e.preventDefault(); $(wrapper).find("#tm-gen-menu").removeClass("open"); handle_generate("Interim", false); });
	$(wrapper).on("click", "#tm-gen-final",       function (e) { e.preventDefault(); $(wrapper).find("#tm-gen-menu").removeClass("open"); handle_generate("Final", false); });
	$(wrapper).on("click", "#tm-gen-all-interim", function (e) { e.preventDefault(); $(wrapper).find("#tm-gen-menu").removeClass("open"); handle_generate("Interim", true); });
	$(wrapper).on("click", "#tm-gen-all-final",   function (e) { e.preventDefault(); $(wrapper).find("#tm-gen-menu").removeClass("open"); handle_generate("Final", true); });

	// Download actions
	$(wrapper).on("click", "#tm-dl-interim", function (e) { e.preventDefault(); $(wrapper).find("#tm-dl-menu").removeClass("open"); handle_download("Interim"); });
	$(wrapper).on("click", "#tm-dl-final",   function (e) { e.preventDefault(); $(wrapper).find("#tm-dl-menu").removeClass("open"); handle_download("Final"); });
	$(wrapper).on("click", "#tm-dl-year-based",       function (e) { e.preventDefault(); $(wrapper).find("#tm-year-menu").removeClass("open"); handle_year_based_download(); });
	$(wrapper).on("click", "#tm-customize-year-based", function (e) { e.preventDefault(); $(wrapper).find("#tm-year-menu").removeClass("open"); frappe.set_route("Form", "Transcript Settings"); });
	$(wrapper).on("click", "#tm-dl-compact",           function (e) { e.preventDefault(); $(wrapper).find("#tm-year-menu").removeClass("open"); handle_compact_download(); });

	// Settings / Templates
	$(wrapper).on("click", "#tm-settings-btn", function () {
		frappe.set_route("transcript-template-page");
	});

	// Sort columns
	$(wrapper).on("click", ".tm-sortable", function () {
		const col = $(this).data("sort");
		if (state.sort_by === col) {
			state.sort_order = state.sort_order === "asc" ? "desc" : "asc";
		} else {
			state.sort_by    = col;
			state.sort_order = "asc";
		}
		state.page = 1;
		update_sort_indicators();
		load_students();
	});

	// Page-length selector
	$(wrapper).on("change", "#tm-page-length", function () {
		state.page_length = parseInt($(this).val());
		state.page = 1;
		load_students();
	});

	// ── Inline badge actions ───────────────────────────────────────────────────

	// Click "—" / "Revoked" badge → generate transcript for that student
	$(wrapper).on("click", ".tm-inline-gen", function (e) {
		e.stopPropagation();
		const student = $(this).data("student");
		const type    = $(this).data("type");
		frappe.confirm(
			__("Generate {0} Transcript for this student?", [type]),
			function () { do_generate([student], type); }
		);
	});

	// Click "Generated" badge → download transcript for that student
	$(wrapper).on("click", ".tm-inline-dl", function (e) {
		e.stopPropagation();
		const student = $(this).data("student");
		const type    = $(this).data("type");
		handle_download_single(student, type);
	});

	// ── Selection bar actions ──────────────────────────────────────────────────
	$(wrapper).on("click", "#tm-sel-gen-interim", function () {
		handle_generate("Interim", false);
	});
	$(wrapper).on("click", "#tm-sel-gen-final", function () {
		handle_generate("Final", false);
	});
	$(wrapper).on("click", "#tm-sel-year", function () {
		handle_year_based_download();
	});
	$(wrapper).on("click", "#tm-sel-clear", function () {
		state.selected.clear();
		$(wrapper).find(".tm-row-check").prop("checked", false);
		$(wrapper).find("#tm-select-all").prop("checked", false).prop("indeterminate", false);
		update_selection_bar();
	});

	// ── Functions ──────────────────────────────────────────────────────────────

	function update_selection_bar() {
		const count = state.selected.size;
		const bar   = $(wrapper).find("#tm-sel-bar");
		$(wrapper).find("#tm-sel-count").text(count);
		if (count > 0) {
			bar.addClass("tm-sel-bar--visible");
		} else {
			bar.removeClass("tm-sel-bar--visible");
		}
	}

	function load_stats() {
		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.get_transcript_stats",
			args: {
				search:         state.search,
				programme:      state.programme,
				course:         state.course,
				academic_year:  state.academic_year,
				batch:          state.batch,
				student_status: state.student_status,
				department:     state.department,
			},
			callback: function (r) {
				if (!r.message) return;
				const s = r.message;
				$(wrapper).find("#tm-stat-total").text(s.total_students || 0);
				$(wrapper).find("#tm-stat-interim").text(s.interim_generated || 0);
				$(wrapper).find("#tm-stat-final").text(s.final_generated || 0);
				const pending = (s.total_students || 0) - (s.final_generated || 0);
				$(wrapper).find("#tm-stat-pending").text(pending > 0 ? pending : 0);
			},
		});
	}

	function load_filter_options() {
		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.get_filter_options",
			callback: function (r) {
				if (!r.message) return;
				state.filter_options = r.message;

				const prog_sel   = $(wrapper).find("#tm-f-programme");
				const dept_sel   = $(wrapper).find("#tm-f-department");
				const course_sel = $(wrapper).find("#tm-f-course");
				const yr_sel     = $(wrapper).find("#tm-f-academic-year");
				const bat_sel    = $(wrapper).find("#tm-f-batch");
				const stat_sel   = $(wrapper).find("#tm-f-status");

				(r.message.programmes || []).forEach(p => {
					const label = p.cohort_name || p.name;
					state._prog_labels[p.name] = label;
					prog_sel.append(`<option value="${p.name}">${frappe.utils.escape_html(label)}</option>`);
				});
				(r.message.departments || []).forEach(d => {
					const label = d.department_name || d.name;
					state._dept_labels[d.name] = label;
					dept_sel.append(`<option value="${d.name}">${frappe.utils.escape_html(label)}</option>`);
				});
				(r.message.courses || []).forEach(c => {
					const label = c.course_name + (c.course_code ? ` (${c.course_code})` : "");
					course_sel.append(`<option value="${c.name}">${frappe.utils.escape_html(label)}</option>`);
				});
				(r.message.academic_years || []).forEach(y => {
					yr_sel.append(`<option value="${y}">${frappe.utils.escape_html(y)}</option>`);
				});
				(r.message.batches || []).forEach(b => {
					bat_sel.append(`<option value="${b}">${frappe.utils.escape_html(b)}</option>`);
				});
				(r.message.student_statuses || []).forEach(s => {
					stat_sel.append(`<option value="${s}">${frappe.utils.escape_html(s)}</option>`);
				});

				prog_sel.val(state.programme);
				dept_sel.val(state.department);
				course_sel.val(state.course);
				yr_sel.val(state.academic_year);
				bat_sel.val(state.batch);
				stat_sel.val(state.student_status);
			}
		});
	}

	function load_students() {
		if (state.loading) return;
		state.loading = true;

		$(wrapper).find("#tm-tbody").html(`
			<tr>
				<td colspan="8" style="text-align:center; padding:48px; color:#aaa;">
					<div class="tm-spinner"></div>
					${__("Loading students...")}
				</td>
			</tr>`);

		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.get_students",
			args: {
				search:         state.search,
				programme:      state.programme,
				course:         state.course,
				academic_year:  state.academic_year,
				batch:          state.batch,
				student_status: state.student_status,
				department:     state.department,
				page:           state.page,
				page_length:    state.page_length,
				sort_by:        state.sort_by,
				sort_order:     state.sort_order,
			},
			callback: function (r) {
				state.loading = false;
				if (!r.message) return;
				const { students, total } = r.message;
				state.total = total;
				render_table(students, total);
				render_pagination();
				load_stats();
			},
			error: function () {
				state.loading = false;
				$(wrapper).find("#tm-tbody").html(`
					<tr><td colspan="8" style="text-align:center; padding:32px; color:#c84630;">
						<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
							style="display:block;margin:0 auto 8px;opacity:.6;">
							<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
						</svg>
						${__("Error loading students. Please try again.")}
					</td></tr>`);
			}
		});
	}

	function render_table(students, total) {
		const tbody = $(wrapper).find("#tm-tbody");
		$(wrapper).find("#tm-count-badge").text(total ? `${total} ${__("record(s) found")}` : "");

		if (!students || students.length === 0) {
			tbody.html(`
				<tr><td colspan="8" style="text-align:center; padding:56px; color:#bbb;">
					<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24"
						fill="none" stroke="#ddd" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
						style="display:block;margin:0 auto 12px;">
						<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
						<circle cx="9" cy="7" r="4"/>
						<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
						<path d="M16 3.13a4 4 0 0 1 0 7.75"/>
					</svg>
					<div style="font-size:14px;font-weight:600;color:#aaa;margin-bottom:4px;">${__("No students found")}</div>
					<div style="font-size:12px;">${__("Try adjusting your filters or search query.")}</div>
				</td></tr>`);
			return;
		}

		const rows = students.map((s) => {
			const name   = frappe.utils.escape_html(s.student_name || "");
			const regId  = frappe.utils.escape_html(s.registration_id || "—");
			const email  = frappe.utils.escape_html(s.email || "");
			const prog   = frappe.utils.escape_html(s.programme_name || s.programme || "");
			const batch  = frappe.utils.escape_html(s.batch_year || "");
			const acYear = frappe.utils.escape_html(s.academic_year || "");
			const checked = state.selected.has(s.student) ? "checked" : "";

			const initials = (name.trim()[0] || "?").toUpperCase();
			const photoSrc = s.photo
				? `<img src="${s.photo}" class="tm-avatar" onerror="this.outerHTML='<div class=\\'tm-avatar-initials\\'>${initials}</div>'">`
				: `<div class="tm-avatar-initials">${initials}</div>`;

			// Learning pathways
			let pathwayHtml = `<span style="color:#ccc;">—</span>`;
			if (s.learning_pathways && s.learning_pathways.length) {
				pathwayHtml = s.learning_pathways.map(p => {
					const type  = frappe.utils.escape_html(p.type || "Major");
					const pname = frappe.utils.escape_html(p.program_name || p.program || "");
					return `<div style="line-height:1.5;">
						<span style="font-size:10px;color:#aaa;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">${type}</span>
						<span style="color:#bbb;"> · </span>
						<span style="font-size:12px;font-weight:600;color:#333;">${pname}</span>
					</div>`;
				}).join("");
			}

			// Credits
			const earned  = s.earned_credits || 0;
			const total_c = s.total_credits  || 0;
			const credHtml = `<span style="font-weight:700;font-size:13px;">${earned}</span>`
				+ `<span style="color:#ccc;margin:0 2px;">/</span>`
				+ `<span style="color:#888;font-size:12px;">${total_c}</span>`;

			// CGPA
			let cgpaHtml = `<span style="color:#ccc;">—</span>`;
			if (s.cgpa !== null && s.cgpa !== undefined && s.cgpa !== "") {
				const v = parseFloat(s.cgpa);
				const color = v >= 7.0 ? "#1a7a36" : v >= 5.0 ? "#b45309" : "#c84630";
				const bg    = v >= 7.0 ? "#e6f4ea" : v >= 5.0 ? "#fef3e6" : "#fdecea";
				cgpaHtml = `<span style="font-weight:700;color:${color};background:${bg};padding:3px 10px;border-radius:20px;font-size:12px;">${v.toFixed(2)}</span>`;
			}

			// Status pill
			const statusPill = s.student_status ? status_pill(s.student_status) : "";

			// Sub-info
			const subParts = [prog, batch ? `Batch ${batch}` : "", acYear].filter(Boolean);
			const subInfo = subParts.join(" · ");

			return `
				<tr data-student="${s.student}">
					<td style="padding:11px 14px;">
						<input type="checkbox" class="tm-row-check tm-checkbox" data-student="${s.student}" ${checked} />
					</td>
					<td>
						<div style="display:flex;align-items:flex-start;gap:10px;">
							${photoSrc}
							<div>
								<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
									<a href="/app/student-master/${s.student}" class="tm-student-link">${name}</a>
									${statusPill}
								</div>
								<div style="font-size:11px;color:#bbb;margin-top:1px;">${email}</div>
								${subInfo ? `<div style="font-size:11px;color:#888;margin-top:2px;">${subInfo}</div>` : ""}
							</div>
						</div>
					</td>
					<td>${pathwayHtml}</td>
					<td style="font-size:12px;color:#555;white-space:nowrap;">${regId}</td>
					<td style="text-align:center;">${credHtml}</td>
					<td style="text-align:center;">${cgpaHtml}</td>
					<td style="text-align:center;">${interactive_badge(s.interim_transcript, s.student, "Interim")}</td>
					<td style="text-align:center;">${interactive_badge(s.final_transcript, s.student, "Final")}</td>
				</tr>`;
		});

		tbody.html(rows.join(""));

		// Restore select-all state
		const total_rows = $(wrapper).find(".tm-row-check").length;
		const sel_rows   = $(wrapper).find(".tm-row-check:checked").length;
		$(wrapper).find("#tm-select-all")
			.prop("indeterminate", sel_rows > 0 && sel_rows < total_rows)
			.prop("checked", sel_rows === total_rows && total_rows > 0);
	}

	/**
	 * Returns an interactive HTML badge for a transcript status cell.
	 * - Empty/null → dashed "Generate" button
	 * - "Generated" → clickable green badge → downloads transcript
	 * - "Revoked"   → clickable red badge → re-generates
	 */
	function interactive_badge(status, student, type) {
		const sid = frappe.utils.escape_html(student);
		if (!status) {
			return `<button class="tm-gen-badge tm-inline-gen"
				data-student="${sid}" data-type="${type}"
				title="${__("Click to generate {0} transcript", [type])}">
				+ ${__("Generate")}
			</button>`;
		}
		const s = status.toLowerCase();
		if (s === "generated") {
			return `<button class="tm-badge tm-badge-generated tm-inline-dl"
				data-student="${sid}" data-type="${type}"
				title="${__("Click to download {0} transcript", [type])}">
				<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
					fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="20 6 9 17 4 12"/>
				</svg>
				${__("Generated")}
			</button>`;
		}
		if (s === "revoked") {
			return `<button class="tm-badge tm-badge-revoked tm-inline-gen"
				data-student="${sid}" data-type="${type}"
				title="${__("Click to re-generate {0} transcript", [type])}">
				<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
					fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
					<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
				</svg>
				${__("Revoked")}
			</button>`;
		}
		return `<span class="tm-badge tm-badge-pending">${frappe.utils.escape_html(status)}</span>`;
	}

	function status_pill(status) {
		const s   = (status || "").toLowerCase();
		const cls = {
			active:    "tm-status-active",
			inactive:  "tm-status-inactive",
			graduated: "tm-status-graduated",
			dropped:   "tm-status-dropped",
			alumni:    "tm-status-alumni",
			dormant:   "tm-status-dormant",
		}[s] || "tm-status-inactive";
		return `<span class="tm-status-pill ${cls}">${frappe.utils.escape_html(status)}</span>`;
	}

	function render_pagination() {
		const total_pages = Math.ceil(state.total / state.page_length) || 1;
		const from = state.total ? (state.page - 1) * state.page_length + 1 : 0;
		const to   = Math.min(state.page * state.page_length, state.total);

		// Info text (bottom-left, DataTables style)
		$(wrapper).find("#tm-page-info").text(
			state.total
				? `${__("Showing")} ${from} ${__("to")} ${to} ${__("of")} ${state.total} ${__("entries")}`
				: __("No entries found")
		);

		// Page number buttons (bottom-right)
		const controls = $(wrapper).find("#tm-page-controls");
		controls.empty();

		// Previous button
		const prev = $(`<button class="tm-page-btn"${state.page <= 1 ? " disabled" : ""}>‹ ${__("Previous")}</button>`);
		prev.on("click", function () { if (state.page > 1) { state.page--; load_students(); } });
		controls.append(prev);

		// Determine visible page window (max 5 pages shown)
		const win = 5;
		let start = Math.max(1, state.page - Math.floor(win / 2));
		let end   = Math.min(total_pages, start + win - 1);
		if (end - start < win - 1) start = Math.max(1, end - win + 1);

		if (start > 1) {
			const b1 = $(`<button class="tm-page-num">1</button>`);
			b1.on("click", function () { state.page = 1; load_students(); });
			controls.append(b1);
			if (start > 2) controls.append(`<span class="tm-page-ellipsis">…</span>`);
		}

		for (let i = start; i <= end; i++) {
			const pg  = i;
			const btn = $(`<button class="tm-page-num${i === state.page ? " active" : ""}">${i}</button>`);
			btn.on("click", function () { state.page = pg; load_students(); });
			controls.append(btn);
		}

		if (end < total_pages) {
			if (end < total_pages - 1) controls.append(`<span class="tm-page-ellipsis">…</span>`);
			const blast = $(`<button class="tm-page-num">${total_pages}</button>`);
			blast.on("click", function () { state.page = total_pages; load_students(); });
			controls.append(blast);
		}

		// Next button
		const next = $(`<button class="tm-page-btn"${state.page >= total_pages ? " disabled" : ""}>${__("Next")} ›</button>`);
		next.on("click", function () { if (state.page < total_pages) { state.page++; load_students(); } });
		controls.append(next);
	}

	// Filter key → select element ID map
	const FILTER_KEY_TO_ID = {
		programme:      "tm-f-programme",
		department:     "tm-f-department",
		course:         "tm-f-course",
		academic_year:  "tm-f-academic-year",
		batch:          "tm-f-batch",
		student_status: "tm-f-status",
	};

	function get_filter_label(key, value) {
		if (!value) return null;
		const prefix = {
			programme:      __("Programme"),
			department:     __("Department"),
			course:         __("Course"),
			academic_year:  __("Year"),
			batch:          __("Batch"),
			student_status: __("Status"),
		}[key] || key;
		let display = value;
		if (key === "programme" && state._prog_labels[value]) display = state._prog_labels[value];
		if (key === "department" && state._dept_labels[value]) display = state._dept_labels[value];
		return `${prefix}: ${display}`;
	}

	function render_active_tags() {
		const container = $(wrapper).find("#tm-active-tags");
		container.empty();
		const keys = ["programme", "department", "course", "academic_year", "batch", "student_status"];
		keys.forEach(key => {
			const value = state[key];
			const label = get_filter_label(key, value);
			if (!label) return;
			const tag = $(`
				<span class="tm-tag">
					${frappe.utils.escape_html(label)}
					<button class="tm-tag-remove" data-key="${key}" title="${__("Remove filter")}">
						<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
							<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
						</svg>
					</button>
				</span>`);
			tag.find("button").on("click", function () {
				const k = $(this).data("key");
				state[k] = "";
				const sid = FILTER_KEY_TO_ID[k];
				if (sid) $(wrapper).find(`#${sid}`).val("");
				render_active_tags();
				update_filter_count_badge();
				state.page = 1;
				load_students();
			});
			container.append(tag);
		});
	}

	function update_filter_count_badge() {
		const keys = ["programme", "department", "course", "academic_year", "batch", "student_status"];
		const active = keys.filter(k => !!state[k]).length;
		const badge = $(wrapper).find("#tm-filter-count");
		if (active > 0) {
			badge.text(active).show();
		} else {
			badge.hide();
		}
	}

	function update_sort_indicators() {
		$(wrapper).find(".tm-sort-icon").removeClass("asc desc").text("↕");
		const ind = $(wrapper).find(`.tm-sort-icon[data-col="${state.sort_by}"]`);
		if (state.sort_order === "asc") {
			ind.addClass("asc").text("↑");
		} else {
			ind.addClass("desc").text("↓");
		}
	}

	function get_selected_students() {
		return [...state.selected];
	}

	function handle_generate(type, all_filtered) {
		if (all_filtered) {
			const filterDesc = build_filter_description();
			const msg = filterDesc
				? __("Generate {0} Transcript for ALL students matching: {1}?", [type, filterDesc])
				: __("Generate {0} Transcript for ALL {1} students?", [type, state.total]);

			frappe.confirm(msg, function () {
				frappe.call({
					method: "slcm.slcm.page.transcript_management_page.transcript_management_page.get_students",
					args: {
						search:         state.search,
						programme:      state.programme,
						course:         state.course,
						academic_year:  state.academic_year,
						batch:          state.batch,
						student_status: state.student_status,
						department:     state.department,
						page:           1,
						page_length:    10000,
						sort_by:        "registration_id",
						sort_order:     "asc",
					},
					callback: function (r) {
						if (!r.message || !r.message.students.length) {
							frappe.msgprint(__("No students found to generate transcripts for."));
							return;
						}
						do_generate(r.message.students.map(s => s.student), type);
					}
				});
			});
		} else {
			const students = get_selected_students();
			if (!students.length) {
				frappe.msgprint(__("Please select at least one student, or use 'Generate – All Filtered' from the dropdown."));
				return;
			}
			frappe.confirm(
				__("Generate {0} Transcript for {1} selected student(s)?", [type, students.length]),
				function () { do_generate(students, type); }
			);
		}
	}

	function do_generate(students, type) {
		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.generate_transcript",
			args: {
				students:        JSON.stringify(students),
				transcript_type: type,
			},
			freeze: true,
			freeze_message: __("Generating transcripts..."),
			callback: function (r) {
				if (!r.message) return;
				const ok  = r.message.filter(x => x.success).length;
				const err = r.message.filter(x => !x.success).length;
				frappe.show_alert({
					message:   ok + " " + __("transcript(s) generated.") + (err ? "  " + err + " " + __("failed.") : ""),
					indicator: err ? "orange" : "green",
				}, 5);
				state.selected.clear();
				update_selection_bar();
				load_students();
			}
		});
	}

	function handle_download(type) {
		const students = get_selected_students();
		if (!students.length) {
			frappe.msgprint(__("Please select a student to download the transcript."));
			return;
		}
		if (students.length > 1) {
			frappe.msgprint(__("Please select only one student at a time for download."));
			return;
		}
		handle_download_single(students[0], type);
	}

	function handle_download_single(student, type) {
		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.download_transcript",
			args: { student, transcript_type: type },
			callback: function (r) {
				if (!r.message) return;
				const info = r.message;
				if (info.print_url) {
					window.open(info.print_url, "_blank");
				} else {
					frappe.msgprint({
						title:   __("Transcript Info"),
						message: `${__("Type")}: ${info.transcript_type}<br>${__("Status")}: ${info.status}<br>${__("Generated on")}: ${info.generation_date}`,
					});
				}
			},
			error: function () {
				frappe.msgprint({
					title:     __("Transcript Not Found"),
					message:   __("No {0} transcript exists for this student. Please generate it first.", [type]),
					indicator: "orange",
				});
			}
		});
	}

	function handle_year_based_download() {
		const students = get_selected_students();
		if (!students.length) {
			frappe.msgprint(__("Please select a student to download the year-based transcript."));
			return;
		}
		if (students.length > 1) {
			frappe.msgprint(__("Please select only one student at a time for year-based transcript download."));
			return;
		}

		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.download_year_based_transcript",
			args: { student: students[0] },
			callback: function (r) {
				if (r.message && r.message.print_url) {
					window.open(r.message.print_url, "_blank");
				}
			},
			error: function () {
				frappe.msgprint({
					title: __("Year-Based Transcript"),
					message: __("Could not prepare the year-based transcript. Please check Transcript Settings and try again."),
					indicator: "orange",
				});
			}
		});
	}

	function handle_compact_download() {
		const students = get_selected_students();
		if (!students.length) {
			frappe.msgprint(__("Please select a student to download the compact transcript."));
			return;
		}
		if (students.length > 1) {
			frappe.msgprint(__("Please select only one student at a time for compact transcript download."));
			return;
		}

		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.download_compact_transcript",
			args: { student: students[0] },
			callback: function (r) {
				if (r.message && r.message.print_url) {
					window.open(r.message.print_url, "_blank");
				}
			},
			error: function (r) {
				const msg = (r && r.message) || __("No approved Final or Interim Transcript Request found for this student. The student must submit and get a transcript request approved before downloading the compact transcript.");
				frappe.msgprint({
					title: __("Compact Transcript"),
					message: msg,
					indicator: "orange",
				});
			}
		});
	}

	function build_filter_description() {
		const parts = [];
		if (state.search)         parts.push(`"${state.search}"`);
		if (state.programme)      parts.push(__("Programme") + ": " + (state._prog_labels[state.programme] || state.programme));
		if (state.department)     parts.push(__("Dept") + ": " + (state._dept_labels[state.department] || state.department));
		if (state.course)         parts.push(__("Course") + ": " + state.course);
		if (state.academic_year)  parts.push(__("Year") + ": " + state.academic_year);
		if (state.batch)          parts.push(__("Batch") + ": " + state.batch);
		if (state.student_status) parts.push(__("Status") + ": " + state.student_status);
		return parts.join(", ");
	}

	// ── Initial Load ───────────────────────────────────────────────────────────
	update_sort_indicators();
	load_filter_options();
	load_students();

};
