frappe.pages['promotion-management'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Promotion Management',
		single_column: true,
	});

	// ── CSS ───────────────────────────────────────────────────────────────────
	if (!document.getElementById('pm-style')) {
		var style = document.createElement('style');
		style.id = 'pm-style';
		style.textContent = `
		.pm-wrap         { font-family:var(--font-stack,'Inter',sans-serif); padding:0; background:#f1f5f9; min-height:100vh; }

		/* Header */
		.pm-header       { background:#fff; border-radius:12px; padding:18px 24px; margin-bottom:14px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); display:flex; align-items:center; gap:14px; }
		.pm-header-icon  { width:44px; height:44px; border-radius:11px; flex-shrink:0;
		                   background:linear-gradient(135deg,#6366f1,#8b5cf6);
		                   display:flex; align-items:center; justify-content:center; color:#fff; font-size:20px; }
		.pm-header-title { font-size:16px; font-weight:800; color:#0f172a; }
		.pm-header-sub   { font-size:12px; color:#94a3b8; margin-top:2px; }

		/* Filter card */
		.pm-filter-card  { background:#fff; border-radius:12px; padding:16px 20px; margin-bottom:14px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); }
		.pm-filter-title { font-size:11px; color:#64748b; font-weight:700; text-transform:uppercase;
		                   letter-spacing:.7px; margin-bottom:12px; display:flex; align-items:center; gap:6px; }
		.pm-filter-row   { display:flex; gap:14px; flex-wrap:wrap; align-items:flex-end; }
		.pm-fg           { display:flex; flex-direction:column; min-width:190px; flex:1; max-width:280px; }
		.pm-fg.wide      { max-width:340px; }
		.pm-fl           { font-size:11px; color:#94a3b8; font-weight:700; margin-bottom:5px;
		                   text-transform:uppercase; letter-spacing:.5px; }
		.pm-sel          { height:38px; border:1.5px solid #e2e8f0; border-radius:8px;
		                   padding:0 12px; font-size:13px; background:#fff; color:#1e293b;
		                   outline:none; cursor:pointer; transition:border-color .2s; }
		.pm-sel:focus    { border-color:#6366f1; box-shadow:0 0 0 3px rgba(99,102,241,.1); }
		.pm-inp          { height:38px; border:1.5px solid #e2e8f0; border-radius:8px;
		                   padding:0 12px; font-size:13px; background:#fff; color:#1e293b;
		                   outline:none; width:100%; box-sizing:border-box; transition:border-color .2s; }
		.pm-inp:focus    { border-color:#6366f1; box-shadow:0 0 0 3px rgba(99,102,241,.1); }

		/* Buttons */
		.pm-btn          { height:38px; padding:0 16px; border-radius:8px; border:1.5px solid #e2e8f0;
		                   background:#fff; cursor:pointer; font-size:13px; font-weight:600;
		                   color:#475569; display:inline-flex; align-items:center; gap:6px;
		                   white-space:nowrap; transition:all .15s; }
		.pm-btn:hover    { background:#f8fafc; border-color:#cbd5e1; }
		.pm-btn:disabled { opacity:.45; cursor:not-allowed; pointer-events:none; }
		.pm-btn.indigo   { background:linear-gradient(135deg,#6366f1,#818cf8); border-color:transparent; color:#fff; }
		.pm-btn.indigo:hover { opacity:.88; }
		.pm-btn.emerald  { background:linear-gradient(135deg,#10b981,#34d399); border-color:transparent; color:#fff; }
		.pm-btn.emerald:hover { opacity:.88; }
		.pm-btn.rose     { background:linear-gradient(135deg,#f43f5e,#fb7185); border-color:transparent; color:#fff; }
		.pm-btn.rose:hover { opacity:.88; }
		.pm-btn.amber    { background:linear-gradient(135deg,#f59e0b,#fbbf24); border-color:transparent; color:#fff; }
		.pm-btn.amber:hover { opacity:.88; }
		.pm-btn.slate    { background:linear-gradient(135deg,#475569,#64748b); border-color:transparent; color:#fff; }
		.pm-btn.slate:hover { opacity:.88; }
		.pm-btn.sm       { height:30px; padding:0 10px; font-size:11.5px; border-radius:6px; }

		/* Policy info strip */
		.pm-policy-strip { background:#eef2ff; border:1.5px solid #c7d2fe; border-radius:10px;
		                   padding:10px 16px; margin-bottom:14px; display:flex; gap:10px;
		                   flex-wrap:wrap; align-items:center; font-size:12px; color:#3730a3; }
		.pm-crit         { display:inline-flex; align-items:center; gap:4px; padding:3px 9px;
		                   border-radius:6px; font-size:11.5px; font-weight:700; }
		.pm-crit.on      { background:#dcfce7; color:#166534; }
		.pm-crit.off     { background:#f1f5f9; color:#94a3b8; }
		.pm-crit-label   { font-weight:700; color:#6366f1; margin-right:4px; }

		/* Stat cards */
		.pm-stats        { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
		.pm-sc           { background:#fff; border-radius:12px; padding:14px 18px; flex:1;
		                   min-width:140px; box-shadow:0 1px 3px rgba(0,0,0,.06);
		                   border-top:3px solid var(--c,#6366f1);
		                   display:flex; align-items:center; gap:12px; }
		.pm-sc-ico       { width:36px; height:36px; border-radius:9px; flex-shrink:0;
		                   display:flex; align-items:center; justify-content:center;
		                   background:var(--cb,#eef2ff); color:var(--c,#6366f1); font-size:15px; }
		.pm-sc-val       { font-size:24px; font-weight:800; color:var(--c,#6366f1); line-height:1; }
		.pm-sc-lbl       { font-size:10px; color:#94a3b8; font-weight:700; text-transform:uppercase;
		                   letter-spacing:.6px; margin-top:3px; }

		/* Action row */
		.pm-actrow       { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:12px; }
		.pm-srch         { flex:1; min-width:180px; max-width:320px; position:relative; }
		.pm-srch input   { width:100%; height:36px; border:1.5px solid #e2e8f0; border-radius:8px;
		                   padding:0 12px 0 34px; font-size:13px; outline:none; color:#1e293b;
		                   background:#fff; transition:border-color .2s; box-sizing:border-box; }
		.pm-srch input:focus { border-color:#6366f1; box-shadow:0 0 0 3px rgba(99,102,241,.1); }
		.pm-srch-ico     { position:absolute; left:9px; top:9px; color:#94a3b8; font-size:14px; }

		/* Tabs */
		.pm-tabs         { display:flex; gap:3px; background:#e2e8f0; border-radius:10px; padding:3px;
		                   width:fit-content; margin-bottom:12px; }
		.pm-tab          { padding:7px 15px; border-radius:7px; font-size:13px; font-weight:600;
		                   color:#64748b; cursor:pointer; transition:all .18s; user-select:none;
		                   display:inline-flex; align-items:center; gap:5px; }
		.pm-tab:hover    { color:#4f46e5; background:rgba(79,70,229,.07); }
		.pm-tab.active   { background:#fff; color:#4f46e5; box-shadow:0 1px 4px rgba(0,0,0,.1); }
		.pm-tbadge       { padding:1px 7px; border-radius:10px; font-size:10.5px; font-weight:700; }
		.tball    { background:#eef2ff; color:#6366f1; }
		.tbpro    { background:#dcfce7; color:#16a34a; }
		.tbnot    { background:#fee2e2; color:#dc2626; }
		.tbcond   { background:#fef3c7; color:#d97706; }

		/* Table card */
		.pm-card         { background:#fff; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,.06);
		                   overflow:hidden; margin-bottom:16px; }
		.pm-table-wrap   { overflow-x:auto; }
		table.pm-tbl     { width:100%; border-collapse:collapse; font-size:13px; }
		table.pm-tbl th  { background:#f8fafc; color:#64748b; font-size:10px; font-weight:700;
		                   text-transform:uppercase; letter-spacing:.5px; padding:10px 12px;
		                   border-bottom:2px solid #e2e8f0; white-space:nowrap; text-align:left; }
		table.pm-tbl td  { padding:9px 12px; border-bottom:1px solid #f1f5f9; color:#334155;
		                   vertical-align:middle; }
		table.pm-tbl tr:last-child td { border-bottom:none; }
		table.pm-tbl tr:hover td { background:#fafbff; }

		/* Status badges */
		.pm-bdg          { display:inline-block; padding:2px 9px; border-radius:6px;
		                   font-size:11px; font-weight:700; letter-spacing:.2px; }
		.bdg-pro         { background:#dcfce7; color:#15803d; }
		.bdg-not         { background:#fee2e2; color:#b91c1c; }
		.bdg-cond        { background:#fef3c7; color:#92400e; }
		.bdg-ovp         { background:#a7f3d0; color:#065f46; }
		.bdg-ovn         { background:#fecaca; color:#7f1d1d; }
		.chk-pass        { color:#16a34a; font-weight:700; font-size:12px; }
		.chk-fail        { color:#dc2626; font-weight:700; font-size:12px; }
		.chk-nc          { color:#cbd5e1; font-size:12px; }

		/* Notice */
		.pm-notice       { border-radius:9px; padding:10px 16px; margin-bottom:12px;
		                   font-size:12.5px; font-weight:500; display:flex; align-items:center; gap:8px; }
		.pm-notice.info  { background:#eff6ff; border:1.5px solid #bfdbfe; color:#1e40af; }
		.pm-notice.warn  { background:#fffbeb; border:1.5px solid #fde68a; color:#92400e; }
		.pm-notice.ok    { background:#f0fdf4; border:1.5px solid #bbf7d0; color:#166534; }

		/* Empty */
		.pm-empty        { text-align:center; padding:50px 20px; color:#94a3b8; }
		.pm-empty-ico    { font-size:42px; margin-bottom:10px; }

		/* Download bar */
		.pm-dl-bar       { background:#fff; border-radius:12px; padding:14px 20px; margin-bottom:14px;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); display:flex; gap:10px;
		                   flex-wrap:wrap; align-items:center; }
		.pm-dl-label     { font-size:12px; font-weight:700; color:#64748b; flex-shrink:0; }
		.pm-dl-divider   { width:1px; height:28px; background:#e2e8f0; flex-shrink:0; }
		/* Official download dialog */
		.pm-odl-row      { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:12px; }
		.pm-odl-fg       { display:flex; flex-direction:column; flex:1; min-width:160px; }
		.pm-odl-fl       { font-size:11px; color:#64748b; font-weight:700; margin-bottom:4px;
		                   text-transform:uppercase; letter-spacing:.5px; }
		.pm-odl-sel,.pm-odl-inp { height:36px; border:1.5px solid #e2e8f0; border-radius:7px;
		                          padding:0 10px; font-size:13px; background:#fff; color:#1e293b;
		                          outline:none; width:100%; box-sizing:border-box; }
		.pm-odl-sel:focus,.pm-odl-inp:focus { border-color:#6366f1; }
		`;
		document.head.appendChild(style);
	}

	// ── State ─────────────────────────────────────────────────────────────────
	var S = {
		program: '', academicYear: '', fromYear: '', toYear: '',
		policyName: null,
		students: [], counts: {total:0, promoted:0, not_promoted:0, conditional:0},
		confirmed: false, activeTab: 'all', search: '',
	};

	// ── Mount ─────────────────────────────────────────────────────────────────
	var $root = $('<div class="pm-wrap"></div>');
	$(page.main).html('').append($root);

	$root.html(`
		<div class="pm-header">
			<div class="pm-header-icon">&#127891;</div>
			<div>
				<div class="pm-header-title">Promotion Management</div>
				<div class="pm-header-sub">Fetch students by filters, evaluate promotion criteria, confirm and download lists</div>
			</div>
		</div>

		<!-- Filters -->
		<div class="pm-filter-card">
			<div class="pm-filter-title">&#128269; Select Filters</div>
			<div class="pm-filter-row">
				<div class="pm-fg">
					<div class="pm-fl">Program</div>
					<select class="pm-sel" id="pm-prog"><option value="">-- Program --</option></select>
				</div>
				<div class="pm-fg">
					<div class="pm-fl">Academic Year</div>
					<select class="pm-sel" id="pm-ay"><option value="">-- Academic Year --</option></select>
				</div>
				<div class="pm-fg" style="max-width:140px;">
					<div class="pm-fl">Current Year</div>
					<input type="number" class="pm-inp" id="pm-fy" min="1" max="10" placeholder="e.g. 1">
				</div>
				<div class="pm-fg" style="max-width:140px;">
					<div class="pm-fl">Target Year</div>
					<input type="number" class="pm-inp" id="pm-ty" min="1" max="10" placeholder="e.g. 2">
				</div>
				<div class="pm-fg wide">
					<div class="pm-fl">Policy <span style="color:#cbd5e1;">(optional)</span></div>
					<select class="pm-sel" id="pm-policy"><option value="">-- No policy / All Promoted --</option></select>
				</div>
				<div style="padding-bottom:1px;">
					<button class="pm-btn indigo" id="pm-fetch-btn">&#8618; Fetch Students</button>
				</div>
			</div>
		</div>

		<!-- Policy criteria strip -->
		<div id="pm-policy-strip" style="display:none;" class="pm-policy-strip"></div>

		<!-- Notice -->
		<div id="pm-notice" style="display:none;"></div>

		<!-- Stats -->
		<div class="pm-stats" id="pm-stats" style="display:none;">
			<div class="pm-sc" style="--c:#6366f1;--cb:#eef2ff;">
				<div class="pm-sc-ico">&#128100;</div>
				<div><div class="pm-sc-val" id="sc-total">0</div><div class="pm-sc-lbl">Total Students</div></div>
			</div>
			<div class="pm-sc" style="--c:#10b981;--cb:#d1fae5;">
				<div class="pm-sc-ico">&#10003;</div>
				<div><div class="pm-sc-val" id="sc-pro">0</div><div class="pm-sc-lbl">Promoted</div></div>
			</div>
			<div class="pm-sc" style="--c:#ef4444;--cb:#fee2e2;">
				<div class="pm-sc-ico">&#10007;</div>
				<div><div class="pm-sc-val" id="sc-not">0</div><div class="pm-sc-lbl">Not Promoted</div></div>
			</div>
			<div class="pm-sc" style="--c:#f59e0b;--cb:#fef3c7;">
				<div class="pm-sc-ico">&#9201;</div>
				<div><div class="pm-sc-val" id="sc-cond">0</div><div class="pm-sc-lbl">Conditional</div></div>
			</div>
		</div>

		<!-- Action row -->
		<div class="pm-actrow" id="pm-actrow" style="display:none;">
			<div class="pm-srch">
				<span class="pm-srch-ico">&#128269;</span>
				<input type="text" id="pm-search" placeholder="Search by name or ID...">
			</div>
			<button class="pm-btn emerald" id="pm-confirm-btn" disabled>
				&#10003; Confirm &amp; Save Promotion
			</button>
		</div>

		<!-- Download bar -->
		<div class="pm-dl-bar" id="pm-dl-bar" style="display:none;">
			<span class="pm-dl-label">&#8659; Quick Download:</span>
			<button class="pm-btn emerald sm" onclick="pmDl('promoted')">&#9989; Promoted List</button>
			<button class="pm-btn rose sm"   onclick="pmDl('not_promoted')">&#10060; Not Promoted List</button>
			<button class="pm-btn amber sm"  onclick="pmDl('conditional')">&#9201; Conditional List</button>
			<button class="pm-btn slate sm"  onclick="pmDl('all')">&#128196; All Students</button>
			<div class="pm-dl-divider"></div>
			<button class="pm-btn indigo sm" onclick="pmOfficialDl()">&#128203; Official Promotion Report</button>
		</div>
		<!-- Standalone official download card (visible always for course-wise download) -->
		<div class="pm-dl-bar" id="pm-official-dl-bar">
			<span class="pm-dl-label">&#128196; Official Report:</span>
			<button class="pm-btn indigo sm" onclick="pmOfficialDl()">&#128203; Download Course-wise Promotion List</button>
		</div>

		<!-- Tabs -->
		<div class="pm-tabs" id="pm-tabs" style="display:none;">
			<div class="pm-tab active" data-tab="all">All <span class="pm-tbadge tball" id="tb-all">0</span></div>
			<div class="pm-tab" data-tab="promoted">Promoted <span class="pm-tbadge tbpro" id="tb-pro">0</span></div>
			<div class="pm-tab" data-tab="not_promoted">Not Promoted <span class="pm-tbadge tbnot" id="tb-not">0</span></div>
			<div class="pm-tab" data-tab="conditional">Conditional <span class="pm-tbadge tbcond" id="tb-cond">0</span></div>
		</div>

		<!-- Table -->
		<div class="pm-card" id="pm-table-card" style="display:none;">
			<div class="pm-table-wrap">
				<table class="pm-tbl">
					<thead>
						<tr>
							<th>#</th>
							<th>Student ID</th>
							<th>Student Name</th>
							<th>Batch</th>
							<th>CGPA</th>
							<th>Backlogs</th>
							<th>Att %</th>
							<th>Shortage Courses</th>
							<th>CF FA+Shortage</th>
							<th>CGPA ✓</th>
							<th>Backlog ✓</th>
							<th>Att ✓</th>
							<th>Shortage ✓</th>
							<th>CF ✓</th>
							<th>Status</th>
							<th>Action</th>
						</tr>
					</thead>
					<tbody id="pm-tbody"></tbody>
				</table>
			</div>
		</div>
	`);

	// ── Load dropdowns ────────────────────────────────────────────────────────
	var _dropdownsLoaded = {programs: false, years: false};
	function _checkAutoAction() {
		if (!_dropdownsLoaded.programs || !_dropdownsLoaded.years) return;
		var urlParams = new URLSearchParams(window.location.search);
		if (urlParams.get('action') === 'download_report') {
			// Small delay so the dialog renders cleanly after page settles
			setTimeout(function () { window.pmOfficialDl && window.pmOfficialDl(); }, 400);
		}
	}

	frappe.call({
		method: 'slcm.slcm.page.promotion_management.promotion_management.get_programs',
		callback: function (r) {
			var sel = document.getElementById('pm-prog');
			(r.message || []).forEach(function (p) {
				var o = document.createElement('option');
				o.value = p.name;
				o.text  = p.name + (p.program_name && p.program_name !== p.name ? ' — ' + p.program_name : '');
				sel.appendChild(o);
			});
			_dropdownsLoaded.programs = true;
			_checkAutoAction();
		},
	});

	frappe.call({
		method: 'slcm.slcm.page.promotion_management.promotion_management.get_academic_years',
		callback: function (r) {
			var sel = document.getElementById('pm-ay');
			(r.message || []).forEach(function (a) {
				var o = document.createElement('option');
				o.value = a.name;
				o.text  = a.name;
				sel.appendChild(o);
			});
			_dropdownsLoaded.years = true;
			_checkAutoAction();
		},
	});

	// ── Auto-increment target year ────────────────────────────────────────────
	$root.on('input', '#pm-fy', function () {
		var v = parseInt(this.value);
		if (!isNaN(v)) {
			$('#pm-ty').val(v + 1);
			S.fromYear = String(v);
			S.toYear   = String(v + 1);
		}
		loadPolicies();
	});
	$root.on('change', '#pm-prog', function () {
		S.program = this.value; loadPolicies();
	});
	$root.on('change', '#pm-ay', function () {
		S.academicYear = this.value; loadPolicies();
	});
	$root.on('input', '#pm-ty', function () {
		S.toYear = this.value;
	});
	$root.on('change', '#pm-policy', function () {
		S.policyName = this.value || null;
		renderPolicyStrip();
	});

	function loadPolicies() {
		var prog = $('#pm-prog').val();
		var ay   = $('#pm-ay').val();
		if (!prog || !ay) return;
		frappe.call({
			method: 'slcm.slcm.page.promotion_management.promotion_management.get_policies_for_filters',
			args: { program: prog, academic_year: ay },
			callback: function (r) {
				var sel = document.getElementById('pm-policy');
				sel.innerHTML = '<option value="">-- No policy / All Promoted --</option>';
				(r.message || []).forEach(function (p) {
					var o = document.createElement('option');
					o.value = p.name;
					o.text  = p.title + ' (Yr ' + p.from_year + '→' + p.to_year + ')';
					o._data = p;
					sel.appendChild(o);
				});
				S.policyName = null;
				renderPolicyStrip();
			},
		});
	}

	function renderPolicyStrip() {
		var sel  = document.getElementById('pm-policy');
		var opt  = sel.options[sel.selectedIndex];
		var data = opt && opt._data;
		if (!data) { $('#pm-policy-strip').hide(); return; }

		var html = '<span style="font-weight:700;color:#6366f1;margin-right:6px;">Active Criteria:</span>';
		html += data.enable_cgpa_check
			? '<span class="pm-crit on">&#10003; CGPA &ge; ' + (data.min_cgpa || 0) + '</span>'
			: '<span class="pm-crit off">CGPA: off</span>';
		html += data.enable_backlog_check
			? '<span class="pm-crit on">&#10003; Max ' + (data.max_backlogs_allowed || 0) + ' backlogs</span>'
			: '<span class="pm-crit off">Backlogs: off</span>';
		html += data.enable_attendance_check
			? '<span class="pm-crit on">&#10003; Avg Att &ge; ' + (data.min_attendance_percent || 0) + '%</span>'
			: '<span class="pm-crit off">Avg Att: off</span>';
		html += data.enable_course_shortage_check
			? '<span class="pm-crit on">&#10003; Shortage &le; ' + (data.max_shortage_courses != null ? data.max_shortage_courses : 2) + ' courses</span>'
			: '<span class="pm-crit off">Shortage: off</span>';
		html += data.enable_cf_check
			? '<span class="pm-crit on">&#10003; CF FA+Shortage &le; ' + (data.max_cf_fa_shortage != null ? data.max_cf_fa_shortage : 0) + '</span>'
			: '<span class="pm-crit off">CF Check: off</span>';
		html += '<a href="/app/promotion-policy/' + data.name + '" target="_blank" style="margin-left:auto;font-size:11px;color:#6366f1;">Edit Policy &#8599;</a>';

		$('#pm-policy-strip').html(html).show();
	}

	// ── Fetch Students ────────────────────────────────────────────────────────
	$root.on('click', '#pm-fetch-btn', function () {
		var prog = $('#pm-prog').val();
		var ay   = $('#pm-ay').val();
		var fy   = $('#pm-fy').val();
		var ty   = $('#pm-ty').val();

		if (!prog)  { frappe.show_alert({message: 'Please select a Program.', indicator: 'red'}); return; }
		if (!ay)    { frappe.show_alert({message: 'Please select an Academic Year.', indicator: 'red'}); return; }
		if (!fy)    { frappe.show_alert({message: 'Please enter Current Year (e.g. 1).', indicator: 'red'}); return; }
		if (!ty)    { $('#pm-ty').val(parseInt(fy) + 1); ty = $('#pm-ty').val(); }

		S.program = prog; S.academicYear = ay; S.fromYear = fy; S.toYear = ty;

		var $btn = $(this);
		$btn.prop('disabled', true).text('Fetching...');
		$('#pm-notice').hide();

		frappe.call({
			method: 'slcm.slcm.page.promotion_management.promotion_management.fetch_students',
			args: {
				program:       prog,
				academic_year: ay,
				from_year:     fy,
				policy_name:   S.policyName || '',
			},
			callback: function (r) {
				$btn.prop('disabled', false).html('&#8618; Fetch Students');
				if (!r.message) return;

				var data = r.message;
				if (!data.students || !data.students.length) {
					showNotice('warn', '&#9888; No active students found for the selected filters. Verify Program, Academic Year, and Current Year match your Cohort settings.');
					$('#pm-stats,#pm-actrow,#pm-tabs,#pm-table-card,#pm-dl-bar').hide();
					return;
				}

				S.students  = data.students;
				S.counts    = data.counts;
				S.confirmed = false;
				$('#pm-confirm-btn').prop('disabled', false);
				showNotice('warn', '&#9888; Preview only — click <strong>Confirm &amp; Save</strong> to persist these results and update student records.');
				renderAll();

				// Check for existing saved results
				frappe.call({
					method: 'slcm.slcm.page.promotion_management.promotion_management.get_saved_results_by_filters',
					args: { program: prog, academic_year: ay, from_year: fy, to_year: ty },
					callback: function (res) {
						if (res.message && res.message.records && res.message.records.length) {
							S.policyName = res.message.policy_name;
							S.students   = res.message.records.map(function(r) {
								return {
									student: r.student, student_name: r.student_name,
									batch_year: r.batch_year, current_year: r.current_year,
									target_year: r.target_year, promotion_status: r.promotion_status,
									current_cgpa: r.current_cgpa, backlog_count: r.backlog_count,
									attendance_percent: r.attendance_percent,
									shortage_course_count: r.shortage_course_count,
									cf_fa_shortage_count: r.cf_fa_shortage_count,
									cgpa_result: r.cgpa_result, backlog_result: r.backlog_result,
									attendance_result: r.attendance_result,
									shortage_course_result: r.shortage_course_result,
									cf_result: r.cf_result,
									manual_override: r.manual_override, override_reason: r.override_reason,
									name: r.name,
								};
							});
							S.confirmed = true;
							S.counts = countStudents(S.students);
							showNotice('info', '&#9432; Previously saved results loaded. Fetch again to re-evaluate, or download below.');
							$('#pm-confirm-btn').prop('disabled', true);
							renderAll();
						}
					},
				});
			},
			error: function () {
				$btn.prop('disabled', false).html('&#8618; Fetch Students');
			},
		});
	});

	// ── Confirm & Save ────────────────────────────────────────────────────────
	$root.on('click', '#pm-confirm-btn', function () {
		frappe.confirm(
			'Save promotion decisions for all <strong>' + S.students.length + ' students</strong>? Promoted students\' year will be updated automatically.',
			function () {
				$('#pm-confirm-btn').prop('disabled', true).text('Saving...');
				frappe.call({
					method: 'slcm.slcm.page.promotion_management.promotion_management.confirm_promotion',
					args: {
						program:       S.program,
						academic_year: S.academicYear,
						from_year:     S.fromYear,
						to_year:       S.toYear,
						policy_name:   S.policyName || '',
					},
					callback: function (r) {
						$('#pm-confirm-btn').prop('disabled', true).html('&#10003; Confirm &amp; Save Promotion');
						if (!r.message) return;
						var m = r.message;
						S.policyName = m.policy_name;
						S.confirmed  = true;
						showNotice('ok',
							'&#10003; Saved! <strong>' + m.promoted + '</strong> Promoted &nbsp;|&nbsp; '
							+ '<strong>' + m.not_promoted + '</strong> Not Promoted &nbsp;|&nbsp; '
							+ '<strong>' + m.conditional + '</strong> Conditional &nbsp;&mdash;&nbsp; Total: <strong>' + m.total + '</strong>'
						);
						$('#pm-dl-bar').show();
					},
					error: function () {
						$('#pm-confirm-btn').prop('disabled', false).html('&#10003; Confirm &amp; Save Promotion');
					},
				});
			}
		);
	});

	// ── Search & Tabs ─────────────────────────────────────────────────────────
	$root.on('input', '#pm-search', function () {
		S.search = this.value.toLowerCase();
		renderTable();
	});
	$root.on('click', '.pm-tab', function () {
		$('.pm-tab').removeClass('active');
		$(this).addClass('active');
		S.activeTab = $(this).data('tab');
		renderTable();
	});

	// ── Render helpers ────────────────────────────────────────────────────────

	function countStudents(rows) {
		var c = {total: rows.length, promoted: 0, not_promoted: 0, conditional: 0};
		rows.forEach(function (r) {
			var s = (r.promotion_status || '').toLowerCase();
			if (s === 'promoted' || s === 'override - promoted') c.promoted++;
			else if (s === 'not promoted' || s === 'override - not promoted') c.not_promoted++;
			else c.conditional++;
		});
		return c;
	}

	function renderAll() {
		var c = S.counts;
		$('#sc-total').text(c.total);
		$('#sc-pro').text(c.promoted);
		$('#sc-not').text(c.not_promoted);
		$('#sc-cond').text(c.conditional);
		$('#tb-all').text(c.total);
		$('#tb-pro').text(c.promoted);
		$('#tb-not').text(c.not_promoted);
		$('#tb-cond').text(c.conditional);
		$('#pm-stats,#pm-actrow,#pm-tabs,#pm-table-card').show();
		if (S.confirmed) $('#pm-dl-bar').show();
		renderTable();
	}

	function renderTable() {
		var data = S.students;
		var tab  = S.activeTab;
		var term = S.search;

		var filtered = data.filter(function (r) {
			var s = (r.promotion_status || '').toLowerCase();
			if (tab === 'promoted')     return s === 'promoted' || s === 'override - promoted';
			if (tab === 'not_promoted') return s === 'not promoted' || s === 'override - not promoted';
			if (tab === 'conditional')  return s === 'conditional';
			return true;
		});

		if (term) {
			filtered = filtered.filter(function (r) {
				return (r.student_name || '').toLowerCase().includes(term)
					|| (r.student || '').toLowerCase().includes(term);
			});
		}

		var tbody = document.getElementById('pm-tbody');
		if (!tbody) return;

		if (!filtered.length) {
			tbody.innerHTML = '<tr><td colspan="12"><div class="pm-empty"><div class="pm-empty-ico">&#128203;</div><div>No students found</div></div></td></tr>';
			return;
		}

		tbody.innerHTML = filtered.map(function (r, i) {
			var statusBadge = _badge(r.promotion_status);
			var rowName = r.name || '';
			return '<tr>'
				+ '<td>' + (i+1) + '</td>'
				+ '<td><a href="/app/student-master/' + esc(r.student) + '" target="_blank" style="color:#6366f1;">' + esc(r.student) + '</a></td>'
				+ '<td><strong>' + esc(r.student_name || '') + '</strong></td>'
				+ '<td>' + esc(r.batch_year || '—') + '</td>'
				+ '<td><strong>' + (r.current_cgpa != null ? flt2(r.current_cgpa) : '—') + '</strong></td>'
				+ '<td>' + (r.backlog_count != null ? r.backlog_count : '—') + '</td>'
				+ '<td>' + (r.attendance_percent != null ? flt1(r.attendance_percent) + '%' : '—') + '</td>'
				+ '<td>' + _countBadge(r.shortage_course_count) + '</td>'
				+ '<td>' + _countBadge(r.cf_fa_shortage_count) + '</td>'
				+ '<td>' + _chk(r.cgpa_result) + '</td>'
				+ '<td>' + _chk(r.backlog_result) + '</td>'
				+ '<td>' + _chk(r.attendance_result) + '</td>'
				+ '<td>' + _chk(r.shortage_course_result) + '</td>'
				+ '<td>' + _chk(r.cf_result) + '</td>'
				+ '<td>' + statusBadge + (r.manual_override ? ' <small title="' + esc(r.override_reason||'') + '" style="cursor:help;">&#9998;</small>' : '') + '</td>'
				+ '<td>'
				+ (S.confirmed && rowName
					? '<button class="pm-btn sm" onclick="pmOverride(\'' + rowName + '\',\'' + esc(r.promotion_status) + '\')">Override</button>'
					: '—')
				+ '</td>'
				+ '</tr>';
		}).join('');
	}

	function _badge(s) {
		var cls = {
			'Promoted':                'bdg-pro',
			'Not Promoted':            'bdg-not',
			'Conditional':             'bdg-cond',
			'Override - Promoted':     'bdg-ovp',
			'Override - Not Promoted': 'bdg-ovn',
		}[s] || '';
		return '<span class="pm-bdg ' + cls + '">' + esc(s||'') + '</span>';
	}

	function _chk(v) {
		if (v === 'Pass') return '<span class="chk-pass">&#10003; Pass</span>';
		if (v === 'Fail') return '<span class="chk-fail">&#10007; Fail</span>';
		return '<span class="chk-nc">—</span>';
	}

	function _countBadge(v) {
		if (v == null) return '<span class="chk-nc">—</span>';
		var n = parseInt(v) || 0;
		if (n === 0) return '<span style="color:#16a34a;font-weight:700;">0</span>';
		return '<span style="color:#dc2626;font-weight:700;">' + n + '</span>';
	}

	function showNotice(type, html) {
		$('#pm-notice').attr('class', 'pm-notice ' + type).html('<span>' + html + '</span>').show();
	}
	function esc(s) {
		return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
	}
	function flt2(v) { return parseFloat(v).toFixed(2); }
	function flt1(v) { return parseFloat(v).toFixed(1); }

	// ── Globals ───────────────────────────────────────────────────────────────

	window.pmDl = function (listType) {
		if (!S.confirmed || !S.policyName) {
			frappe.msgprint('Please confirm the promotion first before downloading.');
			return;
		}
		var url = '/api/method/slcm.slcm.page.promotion_management.promotion_management.download_promotion_list'
			+ '?policy_name=' + encodeURIComponent(S.policyName)
			+ '&list_type='  + encodeURIComponent(listType);
		window.open(url, '_blank');
	};

	window.pmOfficialDl = function () {
		// Build program and academic year options from the selects that already exist
		var progOptions   = Array.from($('#pm-prog option')).map(function(o) { return {value: o.value, label: o.textContent}; }).filter(function(o) { return o.value; });
		var ayOptions     = Array.from($('#pm-ay option')).map(function(o) { return {value: o.value, label: o.textContent}; }).filter(function(o) { return o.value; });

		var dlDialog = new frappe.ui.Dialog({
			title: '&#128203; Download Official Promotion Report',
			fields: [
				{
					label: 'University / Institution Name',
					fieldname: 'university_name',
					fieldtype: 'Data',
					description: 'Printed at the top of the sheet (optional)',
					default: '',
				},
				{ fieldtype: 'Column Break' },
				{
					label: 'Program (Course)',
					fieldname: 'program',
					fieldtype: 'Select',
					options: [''].concat(progOptions.map(function(o) { return o.value; })).join('\n'),
					default: S.program || '',
					reqd: 1,
				},
				{ fieldtype: 'Section Break' },
				{
					label: 'Academic Year',
					fieldname: 'academic_year',
					fieldtype: 'Select',
					options: [''].concat(ayOptions.map(function(o) { return o.value; })).join('\n'),
					default: S.academicYear || '',
					reqd: 1,
				},
				{ fieldtype: 'Column Break' },
				{
					label: '',
					fieldname: 'info',
					fieldtype: 'HTML',
					options: '<div style="font-size:12px;color:#64748b;padding-top:18px;">'
						+ '&#9432; One sheet is created per year-level (based on Active policies).<br>'
						+ 'Each sheet shows Promoted students and Re-admitted students<br>'
						+ 'with term-wise failed / attendance-shortage courses.'
						+ '</div>',
				},
			],
			primary_action_label: '&#8659; Download Excel',
			primary_action: function (vals) {
				if (!vals.program || !vals.academic_year) {
					frappe.msgprint('Please select both Program and Academic Year.');
					return;
				}
				dlDialog.hide();
				var url = '/api/method/slcm.slcm.page.promotion_management.promotion_management.download_formatted_promotion_list'
					+ '?program='        + encodeURIComponent(vals.program)
					+ '&academic_year='  + encodeURIComponent(vals.academic_year)
					+ '&university_name='+ encodeURIComponent(vals.university_name || '');
				window.open(url, '_blank');
			},
		});
		dlDialog.show();
	};

	window.pmOverride = function (recordName, currentStatus) {
		var d = new frappe.ui.Dialog({
			title: 'Override Promotion Status',
			fields: [
				{
					label: 'New Status', fieldname: 'new_status', fieldtype: 'Select',
					options: 'Promoted\nNot Promoted\nConditional\nOverride - Promoted\nOverride - Not Promoted',
					default: currentStatus, reqd: 1,
				},
				{ label: 'Reason', fieldname: 'reason', fieldtype: 'Small Text', reqd: 1 },
			],
			primary_action_label: 'Save Override',
			primary_action: function (vals) {
				frappe.call({
					method: 'slcm.slcm.page.promotion_management.promotion_management.save_override',
					args: { record_name: recordName, new_status: vals.new_status, reason: vals.reason },
					callback: function () {
						d.hide();
						frappe.show_alert({ message: 'Override saved.', indicator: 'green' });
						frappe.call({
							method: 'slcm.slcm.page.promotion_management.promotion_management.get_saved_results_by_filters',
							args: {
								program: S.program, academic_year: S.academicYear,
								from_year: S.fromYear, to_year: S.toYear,
							},
							callback: function (res) {
								if (res.message && res.message.records) {
									S.students = res.message.records;
									S.counts   = countStudents(S.students);
									renderAll();
								}
							},
						});
					},
				});
			},
		});
		d.show();
	};
};
