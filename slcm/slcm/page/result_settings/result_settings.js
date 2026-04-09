frappe.pages['result-settings'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Result Settings',
		single_column: true,
	});

	// ── CSS ───────────────────────────────────────────────────────────────────
	if (!document.getElementById('rs-style')) {
		var style = document.createElement('style');
		style.id  = 'rs-style';
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
		.er2-pnav-btn.active { background:#fff; color:#4f46e5; box-shadow:0 1px 4px rgba(0,0,0,.12); }

		/* Plan selector card */
		.rs-plan-card    { background:#fff; border-radius:12px; padding:14px 20px; margin-bottom:16px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap; }
		.rs-fgroup       { display:flex; flex-direction:column; min-width:240px; flex:1; max-width:360px; }
		.rs-flabel       { font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:5px;
		                   text-transform:uppercase; letter-spacing:.6px; }
		.rs-select       { height:36px; border:1.5px solid #e2e8f0; border-radius:8px;
		                   padding:0 12px; font-size:13px; background:#fff; color:#1e293b;
		                   outline:none; cursor:pointer; transition:border-color .2s; }
		.rs-select:focus { border-color:#f59e0b; box-shadow:0 0 0 3px rgba(245,158,11,.1); }

		/* Secondary sub-tab nav */
		.rs-subtab-bar   { display:flex; align-items:center; border-bottom:2px solid #e2e8f0;
		                   margin-bottom:20px; gap:0; overflow-x:auto; }
		.rs-subtab       { padding:10px 20px; font-size:13px; font-weight:600; color:#64748b;
		                   border-bottom:2px solid transparent; margin-bottom:-2px; cursor:pointer;
		                   white-space:nowrap; transition:all .18s; user-select:none; }
		.rs-subtab:hover { color:#1e293b; }
		.rs-subtab.active{ color:#e11d48; border-bottom-color:#e11d48; }

		/* Content area header (Cancel / Save) */
		.rs-content-hdr  { display:flex; align-items:center; justify-content:flex-end;
		                   gap:8px; margin-bottom:16px; }
		.rs-btn          { height:34px; padding:0 18px; border-radius:7px; border:1.5px solid #e2e8f0;
		                   background:#fff; cursor:pointer; font-size:13px; font-weight:600;
		                   color:#475569; transition:all .15s; }
		.rs-btn:hover    { background:#f8fafc; border-color:#cbd5e1; color:#1e293b; }
		.rs-btn.primary  { background:linear-gradient(135deg,#f59e0b,#fbbf24);
		                   border-color:transparent; color:#fff; }
		.rs-btn.primary:hover { opacity:.9; }
		.rs-btn:disabled { opacity:.5; cursor:default; }

		/* Section cards */
		.rs-section      { background:#fff; border-radius:12px; padding:24px 28px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); margin-bottom:16px; }
		.rs-sec-title    { font-size:14px; font-weight:800; color:#0f172a; margin-bottom:18px;
		                   padding-bottom:12px; border-bottom:1.5px solid #f1f5f9; }

		/* Component tags */
		.rs-tags-wrap    { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
		.rs-tag          { display:inline-flex; align-items:center; gap:6px; padding:5px 10px 5px 12px;
		                   border-radius:20px; font-size:12.5px; font-weight:700; color:#fff; }
		.rs-tag-x        { width:16px; height:16px; border-radius:50%; background:rgba(255,255,255,.25);
		                   display:inline-flex; align-items:center; justify-content:center;
		                   cursor:pointer; font-size:10px; line-height:1; transition:background .15s; }
		.rs-tag-x:hover  { background:rgba(255,255,255,.45); }

		/* Add component dropdown */
		.rs-add-wrap     { position:relative; display:inline-block; }
		.rs-add-btn      { display:inline-flex; align-items:center; gap:6px; padding:5px 14px;
		                   border-radius:20px; border:1.5px dashed #cbd5e1; background:#fff;
		                   cursor:pointer; font-size:12.5px; font-weight:600; color:#64748b;
		                   transition:all .15s; }
		.rs-add-btn:hover{ border-color:#f59e0b; color:#92400e; background:#fffbeb; }
		.rs-add-dd       { display:none; position:absolute; top:calc(100% + 6px); left:0; z-index:999;
		                   background:#fff; border:1.5px solid #e2e8f0; border-radius:10px;
		                   box-shadow:0 8px 24px rgba(0,0,0,.12); min-width:200px; padding:5px; }
		.rs-add-wrap.open .rs-add-dd { display:block; }
		.rs-add-item     { padding:8px 12px; font-size:12.5px; cursor:pointer; color:#475569;
		                   border-radius:7px; font-weight:500; transition:background .12s; }
		.rs-add-item:hover { background:#f1f5f9; color:#1e293b; }
		.rs-add-none     { padding:10px 12px; font-size:12px; color:#94a3b8; }

		/* Settings rows */
		.rs-setting-row  { display:flex; align-items:center; gap:16px; padding:14px 0;
		                   border-bottom:1.5px solid #f8fafc; }
		.rs-setting-row:last-child { border-bottom:none; padding-bottom:0; }
		.rs-setting-row:first-child { padding-top:0; }
		.rs-setting-lbl  { flex:1; font-size:13.5px; color:#1e293b; font-weight:500; }
		.rs-setting-ctrl { display:flex; align-items:center; gap:12px; flex-shrink:0; }

		/* Toggle switch */
		.rs-toggle       { position:relative; display:inline-block; width:44px; height:24px;
		                   cursor:pointer; flex-shrink:0; }
		.rs-toggle input { opacity:0; width:0; height:0; position:absolute; }
		.rs-toggle-sl    { position:absolute; inset:0; background:#cbd5e1; border-radius:24px;
		                   transition:background .2s; }
		.rs-toggle-sl:before { content:''; position:absolute; width:18px; height:18px;
		                       left:3px; bottom:3px; background:#fff; border-radius:50%;
		                       transition:transform .2s; box-shadow:0 1px 3px rgba(0,0,0,.2); }
		.rs-toggle input:checked + .rs-toggle-sl { background:#10b981; }
		.rs-toggle input:checked + .rs-toggle-sl:before { transform:translateX(20px); }

		/* Inline checkbox (beside Show SGPA) */
		.rs-inline-chk   { display:flex; align-items:center; gap:6px; font-size:12.5px;
		                   color:#475569; font-weight:500; cursor:pointer; user-select:none; }
		.rs-inline-chk input[type="checkbox"] { width:15px; height:15px; accent-color:#10b981;
		                                         cursor:pointer; flex-shrink:0; }

		/* Coming soon placeholder */
		.rs-coming-card  { background:#fff; border-radius:16px; padding:60px 40px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); display:flex;
		                   flex-direction:column; align-items:center; text-align:center; }
		.rs-coming-icon  { width:72px; height:72px; border-radius:18px; display:flex;
		                   align-items:center; justify-content:center; margin-bottom:16px; }
		.rs-coming-title { font-size:18px; font-weight:800; color:#0f172a; margin-bottom:8px; }
		.rs-coming-desc  { font-size:13px; color:#64748b; max-width:380px; line-height:1.6; }
		.rs-coming-badge { display:inline-flex; align-items:center; gap:6px; margin-top:18px;
		                   background:#f1f5f9; border:1.5px solid #e2e8f0; border-radius:20px;
		                   padding:6px 14px; font-size:12px; font-weight:700; color:#64748b; }

		/* Loading / empty */
		.rs-loading      { padding:48px; text-align:center; color:#94a3b8; font-size:13px; }
		@keyframes rs-spin { to { transform:rotate(360deg); } }
		.rs-spin         { animation:rs-spin 1s linear infinite; display:inline-block; }
		`;
		document.head.appendChild(style);
	}

	// ── State ─────────────────────────────────────────────────────────────────
	var S = {
		exam_plan:        null,
		all_components:   [],   // [{name, component_name, component_type}]
		components:       [],   // currently selected [{component, component_name, component_type}]
		settings: {
			show_total_marks:       0,
			show_sgpa:              0,
			hide_sgpa_for_failed:   0,
			show_egradesheet:       0,
			no_publish_unpaid:      0,
			no_publish_no_feedback: 0,
		},
		active_subtab: 'publish',
		saving:        false,
	};

	// ── Render shell ──────────────────────────────────────────────────────────
	var $body = $(page.main);
	$body.html(`
		<div class="er2-wrap" style="padding:20px 24px;">

			<!-- Page header -->
			<div class="er2-page-header">
				<div class="er2-page-icon" style="background:linear-gradient(135deg,#f59e0b,#fbbf24);">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2">
						<circle cx="12" cy="12" r="3"/>
						<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
					</svg>
				</div>
				<div>
					<div class="er2-page-title">Result Settings</div>
					<div class="er2-page-sub">Configure grading schemas, access rules, and result display preferences</div>
				</div>
			</div>

			<!-- Main page nav -->
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
				<button class="er2-pnav-btn active">
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
					Settings
				</button>
			</div>

			<!-- Exam Plan selector -->
			<div class="rs-plan-card">
				<div class="rs-fgroup">
					<span class="rs-flabel">
						<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>
						Exam Plan
					</span>
					<select class="rs-select" id="rs-exam-plan">
						<option value="">Choose Exam Plan</option>
					</select>
				</div>
			</div>

			<!-- Dynamic content (shown after plan is selected) -->
			<div id="rs-content" style="display:none;">

				<!-- Sub-tab navigation -->
				<div class="rs-subtab-bar">
					<div class="rs-subtab" data-tab="access_results">Access Results</div>
					<div class="rs-subtab" data-tab="gradebook_access">Gradebook Access</div>
					<div class="rs-subtab" data-tab="term_sheet">Term Sheet</div>
					<div class="rs-subtab active" data-tab="publish">Publish</div>
					<div class="rs-subtab" data-tab="result_settings">Result Settings</div>
				</div>

				<!-- Tab panels -->
				<div id="rs-tab-panel"></div>

			</div>
		</div>
	`);

	// ── DOM refs ──────────────────────────────────────────────────────────────
	var $examPlan  = $body.find('#rs-exam-plan');
	var $content   = $body.find('#rs-content');
	var $tabPanel  = $body.find('#rs-tab-panel');

	// ── Load Exam Plans ───────────────────────────────────────────────────────
	frappe.call({
		method: 'slcm.slcm.page.result_settings.result_settings.get_exam_plans',
		callback: function (r) {
			if (!r.message) return;
			r.message.forEach(function (ep) {
				$examPlan.append(
					'<option value="' + ep.name + '">' +
					frappe.utils.escape_html(ep.exam_name || ep.name) +
					(ep.status === 'Active' ? ' [Active]' : '') + '</option>'
				);
			});
		},
	});

	// ── Load all exam components once ─────────────────────────────────────────
	frappe.call({
		method: 'slcm.slcm.page.result_settings.result_settings.get_exam_components',
		callback: function (r) {
			S.all_components = r.message || [];
		},
	});

	// ── Exam Plan change ──────────────────────────────────────────────────────
	$examPlan.on('change', function () {
		S.exam_plan = $(this).val();
		if (!S.exam_plan) {
			$content.hide();
			return;
		}
		$content.show();
		loadPublishSetting();
	});

	// ── Sub-tab click ─────────────────────────────────────────────────────────
	$body.on('click', '.rs-subtab', function () {
		var tab = $(this).data('tab');
		if (tab === S.active_subtab) return;
		S.active_subtab = tab;
		$body.find('.rs-subtab').removeClass('active');
		$(this).addClass('active');
		renderTabPanel();
	});

	// ── Load publish setting from server ──────────────────────────────────────
	function loadPublishSetting() {
		$tabPanel.html('<div class="rs-loading"><svg class="rs-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.22-8.56"/></svg> Loading…</div>');
		frappe.call({
			method: 'slcm.slcm.page.result_settings.result_settings.get_publish_setting',
			args:   { exam_plan: S.exam_plan },
			callback: function (r) {
				var d = r.message || {};
				// Merge fetched settings into state
				S.settings.show_total_marks       = d.show_total_marks       || 0;
				S.settings.show_sgpa              = d.show_sgpa              || 0;
				S.settings.hide_sgpa_for_failed   = d.hide_sgpa_for_failed   || 0;
				S.settings.show_egradesheet       = d.show_egradesheet       || 0;
				S.settings.no_publish_unpaid      = d.no_publish_unpaid      || 0;
				S.settings.no_publish_no_feedback = d.no_publish_no_feedback || 0;

				// Build component list enriched with component_type from all_components
				S.components = (d.components || []).map(function (c) {
					var full = S.all_components.find(function (a) { return a.name === c.component; });
					return {
						component:      c.component,
						component_name: c.component_name || c.component,
						component_type: full ? full.component_type : 'Custom',
					};
				});

				renderTabPanel();
			},
		});
	}

	// ── Render current tab panel ──────────────────────────────────────────────
	function renderTabPanel() {
		if (S.active_subtab === 'publish') {
			renderPublishTab();
		} else {
			renderComingSoon(S.active_subtab);
		}
	}

	// ── Render Publish tab ────────────────────────────────────────────────────
	function renderPublishTab() {
		$tabPanel.html(`
			<div>
				<!-- Cancel / Save -->
				<div class="rs-content-hdr">
					<button class="rs-btn" id="rs-cancel-btn">Cancel</button>
					<button class="rs-btn primary" id="rs-save-btn">Save</button>
				</div>

				<!-- Component Settings -->
				<div class="rs-section">
					<div class="rs-sec-title">Component Settings</div>
					<div class="rs-setting-row" style="border-bottom:none;padding:0;">
						<div class="rs-setting-lbl">Publish Marks For Components</div>
						<div class="rs-setting-ctrl" style="flex:2;justify-content:flex-start;flex-wrap:wrap;gap:8px;" id="rs-components-area">
						</div>
					</div>
				</div>

				<!-- Exam Settings -->
				<div class="rs-section">
					<div class="rs-sec-title">Exam Settings</div>

					<div class="rs-setting-row">
						<div class="rs-setting-lbl">Show Total Marks</div>
						<div class="rs-setting-ctrl">
							<label class="rs-toggle">
								<input type="checkbox" id="rs-show-total" ${S.settings.show_total_marks ? 'checked' : ''}>
								<span class="rs-toggle-sl"></span>
							</label>
						</div>
					</div>

					<div class="rs-setting-row">
						<div class="rs-setting-lbl">Show SGPA</div>
						<div class="rs-setting-ctrl">
							<label class="rs-toggle">
								<input type="checkbox" id="rs-show-sgpa" ${S.settings.show_sgpa ? 'checked' : ''}>
								<span class="rs-toggle-sl"></span>
							</label>
							<label class="rs-inline-chk" id="rs-sgpa-hide-wrap" style="${S.settings.show_sgpa ? '' : 'display:none;'}">
								<input type="checkbox" id="rs-hide-sgpa-failed" ${S.settings.hide_sgpa_for_failed ? 'checked' : ''}>
								Hide SGPA for Student(s) who have failed in one or more courses in this term
							</label>
						</div>
					</div>

					<div class="rs-setting-row">
						<div class="rs-setting-lbl">Show E-GradeSheet Download Option</div>
						<div class="rs-setting-ctrl">
							<label class="rs-toggle">
								<input type="checkbox" id="rs-show-egradesheet" ${S.settings.show_egradesheet ? 'checked' : ''}>
								<span class="rs-toggle-sl"></span>
							</label>
						</div>
					</div>

					<div class="rs-setting-row">
						<div class="rs-setting-lbl">Do not Publish Result for Student who have not paid Fees</div>
						<div class="rs-setting-ctrl">
							<label class="rs-toggle">
								<input type="checkbox" id="rs-no-publish-unpaid" ${S.settings.no_publish_unpaid ? 'checked' : ''}>
								<span class="rs-toggle-sl"></span>
							</label>
						</div>
					</div>

					<div class="rs-setting-row">
						<div class="rs-setting-lbl">Do not Publish Result for Student(s) who have not given faculty feedback</div>
						<div class="rs-setting-ctrl">
							<label class="rs-toggle">
								<input type="checkbox" id="rs-no-publish-feedback" ${S.settings.no_publish_no_feedback ? 'checked' : ''}>
								<span class="rs-toggle-sl"></span>
							</label>
						</div>
					</div>

				</div>
			</div>
		`);

		renderComponentTags();

		// Show SGPA toggle → show/hide inline checkbox
		$tabPanel.find('#rs-show-sgpa').on('change', function () {
			if ($(this).is(':checked')) {
				$tabPanel.find('#rs-sgpa-hide-wrap').show();
			} else {
				$tabPanel.find('#rs-sgpa-hide-wrap').hide();
				$tabPanel.find('#rs-hide-sgpa-failed').prop('checked', false);
			}
		});

		// Cancel
		$tabPanel.find('#rs-cancel-btn').on('click', function () {
			loadPublishSetting();
		});

		// Save
		$tabPanel.find('#rs-save-btn').on('click', function () {
			if (S.saving) return;
			savePublishSetting();
		});
	}

	// ── Render component tags + Add button ────────────────────────────────────
	function renderComponentTags() {
		var $area = $tabPanel.find('#rs-components-area');
		if (!$area.length) return;

		var html = '';
		S.components.forEach(function (c, idx) {
			var col = componentColor(c.component_type);
			html += '<span class="rs-tag" style="background:' + col + ';" data-idx="' + idx + '">' +
				frappe.utils.escape_html(c.component_name) +
				'<span class="rs-tag-x" title="Remove">&#10005;</span>' +
			'</span>';
		});

		// "Add New Component" dropdown
		var available = availableComponents();
		var ddItems = '';
		if (available.length) {
			available.forEach(function (c) {
				ddItems += '<div class="rs-add-item" data-comp="' + frappe.utils.escape_html(c.name) + '">' +
					frappe.utils.escape_html(c.component_name) + '</div>';
			});
		} else {
			ddItems = '<div class="rs-add-none">All components added</div>';
		}

		html += '<div class="rs-add-wrap" id="rs-add-wrap">' +
			'<button class="rs-add-btn" id="rs-add-comp-btn">' +
				'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>' +
				'Add New Component' +
				'<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>' +
			'</button>' +
			'<div class="rs-add-dd">' + ddItems + '</div>' +
		'</div>';

		$area.html(html);

		// Remove tag
		$area.find('.rs-tag-x').on('click', function () {
			var idx = $(this).closest('.rs-tag').data('idx');
			S.components.splice(idx, 1);
			renderComponentTags();
		});

		// Toggle add dropdown
		$area.find('#rs-add-comp-btn').on('click', function (e) {
			e.stopPropagation();
			var $wrap = $area.find('#rs-add-wrap');
			$wrap.toggleClass('open');
		});

		// Add component
		$area.find('.rs-add-item').on('click', function (e) {
			e.stopPropagation();
			var compName = $(this).data('comp');
			var full = S.all_components.find(function (a) { return a.name === compName; });
			if (full) {
				S.components.push({
					component:      full.name,
					component_name: full.component_name,
					component_type: full.component_type,
				});
				renderComponentTags();
			}
		});

		// Close dropdown on outside click
		$(document).off('click.rs_add').on('click.rs_add', function () {
			$area.find('#rs-add-wrap').removeClass('open');
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────
	function availableComponents() {
		var used = S.components.map(function (c) { return c.component; });
		return S.all_components.filter(function (a) { return used.indexOf(a.name) === -1; });
	}

	function componentColor(type) {
		if (type === 'Re Exam') return '#ef4444';
		if (type === 'Makeup')  return '#f97316';
		return '#059669';  // Custom / any other
	}

	// ── Save publish setting ──────────────────────────────────────────────────
	function savePublishSetting() {
		if (!S.exam_plan) return;

		var $saveBtn = $tabPanel.find('#rs-save-btn');
		S.saving = true;
		$saveBtn.prop('disabled', true).text('Saving…');

		var settings = {
			show_total_marks:       $tabPanel.find('#rs-show-total').is(':checked')          ? 1 : 0,
			show_sgpa:              $tabPanel.find('#rs-show-sgpa').is(':checked')            ? 1 : 0,
			hide_sgpa_for_failed:   $tabPanel.find('#rs-hide-sgpa-failed').is(':checked')    ? 1 : 0,
			show_egradesheet:       $tabPanel.find('#rs-show-egradesheet').is(':checked')    ? 1 : 0,
			no_publish_unpaid:      $tabPanel.find('#rs-no-publish-unpaid').is(':checked')   ? 1 : 0,
			no_publish_no_feedback: $tabPanel.find('#rs-no-publish-feedback').is(':checked') ? 1 : 0,
		};

		frappe.call({
			method: 'slcm.slcm.page.result_settings.result_settings.save_publish_setting',
			args: {
				exam_plan:              S.exam_plan,
				components:             JSON.stringify(S.components.map(function (c) {
					return { component: c.component };
				})),
				show_total_marks:       settings.show_total_marks,
				show_sgpa:              settings.show_sgpa,
				hide_sgpa_for_failed:   settings.hide_sgpa_for_failed,
				show_egradesheet:       settings.show_egradesheet,
				no_publish_unpaid:      settings.no_publish_unpaid,
				no_publish_no_feedback: settings.no_publish_no_feedback,
			},
			callback: function (r) {
				S.saving = false;
				$saveBtn.prop('disabled', false).text('Save');
				if (r.message && r.message.success) {
					// Update local state from UI values
					Object.assign(S.settings, settings);
					frappe.show_alert({ message: 'Publish settings saved', indicator: 'green' });
				} else {
					frappe.show_alert({ message: 'Failed to save settings', indicator: 'red' });
				}
			},
			error: function () {
				S.saving = false;
				$saveBtn.prop('disabled', false).text('Save');
				frappe.show_alert({ message: 'Error saving settings', indicator: 'red' });
			},
		});
	}

	// ── Render coming-soon placeholder for other sub-tabs ────────────────────
	var SUBTAB_LABELS = {
		access_results:  'Access Results',
		gradebook_access: 'Gradebook Access',
		term_sheet:      'Term Sheet',
		result_settings: 'Result Settings',
	};

	function renderComingSoon(tab) {
		var label = SUBTAB_LABELS[tab] || tab;
		$tabPanel.html(`
			<div class="rs-coming-card">
				<div class="rs-coming-icon" style="background:linear-gradient(135deg,#fffbeb,#fef3c7);">
					<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="1.8">
						<circle cx="12" cy="12" r="3"/>
						<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
					</svg>
				</div>
				<div class="rs-coming-title">${frappe.utils.escape_html(label)}</div>
				<div class="rs-coming-desc">This settings section is under development and will be available soon.</div>
				<div class="rs-coming-badge">
					<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
					Coming Soon
				</div>
			</div>
		`);
	}
};
