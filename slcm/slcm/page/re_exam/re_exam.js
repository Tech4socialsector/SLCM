frappe.pages['re-exam'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Re Exam',
		single_column: true,
	});

	// ── CSS ───────────────────────────────────────────────────────────────────
	if (!document.getElementById('rx-style')) {
		var style = document.createElement('style');
		style.id  = 'rx-style';
		style.textContent = `
		.er2-wrap        { font-family:var(--font-stack,'Inter',sans-serif); padding:0; background:#f1f5f9; min-height:100vh; }
		.er2-page-header { background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:16px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); display:flex; align-items:center; gap:16px; }
		.er2-page-icon   { width:46px; height:46px; border-radius:12px; flex-shrink:0;
		                   display:flex; align-items:center; justify-content:center; }
		.er2-page-title  { font-size:17px; font-weight:800; color:#0f172a; line-height:1.2; }
		.er2-page-sub    { font-size:12px; color:#94a3b8; margin-top:3px; font-weight:500; }
		.er2-page-nav    { display:flex; gap:4px; margin-bottom:16px; background:#e2e8f0;
		                   border-radius:10px; padding:4px; width:fit-content; }
		.er2-pnav-btn    { padding:8px 18px; cursor:pointer; font-size:13px; font-weight:600;
		                   color:#64748b; border-radius:7px; transition:all .2s; user-select:none;
		                   letter-spacing:.1px; border:none; background:transparent;
		                   display:inline-flex; align-items:center; gap:5px; }
		.er2-pnav-btn:hover  { color:#4f46e5; background:rgba(79,70,229,.08); }
		.er2-pnav-btn.active { background:#fff; color:#ef4444; box-shadow:0 1px 4px rgba(0,0,0,.12); }
		.er2-pnav-btn.active svg { stroke:#ef4444; }

		/* Filter card */
		.rx-filter-card  { background:#fff; border-radius:12px; padding:14px 20px; margin-bottom:14px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); display:flex; gap:14px;
		                   align-items:flex-end; flex-wrap:wrap; }
		.rx-fgroup       { display:flex; flex-direction:column; min-width:200px; flex:1; max-width:300px; }
		.rx-fgroup.wide  { max-width:400px; }
		.rx-filter-arrow { display:flex; align-items:flex-end; padding-bottom:9px; color:#cbd5e1; font-size:16px; flex-shrink:0; }
		.rx-active-badge { display:inline-block; border-radius:6px; font-size:10px; font-weight:700;
		                   padding:2px 7px; margin-left:6px; letter-spacing:.3px; vertical-align:middle; }
		.rx-active-badge.prog   { background:#fff0f0; color:#ef4444; }
		.rx-active-badge.course { background:#fff0f0; color:#ef4444; }
		.rx-flabel       { font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:5px;
		                   text-transform:uppercase; letter-spacing:.6px; }
		.rx-select       { height:36px; border:1.5px solid #e2e8f0; border-radius:8px;
		                   padding:0 12px; font-size:13px; background:#fff; color:#1e293b;
		                   outline:none; cursor:pointer; transition:border-color .2s; }
		.rx-select:focus { border-color:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,.1); }

		/* Stat cards */
		.rx-stat-cards   { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
		.rx-stat-card    { background:#fff; border-radius:12px; padding:14px 18px; flex:1;
		                   min-width:150px; box-shadow:0 1px 3px rgba(0,0,0,.06);
		                   border-top:3px solid var(--sc-color,#ef4444);
		                   display:flex; align-items:center; gap:12px; }
		.rx-sc-icon      { width:38px; height:38px; border-radius:9px; flex-shrink:0;
		                   display:flex; align-items:center; justify-content:center;
		                   background:var(--sc-bg,#fff0f0); color:var(--sc-color,#ef4444); }
		.rx-sc-val       { font-size:22px; font-weight:800; color:var(--sc-color,#ef4444); line-height:1.1; }
		.rx-sc-lbl       { font-size:10px; color:#94a3b8; font-weight:700; text-transform:uppercase;
		                   letter-spacing:.6px; margin-top:2px; }

		/* Settings card */
		.rx-settings-card { background:#fff; border-radius:12px; padding:18px 22px; margin-bottom:14px;
		                    box-shadow:0 1px 3px rgba(0,0,0,.06); border-left:4px solid #ef4444; }
		.rx-settings-title { font-size:13px; font-weight:800; color:#0f172a; margin-bottom:14px;
		                     display:flex; align-items:center; gap:8px; }
		.rx-settings-grid  { display:flex; gap:14px; flex-wrap:wrap; align-items:flex-end; }
		.rx-field-group    { display:flex; flex-direction:column; min-width:180px; flex:1; max-width:260px; }
		.rx-field-label    { font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:5px;
		                     text-transform:uppercase; letter-spacing:.6px; }
		.rx-input          { height:36px; border:1.5px solid #e2e8f0; border-radius:8px;
		                     padding:0 12px; font-size:13px; background:#fff; color:#1e293b;
		                     outline:none; transition:border-color .2s; width:100%; box-sizing:border-box; }
		.rx-input:focus    { border-color:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,.1); }
		.rx-save-btn       { height:36px; padding:0 20px; border-radius:8px; border:none;
		                     background:linear-gradient(135deg,#ef4444,#f87171);
		                     color:#fff; font-size:13px; font-weight:700; cursor:pointer;
		                     display:inline-flex; align-items:center; gap:6px; transition:opacity .15s;
		                     white-space:nowrap; }
		.rx-save-btn:hover { opacity:.88; }
		.rx-save-btn:disabled { opacity:.5; cursor:default; }
		.rx-saved-badge    { display:inline-flex; align-items:center; gap:4px; font-size:11px;
		                     font-weight:700; color:#10b981; margin-left:10px;
		                     background:#d1fae5; border-radius:6px; padding:3px 9px; }

		/* Action bar */
		.rx-actbar       { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:12px; }
		.rx-srch         { flex:1; min-width:200px; max-width:380px; position:relative; }
		.rx-srch input   { width:100%; height:36px; border:1.5px solid #e2e8f0; border-radius:8px;
		                   padding:0 12px 0 36px; font-size:13px; outline:none; color:#1e293b;
		                   background:#fff; transition:border-color .2s; box-sizing:border-box; }
		.rx-srch input:focus { border-color:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,.1); }
		.rx-srch-ico     { position:absolute; left:10px; top:10px; color:#94a3b8; }
		.rx-count-lbl    { font-size:13px; font-weight:700; color:#0f172a; }

		/* Table */
		.rx-table-card   { background:#fff; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,.06); overflow:hidden; }
		.rx-table-scroll { overflow-x:auto; }
		.rx-table        { width:100%; border-collapse:collapse; font-size:13px; min-width:700px; }
		.rx-table thead tr { background:#f8fafc; }
		.rx-table th     { padding:10px 14px; text-align:left; font-size:11px; font-weight:700;
		                   color:#475569; border-bottom:1.5px solid #e2e8f0; white-space:nowrap;
		                   text-transform:uppercase; letter-spacing:.4px; background:#f8fafc;
		                   position:sticky; top:0; z-index:5; }
		.rx-table th.center { text-align:center; }
		.rx-table td     { padding:0 14px; border-bottom:1.5px solid #f1f5f9; vertical-align:middle; white-space:nowrap; }
		.rx-table tbody tr { height:66px; }
		.rx-table tbody tr:hover td { background:#fafbff; }
		.rx-table tbody tr:last-child td { border-bottom:none; }

		/* Student cell */
		.rx-savatar      { width:38px; height:38px; border-radius:10px; flex-shrink:0;
		                   display:flex; align-items:center; justify-content:center;
		                   font-size:13px; font-weight:700; color:#fff; overflow:hidden; }
		.rx-savatar img  { width:100%; height:100%; object-fit:cover; }
		.rx-sname        { font-size:13px; font-weight:700; color:#0f172a; }
		.rx-sreg         { font-size:11px; color:#ef4444; font-weight:600; margin-top:2px;
		                   background:#fff0f0; border-radius:4px; padding:1px 6px; display:inline-block; }
		.rx-semail       { font-size:11px; color:#94a3b8; margin-top:2px; }
		.rx-grade-badge  { display:inline-flex; align-items:center; justify-content:center;
		                   min-width:34px; height:26px; border-radius:7px; font-size:12px;
		                   font-weight:800; background:#fff0f0; color:#ef4444;
		                   border:1.5px solid #fecaca; padding:0 8px; }
		.rx-marks        { font-size:13px; font-weight:600; color:#0f172a; }

		/* Pagination */
		.rx-pag-bar      { display:flex; align-items:center; justify-content:space-between;
		                   padding:12px 16px; border-top:1.5px solid #f1f5f9; }
		.rx-pag-info     { font-size:12.5px; color:#64748b; }
		.rx-pag-btns     { display:flex; gap:4px; }
		.rx-pag-btn      { width:30px; height:30px; border:1.5px solid #e2e8f0; border-radius:7px;
		                   background:#fff; cursor:pointer; font-size:14px; display:inline-flex;
		                   align-items:center; justify-content:center; color:#64748b; transition:all .15s; }
		.rx-pag-btn:hover:not(:disabled) { background:#fff0f0; border-color:#fecaca; color:#ef4444; }
		.rx-pag-btn:disabled { opacity:.35; cursor:default; }

		/* Empty / Loading */
		.rx-empty        { padding:80px 20px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
		.rx-empty-icon   { width:56px; height:56px; border-radius:14px; background:#f1f5f9; display:flex; align-items:center; justify-content:center; margin-bottom:14px; }
		.rx-empty-txt    { font-size:14px; font-weight:700; color:#94a3b8; }
		.rx-empty-sub    { font-size:12px; color:#cbd5e1; margin-top:4px; }
		.rx-loading      { padding:60px; text-align:center; color:#94a3b8; font-size:13px; }

		/* Avatar colours */
		.av-0{background:linear-gradient(135deg,#4f46e5,#818cf8);}
		.av-1{background:linear-gradient(135deg,#0ea5e9,#38bdf8);}
		.av-2{background:linear-gradient(135deg,#10b981,#34d399);}
		.av-3{background:linear-gradient(135deg,#f59e0b,#fbbf24);}
		.av-4{background:linear-gradient(135deg,#ef4444,#f87171);}
		.av-5{background:linear-gradient(135deg,#8b5cf6,#a78bfa);}
		.av-6{background:linear-gradient(135deg,#ec4899,#f472b6);}
		.av-7{background:linear-gradient(135deg,#14b8a6,#2dd4bf);}
		`;
		document.head.appendChild(style);
	}

	// ── State ─────────────────────────────────────────────────────────────────
	var S = {
		exam_plan:    null,
		programme:    '',
		course:       '',
		students:     [],
		total:        0,
		page:         1,
		page_length:  20,
		search:       '',
		loading:      false,
		search_timer: null,
	};

	// ── Render shell ──────────────────────────────────────────────────────────
	var $body = $(page.main);
	$body.html(`
		<div class="er2-wrap" style="padding:20px 24px;">

			<div class="er2-page-header">
				<div class="er2-page-icon" style="background:linear-gradient(135deg,#ef4444,#f87171);">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/></svg>
				</div>
				<div>
					<div class="er2-page-title">Re Exam</div>
					<div class="er2-page-sub">Configure re-exam settings and view failed students per course</div>
				</div>
			</div>

			<div class="er2-page-nav">
				<button class="er2-pnav-btn" onclick="frappe.set_route('examination-result')">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
					Course Results
				</button>
				<button class="er2-pnav-btn" onclick="frappe.set_route('term-result')">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
					Term Results
				</button>
				<button class="er2-pnav-btn" onclick="frappe.set_route('publish-result')">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
					Publish Results
				</button>
				<button class="er2-pnav-btn" onclick="frappe.set_route('result-settings')">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
					Settings
				</button>
				<button class="er2-pnav-btn active">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/></svg>
					Re Exam
				</button>
				<button class="er2-pnav-btn" id="rx-nav-consolidated">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
					Consolidated Report
				</button>
			</div>

			<!-- Filter card -->
			<div class="rx-filter-card">
				<div class="rx-fgroup">
					<span class="rx-flabel">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>
						Exam Plan
					</span>
					<select class="rx-select" id="rx-exam-plan">
						<option value="">Choose Exam Plan</option>
					</select>
				</div>

				<div class="rx-filter-arrow" id="rx-prog-arrow" style="display:none;">&#8594;</div>

				<div class="rx-fgroup" id="rx-prog-group" style="display:none;">
					<span class="rx-flabel">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
						Programme
						<span class="rx-active-badge prog" id="rx-prog-badge" style="display:none;">Filtered</span>
					</span>
					<select class="rx-select" id="rx-prog-select">
						<option value="">All Programmes</option>
					</select>
				</div>

				<div class="rx-filter-arrow" id="rx-course-arrow" style="display:none;">&#8594;</div>

				<div class="rx-fgroup wide" id="rx-course-group" style="display:none;">
					<span class="rx-flabel">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
						Course
						<span class="rx-active-badge course" id="rx-course-badge" style="display:none;">Filtered</span>
					</span>
					<select class="rx-select" id="rx-course-select">
						<option value="">All Courses</option>
					</select>
				</div>
			</div>

			<!-- Main content (shown after exam plan selected) -->
			<div id="rx-content" style="display:none;">

				<!-- Stat cards -->
				<div class="rx-stat-cards" id="rx-stat-cards" style="display:none;"></div>

				<!-- Re-Exam Settings card (shown when course selected) -->
				<div class="rx-settings-card" id="rx-settings-card" style="display:none;">
					<div class="rx-settings-title">
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
						Re-Exam Settings
						<span id="rx-saved-badge" class="rx-saved-badge" style="display:none;">
							<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
							Saved
						</span>
					</div>
					<div class="rx-settings-grid">
						<div class="rx-field-group">
							<span class="rx-field-label">Re-Exam Fee Amount</span>
							<input class="rx-input" type="number" id="rx-fee" placeholder="0.00" step="0.01" min="0">
						</div>
						<div class="rx-field-group">
							<span class="rx-field-label">Deadline From</span>
							<input class="rx-input" type="date" id="rx-deadline-from">
						</div>
						<div class="rx-field-group">
							<span class="rx-field-label">Deadline To</span>
							<input class="rx-input" type="date" id="rx-deadline-to">
						</div>
						<div style="display:flex;align-items:flex-end;padding-bottom:1px;">
							<button class="rx-save-btn" id="rx-save-settings">
								<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
								Save Settings
							</button>
						</div>
					</div>
				</div>

				<!-- Failed students section -->
				<div id="rx-students-section">
					<!-- Action bar -->
					<div class="rx-actbar">
						<div class="rx-srch">
							<svg class="rx-srch-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
							<input id="rx-search" type="text" placeholder="Search by student name or ID">
						</div>
					</div>

					<!-- Warning banner for fallback mode -->
					<div id="rx-warning-banner" style="display:none;background:#fef3c7;border:1.5px solid #fde68a;border-radius:10px;padding:10px 16px;margin-bottom:12px;display:none;align-items:center;gap:10px;font-size:12.5px;color:#92400e;">
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2.5" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
						<span><b>No failed grades defined in grading schema.</b> Showing all graded students. To filter only failed students, open the <b>Grading Schema</b> and check the <b>Failed</b> checkbox on failing grades (e.g. F).</span>
					</div>

					<!-- Count label -->
					<div style="display:flex;align-items:center;margin-bottom:10px;padding:0 2px;">
						<span id="rx-count-lbl" class="rx-count-lbl">Failed Students (0)</span>
					</div>

					<!-- DataTable wrapper -->
					<div class="rx-table-card">
						<div id="rx-dt-placeholder" class="rx-empty">
							<div class="rx-empty-icon">
								<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
							</div>
							<div class="rx-empty-txt">Select an Exam Plan &amp; Course</div>
							<div class="rx-empty-sub">Choose filters above to view failed students</div>
						</div>
						<div id="rx-dt-wrapper" style="display:none;"></div>
					</div>
				</div>

			</div>

		</div>
	`);

	// ── DOM refs ──────────────────────────────────────────────────────────────
	var $examPlan      = $body.find('#rx-exam-plan');
	var $progGroup     = $body.find('#rx-prog-group');
	var $progArrow     = $body.find('#rx-prog-arrow');
	var $progSelect    = $body.find('#rx-prog-select');
	var $progBadge     = $body.find('#rx-prog-badge');
	var $courseArrow   = $body.find('#rx-course-arrow');
	var $courseGroup   = $body.find('#rx-course-group');
	var $courseSelect  = $body.find('#rx-course-select');
	var $courseBadge   = $body.find('#rx-course-badge');
	var $content       = $body.find('#rx-content');
	var $statCards     = $body.find('#rx-stat-cards');
	var $settingsCard  = $body.find('#rx-settings-card');
	var $savedBadge    = $body.find('#rx-saved-badge');
	var $feeInput      = $body.find('#rx-fee');
	var $dlFrom        = $body.find('#rx-deadline-from');
	var $dlTo          = $body.find('#rx-deadline-to');
	var $saveBtn       = $body.find('#rx-save-settings');
	var $search         = $body.find('#rx-search');
	var $countLbl       = $body.find('#rx-count-lbl');
	var $warningBanner  = $body.find('#rx-warning-banner');
	var $dtPlaceholder  = $body.find('#rx-dt-placeholder');
	var $dtWrapper      = $body.find('#rx-dt-wrapper');
	var _dt             = null; // DataTable instance

	// ── Load Exam Plans ───────────────────────────────────────────────────────
	frappe.call({
		method: 'slcm.slcm.page.re_exam.re_exam.get_exam_plans',
		callback: function (r) {
			if (!r.message) return;
			r.message.forEach(function (ep) {
				$examPlan.append('<option value="' + ep.name + '">' +
					frappe.utils.escape_html(ep.exam_name || ep.name) +
					(ep.status === 'Active' ? ' [Active]' : '') + '</option>');
			});
		},
	});

	// ── Exam Plan change ──────────────────────────────────────────────────────
	$examPlan.on('change', function () {
		S.exam_plan   = $(this).val();
		S.programme   = '';
		S.course      = '';
		S.page        = 1;
		S.search      = '';
		$search.val('');
		$progSelect.val(''); $progBadge.hide();
		$courseSelect.val(''); $courseBadge.hide();
		$settingsCard.hide();
		clearSettings();
		if (S.exam_plan) {
			$content.show();
			loadProgrammes();
			loadCourses();
			loadStats();
			loadStudents();
		} else {
			$content.hide();
			$statCards.hide();
			$progGroup.hide(); $progArrow.hide();
			$courseGroup.hide(); $courseArrow.hide();
			showPlaceholder('Select an Exam Plan & Course', 'Choose filters above to view failed students');
			$countLbl.text('Failed Students (0)');
		}
	});

	// ── Programme change ──────────────────────────────────────────────────────
	$progSelect.on('change', function () {
		S.programme = $(this).val();
		S.course    = '';
		S.search    = '';
		$search.val('');
		$courseSelect.val(''); $courseBadge.hide();
		$progBadge.toggle(!!S.programme);
		$settingsCard.hide();
		clearSettings();
		loadCourses();
		loadStats();
		loadStudents();
	});

	// ── Course change ─────────────────────────────────────────────────────────
	$courseSelect.on('change', function () {
		S.course = $(this).val();
		S.search = '';
		$search.val('');
		$courseBadge.toggle(!!S.course);
		if (S.course) {
			$settingsCard.show();
			loadSettings();
		} else {
			$settingsCard.hide();
			clearSettings();
		}
		loadStats();
		loadStudents();
	});

	// ── Search ────────────────────────────────────────────────────────────────
	$search.on('input', function () {
		clearTimeout(S.search_timer);
		S.search_timer = setTimeout(function () {
			S.search = $search.val().trim();
			S.page = 1;
			loadStudents();
		}, 350);
	});

	// ── Save settings ─────────────────────────────────────────────────────────
	$saveBtn.on('click', function () {
		if (!S.exam_plan || !S.course) {
			frappe.show_alert({ message: 'Select Exam Plan and Course first.', indicator: 'orange' });
			return;
		}
		$saveBtn.prop('disabled', true).text('Saving…');
		frappe.call({
			method: 'slcm.slcm.page.re_exam.re_exam.save_re_exam_setting',
			args: {
				exam_plan:     S.exam_plan,
				course:        S.course,
				re_exam_fee:   $feeInput.val()  || null,
				deadline_from: $dlFrom.val()    || null,
				deadline_to:   $dlTo.val()      || null,
			},
			callback: function (r) {
				$saveBtn.prop('disabled', false).html(
					'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg> Save Settings'
				);
				if (r.message) {
					$savedBadge.show();
					setTimeout(function () { $savedBadge.hide(); }, 2500);
					frappe.show_alert({ message: 'Re-exam settings saved.', indicator: 'green' });
				}
			},
			error: function () {
				$saveBtn.prop('disabled', false).html(
					'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg> Save Settings'
				);
			},
		});
	});

	// ── Consolidated Report ───────────────────────────────────────────────────
	$body.find('#rx-nav-consolidated').on('click', function () {
		var d = new frappe.ui.Dialog({
			title: 'Download Consolidated Report',
			fields: [
				{ label: 'Exam Plan', fieldname: 'exam_plan', fieldtype: 'Link', options: 'Exam Plan', reqd: 1, default: S.exam_plan || '' },
				{ label: 'Report Type', fieldname: 'report_type', fieldtype: 'Select', options: 'Bulk\nCourse Based', reqd: 1, default: 'Bulk' },
				{ label: 'Course', fieldname: 'course', fieldtype: 'Link', options: 'Course', depends_on: 'eval:doc.report_type=="Course Based"' }
			],
			primary_action_label: 'Download CSV',
			primary_action: function (v) {
				var args = { exam_plan: v.exam_plan };
				if (v.report_type === 'Course Based' && v.course) args.course = v.course;
				var url = '/api/method/slcm.slcm.page.term_result.term_result.download_consolidated_report?' + $.param(args);
				window.open(url, '_blank');
				d.hide();
			},
		});
		d.show();
	});

	// ── Helper: load programmes ───────────────────────────────────────────────
	function loadProgrammes() {
		if (!S.exam_plan) return;
		frappe.call({
			method: 'slcm.slcm.page.re_exam.re_exam.get_programmes_for_exam_plan',
			args:   { exam_plan: S.exam_plan },
			callback: function (r) {
				var progs = r.message || [];
				$progSelect.empty().append('<option value="">All Programmes</option>');
				progs.forEach(function (p) {
					var label = (p.programme_name && p.programme_name !== p.programme)
						? frappe.utils.escape_html(p.programme_name)
						: frappe.utils.escape_html(p.programme);
					$progSelect.append('<option value="' + frappe.utils.escape_html(p.programme) + '">' + label + '</option>');
				});
				if (progs.length > 0) { $progGroup.show(); $progArrow.show(); }
				else { $progGroup.hide(); $progArrow.hide(); }
			},
		});
	}

	// ── Helper: load courses ──────────────────────────────────────────────────
	function loadCourses() {
		if (!S.exam_plan) return;
		frappe.call({
			method: 'slcm.slcm.page.re_exam.re_exam.get_courses_for_exam_plan',
			args:   { exam_plan: S.exam_plan, programme: S.programme || '' },
			callback: function (r) {
				var courses = r.message || [];
				$courseSelect.empty().append('<option value="">All Courses</option>');
				courses.forEach(function (c) {
					var label = (c.course_name && c.course_name !== c.course)
						? frappe.utils.escape_html(c.course_name) + ' (' + frappe.utils.escape_html(c.course) + ')'
						: frappe.utils.escape_html(c.course);
					$courseSelect.append('<option value="' + frappe.utils.escape_html(c.course) + '">' + label + '</option>');
				});
				if (courses.length > 0) { $courseGroup.show(); $courseArrow.show(); }
				else { $courseGroup.hide(); $courseArrow.hide(); }
			},
		});
	}

	// ── Helper: load stats ────────────────────────────────────────────────────
	function loadStats() {
		if (!S.exam_plan || !S.course) {
			$statCards.hide();
			return;
		}
		frappe.call({
			method: 'slcm.slcm.page.re_exam.re_exam.get_re_exam_stats',
			args:   { exam_plan: S.exam_plan, course: S.course },
			callback: function (r) {
				if (!r.message) return;
				var d = r.message;
				var cards = [
					{ label: 'Total Students', value: d.total  || 0, color: '#8b5cf6', bg: '#f5f3ff',
					  icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>' },
					{ label: 'Failed',         value: d.failed || 0, color: '#ef4444', bg: '#fff0f0',
					  icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>' },
					{ label: 'Passed',         value: d.passed || 0, color: '#10b981', bg: '#d1fae5',
					  icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/></svg>' },
				];
				var html = cards.map(function (c) {
					return '<div class="rx-stat-card" style="--sc-color:' + c.color + ';--sc-bg:' + c.bg + ';">' +
						'<div class="rx-sc-icon">' + c.icon + '</div>' +
						'<div><div class="rx-sc-val">' + c.value + '</div><div class="rx-sc-lbl">' + c.label + '</div></div></div>';
				}).join('');
				$statCards.html(html).show();
			},
		});
	}

	// ── Helper: load settings ─────────────────────────────────────────────────
	function loadSettings() {
		if (!S.exam_plan || !S.course) return;
		$savedBadge.hide();
		frappe.call({
			method: 'slcm.slcm.page.re_exam.re_exam.get_re_exam_setting',
			args:   { exam_plan: S.exam_plan, course: S.course },
			callback: function (r) {
				var d = r.message || {};
				$feeInput.val(d.re_exam_fee  || '');
				$dlFrom.val(d.deadline_from  || '');
				$dlTo.val(d.deadline_to      || '');
			},
		});
	}

	// ── Helper: clear settings fields ────────────────────────────────────────
	function clearSettings() {
		$feeInput.val('');
		$dlFrom.val('');
		$dlTo.val('');
		$savedBadge.hide();
	}

	// ── Helper: show placeholder (no DataTable) ───────────────────────────────
	function showPlaceholder(title, sub) {
		if (_dt) { _dt.destroy(); _dt = null; }
		$dtWrapper.hide();
		$dtPlaceholder
			.find('.rx-empty-txt').text(title).end()
			.find('.rx-empty-sub').text(sub).end()
			.show();
		$warningBanner.hide();
	}

	// ── Helper: load students ─────────────────────────────────────────────────
	function loadStudents() {
		if (!S.exam_plan) {
			showPlaceholder('Select an Exam Plan & Course', 'Choose filters above to view failed students');
			$countLbl.text('Failed Students (0)');
			return;
		}
		if (!S.course) {
			showPlaceholder('Select a Course', 'Choose a course to view failed students');
			$countLbl.text('Failed Students (0)');
			return;
		}
		$dtPlaceholder.show().find('.rx-empty-txt').text('Loading…').end().find('.rx-empty-sub').text('');
		$dtWrapper.hide();
		frappe.call({
			method: 'slcm.slcm.page.re_exam.re_exam.get_failed_students',
			args: {
				exam_plan:   S.exam_plan,
				course:      S.course,
				search:      S.search,
				page:        1,
				page_length: 500,
			},
			callback: function (r) {
				var data = r.message || { students: [], total: 0 };
				S.students            = data.students;
				S.total               = data.total;
				S.all_grades_fallback = !!data.all_grades_fallback;
				renderDataTable(data.students, data.total);
			},
		});
	}

	// ── Render via Frappe DataTable ───────────────────────────────────────────
	function renderDataTable(students, total) {
		var label = S.all_grades_fallback ? 'Graded Students' : 'Failed Students';
		$countLbl.text(label + ' (' + total + ')');

		// Warning banner
		if (S.all_grades_fallback) {
			$warningBanner.css('display', 'flex');
		} else {
			$warningBanner.hide();
		}

		if (!students || !students.length) {
			showPlaceholder('No Students Found', 'No graded students found for this course and exam plan.');
			return;
		}

		$dtPlaceholder.hide();
		$dtWrapper.show();

		// Build columns for DataTable
		var dtColumns = [
			{
				name: 'Student',
				id:   'student_cell',
				width: 300,
				editable: false,
				format: function (value) { return value || ''; },
			},
			{
				name: 'Registration ID',
				id:   'registration_id',
				width: 150,
				editable: false,
			},
			{
				name: 'Programme',
				id:   'programme',
				width: 160,
				editable: false,
			},
			{
				name: 'Batch',
				id:   'batch_year',
				width: 100,
				editable: false,
			},
			{
				name: 'Total Marks',
				id:   'total_marks',
				width: 120,
				editable: false,
				format: function (value) {
					if (value === null || value === undefined || value === '') return '—';
					return '<span style="font-weight:600;color:#0f172a;">' + parseFloat(value).toFixed(2) + '</span>';
				},
			},
			{
				name: 'Grade',
				id:   'grade',
				width: 100,
				editable: false,
				format: function (value) {
					if (!value) return '<span style="color:#cbd5e1;">—</span>';
					return '<span style="display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:26px;border-radius:7px;font-size:12px;font-weight:800;background:#fff0f0;color:#ef4444;border:1.5px solid #fecaca;padding:0 8px;">' + frappe.utils.escape_html(value) + '</span>';
				},
			},
		];

		// Build rows for DataTable (array of arrays matching column order)
		var dtData = students.map(function (s, i) {
			var initials = ((s.student_name || '').split(' ').map(function (w) { return w[0] || ''; }).join('').slice(0, 2)).toUpperCase() || '?';
			var avClass  = 'av-' + (i % 8);
			var avatarHtml = s.image
				? '<div class="rx-savatar" style="width:36px;height:36px;border-radius:9px;overflow:hidden;flex-shrink:0;"><img src="' + frappe.utils.escape_html(s.image) + '" style="width:100%;height:100%;object-fit:cover;" loading="lazy"></div>'
				: '<div class="rx-savatar ' + avClass + '" style="width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#fff;flex-shrink:0;">' + frappe.utils.escape_html(initials) + '</div>';

			var studentCell =
				'<div style="display:flex;align-items:center;gap:10px;padding:4px 0;">' +
					avatarHtml +
					'<div>' +
						'<div style="font-size:13px;font-weight:700;color:#0f172a;">' + frappe.utils.escape_html(s.student_name || '—') + '</div>' +
						(s.email ? '<div style="font-size:11px;color:#94a3b8;margin-top:1px;">' + frappe.utils.escape_html(s.email) + '</div>' : '') +
					'</div>' +
				'</div>';

			return [
				studentCell,
				frappe.utils.escape_html(s.registration_id || '—'),
				frappe.utils.escape_html(s.programme || '—'),
				frappe.utils.escape_html(s.batch_year ? String(s.batch_year) : '—'),
				s.total_marks,
				s.grade || '',
			];
		});

		if (_dt) {
			_dt.refresh(dtData, dtColumns);
		} else {
			_dt = new DataTable($dtWrapper[0], {
				columns:              dtColumns,
				data:                 dtData,
				layout:               'fluid',
				cellHeight:           58,
				serialNoColumn:       true,
				checkboxColumn:       false,
				inlineFilters:        true,
				noDataMessage:        'No students found',
				language:             frappe.boot.lang,
				translations:         frappe.utils.datatable.get_translations(),
				disableReorderColumn: true,
			});
		}
	}
};
