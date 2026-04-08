frappe.pages['examination-result'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Examination Result',
		single_column: true,
	});

	// ── State ─────────────────────────────────────────────────────────────────
	var S = {
		department:      null,
		course:          null,
		info:            null,   // course_info response
		students:        [],
		total:           0,
		page:            1,
		page_length:     20,
		search:          '',
		sort_by:         'registration_id',
		sort_order:      'asc',
		marks:           {},     // student → {entries: {comp|atype → marks}, grade, ...}
		columns:         [],     // assessment config columns
		reexam_columns:  [],     // reexam config columns
		popup_timer:     null,
		popup_student:   null,
		left_collapsed:  false,
	};

	// ── CSS ───────────────────────────────────────────────────────────────────
	if (!document.getElementById('er2-style')) {
		var style = document.createElement('style');
		style.id  = 'er2-style';
		style.textContent = `
		.er2-wrap { font-family: var(--font-stack); padding: 0; }
		/* Tabs */
		.er2-tabs { display:flex; border-bottom:2px solid #e8eaed; margin-bottom:16px; }
		.er2-tab  { padding:10px 20px; cursor:pointer; font-size:14px; font-weight:500;
		            color:#6c757d; border-bottom:2px solid transparent; margin-bottom:-2px;
		            transition:color .15s, border-color .15s; }
		.er2-tab:hover { color:#e63946; }
		.er2-tab.active { color:#e63946; border-bottom-color:#e63946; }
		/* Filter bar */
		.er2-filters { display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;
		               margin-bottom:14px; padding:0 2px; }
		.er2-fgroup  { display:flex; flex-direction:column; min-width:200px; flex:1; }
		.er2-flabel  { font-size:11px; color:#6c757d; font-weight:500; margin-bottom:4px;
		               text-transform:uppercase; letter-spacing:.4px; }
		.er2-select  { height:34px; border:1px solid #d1d8dd; border-radius:4px;
		               padding:0 10px; font-size:13px; background:#fff; color:#333;
		               outline:none; cursor:pointer; }
		.er2-select:focus { border-color:#6195ff; }
		/* Info panel */
		.er2-info    { background:#fff; border:1px solid #e8eaed; border-radius:8px;
		               padding:16px 20px; margin-bottom:14px;
		               display:grid; grid-template-columns:1fr 1fr; gap:10px 32px; }
		.er2-irow    { display:flex; flex-direction:column; gap:2px; }
		.er2-ilabel  { font-size:11px; color:#8d99ae; text-transform:uppercase;
		               letter-spacing:.4px; font-weight:500; }
		.er2-ival    { font-size:13px; color:#2b2d42; font-weight:500; }
		.er2-ival a  { color:#e63946; text-decoration:none; }
		.er2-ival.green { color:#28a745; }
		.er2-ival.orange { color:#fd7e14; }
		/* Action bar */
		.er2-actbar  { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
		               margin-bottom:12px; }
		.er2-srch    { flex:1; min-width:220px; max-width:340px; position:relative; }
		.er2-srch input { width:100%; height:34px; border:1px solid #d1d8dd; border-radius:20px;
		                  padding:0 12px 0 34px; font-size:13px; outline:none; }
		.er2-srch input:focus { border-color:#6195ff; }
		.er2-srch-ico { position:absolute; left:10px; top:9px; color:#adb5bd; }
		.er2-btn     { height:34px; padding:0 14px; border-radius:4px; border:1px solid #d1d8dd;
		               background:#fff; cursor:pointer; font-size:13px; font-weight:500;
		               color:#333; display:inline-flex; align-items:center; gap:5px;
		               white-space:nowrap; }
		.er2-btn:hover { background:#f4f5f7; }
		.er2-btn.primary { background:#e63946; border-color:#e63946; color:#fff; }
		.er2-btn.primary:hover { background:#c1121f; }
		.er2-btn.outline-red { border-color:#e63946; color:#e63946; }
		.er2-btn.outline-red:hover { background:#fff5f5; }
		.er2-btn-dd  { position:relative; display:inline-flex; }
		.er2-btn-dd .dd-menu { display:none; position:absolute; top:38px; left:0; z-index:999;
		                       background:#fff; border:1px solid #d1d8dd; border-radius:4px;
		                       box-shadow:0 4px 12px rgba(0,0,0,.12); min-width:160px; padding:4px 0; }
		.er2-btn-dd:hover .dd-menu,
		.er2-btn-dd.open .dd-menu { display:block; }
		.dd-item { padding:8px 14px; font-size:13px; cursor:pointer; color:#333; }
		.dd-item:hover { background:#f4f5f7; }
		/* Filter row */
		.er2-filterrow { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
		.er2-pag     { margin-left:auto; display:flex; align-items:center; gap:6px;
		               font-size:13px; color:#6c757d; }
		.er2-pag-btn { width:28px; height:28px; border:1px solid #d1d8dd; border-radius:4px;
		               background:#fff; cursor:pointer; font-size:14px; display:inline-flex;
		               align-items:center; justify-content:center; }
		.er2-pag-btn:disabled { opacity:.4; cursor:default; }
		/* Split panel */
		.er2-split   { display:flex; gap:0; border:1px solid #e8eaed; border-radius:8px;
		               overflow:hidden; background:#fff; }
		.er2-left    { width:360px; flex-shrink:0; overflow-y:auto; overflow-x:hidden;
		               border-right:1px solid #e8eaed; }
		.er2-left.collapsed { width:0; border-right:none; }
		.er2-right   { flex:1; overflow:auto; min-width:0; }
		/* Left panel header */
		.er2-lhdr    { display:flex; align-items:center; gap:8px; padding:10px 12px;
		               background:#fafbfc; border-bottom:1px solid #e8eaed; position:sticky; top:0;
		               z-index:10; }
		.er2-lhdr-title { font-size:13px; font-weight:600; color:#333; flex:1; }
		.er2-sort-btn { font-size:11px; color:#6195ff; cursor:pointer; background:none;
		                border:none; padding:0; display:flex; align-items:center; gap:3px; }
		/* Student row */
		.er2-srow    { display:flex; align-items:center; gap:10px; padding:10px 12px;
		               border-bottom:1px solid #f1f3f5; cursor:pointer; min-height:70px; }
		.er2-srow:hover { background:#f8f9fa; }
		.er2-srow.selected { background:#e8f4ff; }
		.er2-savatar { width:36px; height:36px; border-radius:50%; background:#dee2e6;
		               display:flex; align-items:center; justify-content:center;
		               font-size:14px; color:#6c757d; flex-shrink:0; overflow:hidden; }
		.er2-savatar img { width:100%; height:100%; object-fit:cover; }
		.er2-sinfo   { flex:1; min-width:0; }
		.er2-sname   { font-size:13px; font-weight:600; color:#e63946; white-space:nowrap;
		               overflow:hidden; text-overflow:ellipsis; }
		.er2-sreg    { font-size:11px; color:#6c757d; margin-top:1px; }
		.er2-sbadges { display:flex; gap:4px; margin-top:3px; flex-wrap:wrap; }
		.er2-badge   { font-size:10px; font-weight:600; padding:1px 7px; border-radius:10px; }
		.er2-badge.active   { background:#d4edda; color:#155724; }
		.er2-badge.inactive { background:#f8d7da; color:#721c24; }
		.er2-badge.blocked  { background:#f8d7da; color:#721c24; }
		.er2-badge.regular  { background:#e2e3e5; color:#383d41; }
		.er2-badge.dropped  { background:#fff3cd; color:#856404; }
		/* Right panel marks table */
		.er2-rtable  { border-collapse:collapse; min-width:100%; font-size:12px; }
		.er2-rtable th, .er2-rtable td { padding:6px 10px; border-right:1px solid #e8eaed;
		                                  white-space:nowrap; }
		.er2-rtable th { background:#fafbfc; position:sticky; top:0; z-index:5;
		                 font-weight:600; color:#495057; text-align:center;
		                 border-bottom:1px solid #dee2e6; }
		.er2-rtable th.type-hdr { background:#f0f2f5; border-bottom:2px solid #dee2e6; }
		.er2-rtable td { text-align:center; color:#333; border-bottom:1px solid #f1f3f5; }
		.er2-rtable tr:hover td { background:#f8f9fa; }
		.er2-mrow    { min-height:70px; height:70px; }
		.er2-toggle-wrap { display:flex; align-items:center; gap:8px; padding:8px 12px;
		                   background:#fafbfc; border-bottom:1px solid #e8eaed;
		                   position:sticky; top:0; z-index:10; }
		.er2-toggle-lbl { font-size:12px; font-weight:600; color:#333; }
		.er2-toggle  { position:relative; width:36px; height:20px; }
		.er2-toggle input { opacity:0; width:0; height:0; }
		.er2-slider  { position:absolute; inset:0; border-radius:20px; background:#ccc;
		               cursor:pointer; transition:background .2s; }
		.er2-slider:before { content:''; position:absolute; width:14px; height:14px;
		                     left:3px; top:3px; border-radius:50%; background:#fff;
		                     transition:transform .2s; }
		.er2-toggle input:checked + .er2-slider { background:#28a745; }
		.er2-toggle input:checked + .er2-slider:before { transform:translateX(16px); }
		.er2-collapse-btn { width:20px; cursor:pointer; display:flex; align-items:center;
		                    justify-content:center; background:#f0f2f5; border:none;
		                    border-left:1px solid #e8eaed; color:#6c757d; font-size:14px;
		                    align-self:stretch; flex-shrink:0; }
		.er2-collapse-btn:hover { background:#e8eaed; }
		/* Hover popup */
		#er2-popup   { display:none; position:fixed; z-index:9999; background:#fff;
		               border:1px solid #d1d8dd; border-radius:8px;
		               box-shadow:0 6px 20px rgba(0,0,0,.15); padding:16px 18px;
		               min-width:280px; max-width:360px; pointer-events:none; }
		.er2-pop-name { font-size:15px; font-weight:700; color:#e63946; margin-bottom:10px; }
		.er2-pop-row  { display:flex; gap:8px; margin-bottom:5px; font-size:13px; }
		.er2-pop-lbl  { color:#8d99ae; min-width:100px; font-weight:500; flex-shrink:0; }
		.er2-pop-val  { color:#2b2d42; font-weight:500; }
		/* Sync marks btn */
		.er2-sync-btn { font-size:10px; background:#e63946; color:#fff; border:none;
		                border-radius:3px; padding:2px 6px; cursor:pointer; margin-top:3px; }
		.er2-sync-btn:hover { background:#c1121f; }
		/* Empty state */
		.er2-empty   { display:flex; flex-direction:column; align-items:center;
		               justify-content:center; padding:80px 20px; color:#adb5bd; }
		.er2-empty svg { width:80px; height:80px; margin-bottom:16px; }
		.er2-empty-txt { font-size:15px; font-weight:500; }
		`;
		document.head.appendChild(style);
	}

	// ── Render shell ──────────────────────────────────────────────────────────
	var $body = $(page.main);
	$body.html(`
		<div class="er2-wrap" style="padding:16px 20px;">

			<!-- Tabs -->
			<div class="er2-tabs">
				<div class="er2-tab active" data-tab="course">Course Results</div>
				<div class="er2-tab" data-tab="term">Term Results</div>
				<div class="er2-tab" data-tab="publish">Publish Results</div>
				<div class="er2-tab" data-tab="settings">Settings</div>
			</div>

			<!-- Course Results tab -->
			<div id="er2-tab-course">

				<!-- Top filter bar -->
				<div class="er2-filters">
					<div class="er2-fgroup" style="max-width:260px;">
						<span class="er2-flabel">Department</span>
						<select class="er2-select" id="er2-dept">
							<option value="">Select Department</option>
						</select>
					</div>
					<div class="er2-fgroup" style="max-width:300px;">
						<span class="er2-flabel">Course</span>
						<select class="er2-select" id="er2-course" disabled>
							<option value="">Select Course</option>
						</select>
					</div>
					<div style="margin-left:auto;display:flex;gap:8px;align-items:flex-end;">
						<div class="er2-btn-dd">
							<button class="er2-btn outline-red" id="er2-sync-btn">
								<i class="fa fa-refresh"></i> Sync Students <i class="fa fa-caret-down"></i>
							</button>
							<div class="dd-menu">
								<div class="dd-item" id="er2-sync-enroll">Sync from Enrollment</div>
								<div class="dd-item" id="er2-sync-class">Add Class Students</div>
							</div>
						</div>
						<button class="er2-btn outline-red" id="er2-lock-btn">
							<i class="fa fa-lock"></i> Lock
						</button>
					</div>
				</div>

				<!-- Course info panel (hidden until course selected) -->
				<div id="er2-info-panel" style="display:none;"></div>

				<!-- Action bar (hidden until course selected) -->
				<div id="er2-actbar" class="er2-actbar" style="display:none;">
					<div class="er2-srch">
						<span class="er2-srch-ico">
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none"
							     stroke="currentColor" stroke-width="2">
								<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
							</svg>
						</span>
						<input type="text" id="er2-search" placeholder="Search by Student Name / Id">
					</div>
					<button class="er2-btn" id="er2-moderation-btn">Result Moderation</button>
					<div class="er2-btn-dd" id="er2-grades-dd">
						<button class="er2-btn outline-red">
							Manage Grades <i class="fa fa-caret-down"></i>
						</button>
						<div class="dd-menu">
							<div class="dd-item" id="er2-grade-edit">Edit</div>
							<div class="dd-item" id="er2-grade-bulk-upload">Bulk Upload</div>
							<div class="dd-item" id="er2-grade-report">Grade Report</div>
						</div>
					</div>
					<div class="er2-btn-dd" id="er2-marks-dd">
						<button class="er2-btn outline-red">
							Manage Marks <i class="fa fa-caret-down"></i>
						</button>
						<div class="dd-menu">
							<div class="dd-item">Import Marks</div>
							<div class="dd-item">Export Marks</div>
							<div class="dd-item">Clear All Marks</div>
						</div>
					</div>
					<div class="er2-btn-dd" id="er2-status-dd">
						<button class="er2-btn">
							Manage Status <i class="fa fa-caret-down"></i>
						</button>
						<div class="dd-menu">
							<div class="dd-item">Mark as Submitted</div>
							<div class="dd-item">Mark as Draft</div>
							<div class="dd-item">Lock Selected</div>
						</div>
					</div>
				</div>

				<!-- Filter row (hidden until course selected) -->
				<div id="er2-filterrow" class="er2-filterrow" style="display:none;">
					<select class="er2-select" id="er2-exam-filter" style="max-width:180px;">
						<option value="">Filter Exam Type</option>
					</select>
					<div class="er2-pag" id="er2-pag">
						<span id="er2-pag-info"></span>
						<button class="er2-pag-btn" id="er2-prev">&#8249;</button>
						<button class="er2-pag-btn" id="er2-next">&#8250;</button>
					</div>
					<button class="er2-btn" id="er2-inst-filter" style="margin-left:4px;">
						<svg width="12" height="12" viewBox="0 0 24 24" fill="none"
						     stroke="currentColor" stroke-width="2" style="margin-right:4px;">
							<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
						</svg>
						Institutional Filter
					</button>
				</div>

				<!-- Empty state -->
				<div id="er2-empty" class="er2-empty">
					<svg viewBox="0 0 24 24" fill="none" stroke="#e63946" stroke-width="1.5">
						<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
						<polyline points="14 2 14 8 20 8"/>
						<line x1="16" y1="13" x2="8" y2="13"/>
						<line x1="16" y1="17" x2="8" y2="17"/>
						<polyline points="10 9 9 9 8 9"/>
						<circle cx="19" cy="19" r="4" fill="#e63946" stroke="none"/>
						<path d="M17 19h4M19 17v4" stroke="#fff" stroke-width="1.5"/>
					</svg>
					<div class="er2-empty-txt">Please Select Department &amp; Course</div>
				</div>

				<!-- Split panel -->
				<div id="er2-split" class="er2-split" style="display:none;max-height:calc(100vh - 360px);">
					<!-- Left: student list -->
					<div id="er2-left" class="er2-left">
						<div class="er2-lhdr">
							<input type="checkbox" id="er2-chk-all" title="Select All">
							<span class="er2-lhdr-title" id="er2-student-count-lbl">Students (0)</span>
							<button class="er2-sort-btn" id="er2-sort-btn">
								<svg width="12" height="12" viewBox="0 0 24 24" fill="none"
								     stroke="currentColor" stroke-width="2.5">
									<path d="M11 5H21M11 9H17M11 13H13"/>
									<path d="M3 7l4-4 4 4M7 3v14M3 17l4 4 4-4"/>
								</svg>
								<span id="er2-sort-lbl">Registration Id</span>
							</button>
						</div>
						<div id="er2-student-list"></div>
					</div>
					<!-- Collapse toggle -->
					<button class="er2-collapse-btn" id="er2-collapse-btn" title="Toggle panel">&#9664;</button>
					<!-- Right: marks grid -->
					<div id="er2-right" class="er2-right">
						<div class="er2-toggle-wrap" style="display:none;">
							<label class="er2-toggle">
								<input type="checkbox" id="er2-internal-toggle">
								<span class="er2-slider"></span>
							</label>
							<span class="er2-toggle-lbl">Internal</span>
						</div>
						<div id="er2-marks-table-wrap"></div>
					</div>
				</div>

			</div><!-- /tab-course -->

			<!-- Other tabs (stubs) -->
			<div id="er2-tab-term" style="display:none;">
				<div class="er2-empty" style="padding:60px;">
					<div class="er2-empty-txt" style="color:#adb5bd;">Term Results — Coming Soon</div>
				</div>
			</div>
			<div id="er2-tab-publish" style="display:none;">
				<div class="er2-empty" style="padding:60px;">
					<div class="er2-empty-txt" style="color:#adb5bd;">Publish Results — Coming Soon</div>
				</div>
			</div>
			<div id="er2-tab-settings" style="display:none;">
				<div class="er2-empty" style="padding:60px;">
					<div class="er2-empty-txt" style="color:#adb5bd;">Settings — Coming Soon</div>
				</div>
			</div>
		</div>

		<!-- Hover popup -->
		<div id="er2-popup"></div>
	`);

	// ── DOM refs ──────────────────────────────────────────────────────────────
	var $dept     = $body.find('#er2-dept');
	var $course   = $body.find('#er2-course');
	var $info     = $body.find('#er2-info-panel');
	var $actbar   = $body.find('#er2-actbar');
	var $filterrow= $body.find('#er2-filterrow');
	var $empty    = $body.find('#er2-empty');
	var $split    = $body.find('#er2-split');
	var $left     = $body.find('#er2-left');
	var $right    = $body.find('#er2-right');
	var $slist    = $body.find('#er2-student-list');
	var $mtable   = $body.find('#er2-marks-table-wrap');
	var $search   = $body.find('#er2-search');
	var $prevBtn  = $body.find('#er2-prev');
	var $nextBtn  = $body.find('#er2-next');
	var $pagInfo  = $body.find('#er2-pag-info');
	var $cntLbl   = $body.find('#er2-student-count-lbl');
	var $collapse = $body.find('#er2-collapse-btn');
	var $popup    = $('#er2-popup');
	var $examFilter = $body.find('#er2-exam-filter');

	// ── Tabs ──────────────────────────────────────────────────────────────────
	$body.find('.er2-tab').on('click', function () {
		$body.find('.er2-tab').removeClass('active');
		$(this).addClass('active');
		var tab = $(this).data('tab');
		$body.find('#er2-tab-course, #er2-tab-term, #er2-tab-publish, #er2-tab-settings').hide();
		$body.find('#er2-tab-' + tab).show();
	});

	// ── Collapse left panel ───────────────────────────────────────────────────
	$collapse.on('click', function () {
		S.left_collapsed = !S.left_collapsed;
		$left.toggleClass('collapsed', S.left_collapsed);
		$collapse.html(S.left_collapsed ? '&#9654;' : '&#9664;');
	});

	// ── Sync vertical scroll ──────────────────────────────────────────────────
	var syncing = false;
	$left[0].addEventListener('scroll', function () {
		if (syncing) return;
		syncing = true;
		$right[0].scrollTop = $left[0].scrollTop;
		syncing = false;
	});
	$right[0].addEventListener('scroll', function () {
		if (syncing) return;
		syncing = true;
		$left[0].scrollTop = $right[0].scrollTop;
		syncing = false;
	});

	// ── Load departments ──────────────────────────────────────────────────────
	frappe.call({
		method: 'slcm.slcm.page.examination_result.examination_result.get_departments',
		callback: function (r) {
			(r.message || []).forEach(function (d) {
				$dept.append('<option value="' + d.name + '">' +
					frappe.utils.escape_html(d.department_name) + '</option>');
			});
		},
	});

	// ── Dept change ───────────────────────────────────────────────────────────
	$dept.on('change', function () {
		S.department = $(this).val();
		S.course     = null;
		S.page       = 1;
		$course.val('').prop('disabled', true).find('option:not(:first)').remove();
		hide_detail();
		if (!S.department) return;
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_courses_by_department',
			args: { department: S.department },
			callback: function (r) {
				(r.message || []).forEach(function (c) {
					$course.append('<option value="' + c.name + '">' +
						frappe.utils.escape_html(c.course_name) +
						(c.course_code ? ' [' + c.course_code + ']' : '') + '</option>');
				});
				$course.prop('disabled', false);
			},
		});
	});

	// ── Course change ─────────────────────────────────────────────────────────
	$course.on('change', function () {
		S.course = $(this).val();
		S.page   = 1;
		S.search = '';
		$search.val('');
		hide_detail();
		if (!S.course) return;
		load_course_info();
	});

	// ── Search ────────────────────────────────────────────────────────────────
	$search.on('input', frappe.utils.debounce(function () {
		S.search = $search.val().trim();
		S.page   = 1;
		if (S.course) load_students();
	}, 400));

	// ── Pagination ────────────────────────────────────────────────────────────
	$prevBtn.on('click', function () {
		if (S.page > 1) { S.page--; load_students(); }
	});
	$nextBtn.on('click', function () {
		S.page++;
		load_students();
	});

	// ── Sort ──────────────────────────────────────────────────────────────────
	$body.find('#er2-sort-btn').on('click', function () {
		if (S.sort_by === 'registration_id') {
			S.sort_order = S.sort_order === 'asc' ? 'desc' : 'asc';
		} else {
			S.sort_by    = 'registration_id';
			S.sort_order = 'asc';
		}
		S.page = 1;
		if (S.course) load_students();
	});

	// ── Exam type filter ──────────────────────────────────────────────────────
	$examFilter.on('change', function () {
		render_marks_table();
	});

	// ── Stub buttons ─────────────────────────────────────────────────────────
	$body.find('#er2-moderation-btn').on('click', function () {
		frappe.msgprint('Result Moderation — coming soon.');
	});

	// ── Manage Grades ─────────────────────────────────────────────────────────
	$body.find('#er2-grade-edit').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }
		frappe.msgprint('Edit Grades — coming soon.');
	});

	$body.find('#er2-grade-report').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }
		frappe.msgprint('Grade Report — coming soon.');
	});

	$body.find('#er2-grade-bulk-upload').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }

		var include_students = true;

		var d = new frappe.ui.Dialog({
			title: 'Update Grade In Bulk',
			fields: [
				{
					fieldname: 'info',
					fieldtype: 'HTML',
					options: '<p style="margin-bottom:12px;font-size:13px;color:#333;">Update Grade by uploading an excel file.</p>',
				},
				{
					fieldname: 'include_students',
					fieldtype: 'Check',
					label: 'Include students in sample Excel?',
					default: 1,
					onchange: function () {
						include_students = !!d.get_value('include_students');
					},
				},
				{
					fieldname: 'download_sec',
					fieldtype: 'HTML',
					options: '<div style="margin:10px 0 4px;">' +
						'<button class="btn btn-default btn-sm" id="er2-grade-download-sample" style="width:100%;">' +
						'Download Sample Excel</button></div>',
				},
				{
					fieldname: 'upload_file',
					fieldtype: 'Attach',
					label: 'Upload File',
					reqd: 1,
				},
				{
					fieldname: 'notes_sec',
					fieldtype: 'HTML',
					options: '<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;padding:10px 14px;margin-top:8px;">' +
						'<div style="font-weight:600;margin-bottom:6px;font-size:13px;">Notes</div>' +
						'<ol style="margin:0;padding-left:18px;font-size:12px;color:#555;">' +
						'<li>Either student Registration ID or Email ID should be entered.</li>' +
						'<li>Before updating results, take a backup via Download sample excel.</li>' +
						'</ol></div>',
				},
			],
			primary_action_label: 'Upload File',
			primary_action: function (values) {
				if (!values.upload_file) {
					frappe.msgprint('Please upload a file.');
					return;
				}
				d.hide();
				frappe.call({
					method: 'slcm.slcm.page.examination_result.examination_result.bulk_upload_grades',
					args: {
						course:    S.course,
						exam_plan: S.info.exam_plan || '',
						file_url:  values.upload_file,
					},
					callback: function (r) {
						var res = r.message || {};
						frappe.show_alert({
							message: 'Grades updated: ' + (res.updated || 0) + ' rows processed.',
							indicator: 'green'
						});
						load_students();
					},
				});
			},
		});

		d.show();

		// Wire download button after dialog renders
		setTimeout(function () {
			$('#er2-grade-download-sample').on('click', function () {
				frappe.call({
					method: 'slcm.slcm.page.examination_result.examination_result.download_grade_sample',
					args: {
						course:           S.course,
						exam_plan:        S.info.exam_plan || '',
						include_students: include_students ? 1 : 0,
					},
					callback: function (r) {
						if (r.message && r.message.file_url) {
							window.open(r.message.file_url);
						}
					},
				});
			});
		}, 300);
	});
	$body.find('#er2-lock-btn').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }
		frappe.confirm('Lock this course for result entry?', function () {
			frappe.show_alert({ message: 'Lock feature coming soon.', indicator: 'orange' });
		});
	});
	$body.find('#er2-sync-btn').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }
	});

	$body.find('#er2-sync-enroll').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }
		frappe.confirm('Sync students from Student Enrollment for this course?', function () {
			frappe.call({
				method: 'slcm.slcm.page.examination_result.examination_result.sync_students_from_enrollment',
				args: { course: S.course },
				callback: function (r) {
					var res = r.message || {};
					frappe.show_alert({
						message: 'Synced: ' + (res.added || 0) + ' added, ' + (res.skipped || 0) + ' already existed.',
						indicator: 'green'
					});
					load_course_info();
				},
			});
		});
	});

	$body.find('#er2-sync-class').on('click', function () {
		if (!S.course) { frappe.msgprint('Select a course first.'); return; }
		var d = new frappe.ui.Dialog({
			title: 'Add Class Students',
			fields: [
				{
					fieldname: 'class_config',
					fieldtype: 'Link',
					label: 'Class',
					options: 'Class Configuration',
					reqd: 1,
					get_query: function () {
						return { filters: { course: S.course } };
					},
				},
				{
					fieldname: 'course_type',
					fieldtype: 'Select',
					label: 'Course Type',
					options: '\nCore\nElective',
					reqd: 1,
				},
			],
			primary_action_label: 'Add Students',
			primary_action: function (values) {
				d.hide();
				frappe.call({
					method: 'slcm.slcm.page.examination_result.examination_result.sync_students_from_class_config',
					args: {
						course:       S.course,
						class_config: values.class_config,
						course_type:  values.course_type,
					},
					callback: function (r) {
						var res = r.message || {};
						frappe.show_alert({
							message: 'Added: ' + (res.added || 0) + ' students, ' + (res.skipped || 0) + ' already existed.',
							indicator: 'green'
						});
						load_course_info();
					},
				});
			},
		});
		d.show();
	});

	// ── Data loaders ──────────────────────────────────────────────────────────
	function load_course_info() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_course_info',
			args: { course: S.course },
			callback: function (r) {
				S.info           = r.message || {};
				S.columns        = S.info.columns || [];
				S.reexam_columns = S.info.reexam_columns || [];
				render_info_panel();
				populate_exam_filter();
				$info.show();
				$actbar.show();
				$filterrow.show();
				$empty.hide();
				$split.show();
				$cntLbl.text('Students (' + S.info.student_count + ')');
				load_students();
			},
		});
	}

	function load_students() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_course_students_paged',
			args: {
				course:       S.course,
				search:       S.search,
				page:         S.page,
				page_length:  S.page_length,
				sort_by:      S.sort_by,
				sort_order:   S.sort_order,
			},
			callback: function (r) {
				var data   = r.message || {};
				S.students = data.students || [];
				S.total    = data.total || 0;
				render_student_list();
				load_marks();
				update_pagination();
			},
		});
	}

	function load_marks() {
		if (!S.students.length || !S.info.exam_plan) {
			S.marks = {};
			render_marks_table();
			return;
		}
		var ids = S.students.map(function (s) { return s.student; });
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_marks_for_students',
			args: {
				course:      S.course,
				exam_plan:   S.info.exam_plan,
				student_ids: JSON.stringify(ids),
			},
			callback: function (r) {
				S.marks = r.message || {};
				render_marks_table();
			},
		});
	}

	// ── Renderers ────────────────────────────────────────────────────────────
	function render_info_panel() {
		var o = S.info || {};
		function row(label, val, cls) {
			return '<div class="er2-irow"><span class="er2-ilabel">' + label + '</span>' +
				'<span class="er2-ival' + (cls ? ' ' + cls : '') + '">' + val + '</span></div>';
		}
		var view_access = o.view_access ? '<span style="color:#28a745;font-weight:600;">ON</span>' : '<span style="color:#6c757d;">OFF</span>';
		var edit_val    = o.edit_access
			? '<span style="color:#28a745;font-weight:600;">ON</span>' + (o.edit_deadline ? ' | ' + frappe.utils.escape_html(o.edit_deadline) : '')
			: '<span style="color:#6c757d;">OFF</span>';
		var mask_val    = o.mask_student_info
			? '<span style="color:#28a745;font-weight:600;">ON</span> | Admin Access'
			: '<span style="color:#6c757d;">OFF</span>';
		var eval_link   = o.evaluation_schema
			? '<a href="#" class="er2-schema-link" data-schema="eval" data-name="' + frappe.utils.escape_html(o.evaluation_schema) + '">' + frappe.utils.escape_html(o.evaluation_schema) + '</a>'
			: '—';
		var grade_link  = o.grade_schema
			? '<a href="#" class="er2-schema-link" data-schema="grade" data-name="' + frappe.utils.escape_html(o.grade_schema) + '">' + frappe.utils.escape_html(o.grade_schema) + '</a>'
			: '—';
		var calc_link   = o.evaluation_schema
			? '<a href="#" id="er2-calc-settings-link">Calculation Settings</a>'
			: '—';

		$info.html(
			'<div class="er2-info">' +
			row('Number of Students', '<span style="color:#e63946;font-weight:700;font-size:16px;">' + o.student_count + '</span>') +
			row('Evaluation Schema', eval_link) +
			row('Course Name [Code]', frappe.utils.escape_html((o.course_name || '') + (o.course_code ? ' [' + o.course_code + ']' : ''))) +
			row('Grade Schema', grade_link) +
			row('Course Credits', o.credit_value || '—') +
			row('Calculation Settings', calc_link) +
			row('View Access', view_access) +
			row('Edit Access', edit_val) +
			'<div class="er2-irow"></div>' +
			row('Student Masking', mask_val) +
			'</div>'
		);

		// Bind click handlers after rendering
		$info.find('#er2-calc-settings-link').on('click', function (e) {
			e.preventDefault();
			show_calc_settings_popup(S.info.evaluation_schema);
		});
		$info.find('.er2-schema-link').on('click', function (e) {
			e.preventDefault();
			var schema_type = $(this).data('schema');
			var name = $(this).data('name');
			if (schema_type === 'eval') show_eval_schema_popup(name);
			else show_grade_schema_popup(name);
		});
	}

	function populate_exam_filter() {
		$examFilter.find('option:not(:first)').remove();
		var seen = {};
		(S.columns || []).forEach(function (col) {
			var val = col.assessment_type || '';
			if (!val || seen[val]) return;
			seen[val] = true;
			var lbl = col.type_name || col.assessment_type || '';
			$examFilter.append('<option value="' + frappe.utils.escape_html(val) + '">' +
				frappe.utils.escape_html(lbl) + '</option>');
		});
	}

	function render_student_list() {
		var html = '';
		S.students.forEach(function (s) {
			var status_cls = s.account_status === 'Blocked' ? 'blocked' :
				s.student_status === 'Dropped' ? 'dropped' : 'active';
			var status_txt = s.student_status || 'Active';
			var initials   = (s.student_name || 'S').charAt(0).toUpperCase();
			html +=
				'<div class="er2-srow" data-student="' + frappe.utils.escape_html(s.student) + '">' +
				'  <input type="checkbox" class="er2-chk" style="flex-shrink:0;">' +
				'  <div class="er2-savatar">' + initials + '</div>' +
				'  <div class="er2-sinfo">' +
				'    <div class="er2-sname">' + frappe.utils.escape_html(s.student_name || s.student) + '</div>' +
				'    <div class="er2-sreg">' + frappe.utils.escape_html(s.registration_id || s.student || '') + '</div>' +
				'    <div class="er2-sbadges">' +
				'      <span class="er2-badge ' + status_cls + '">' + frappe.utils.escape_html(status_txt) + '</span>' +
				'      <span class="er2-badge regular">Regular</span>' +
				'    </div>' +
				'  </div>' +
				'</div>';
		});
		if (!html) {
			html = '<div style="padding:40px;text-align:center;color:#adb5bd;font-size:13px;">No students found.</div>';
		}
		$slist.html(html);
		bind_hover();
	}

	function render_marks_table() {
		var cols         = S.columns || [];
		var reexam_cols  = S.reexam_columns || [];
		var filter_val   = $examFilter.val();
		if (filter_val) {
			cols = cols.filter(function (c) { return c.assessment_type === filter_val; });
		}

		if (!cols.length && !reexam_cols.length) {
			$mtable.html('<div style="padding:40px;text-align:center;color:#adb5bd;font-size:13px;">No assessment columns configured.</div>');
			return;
		}

		// ── Group regular cols by component ──────────────────────────────────────
		var groups = [];
		var group_map = {};
		cols.forEach(function (col) {
			var comp = col.component || '__none__';
			if (!group_map[comp]) {
				group_map[comp] = {
					component:      comp,
					component_name: col.component_name || comp,
					cols:           [],
				};
				groups.push(group_map[comp]);
			}
			group_map[comp].cols.push(col);
		});

		// ── Group reexam cols by component ───────────────────────────────────────
		var rxgroups = [];
		var rxgroup_map = {};
		reexam_cols.forEach(function (col) {
			var comp = col.component || '__rx_none__';
			if (!rxgroup_map[comp]) {
				rxgroup_map[comp] = {
					component:      comp,
					component_name: col.component_name || comp,
					cols:           [],
				};
				rxgroups.push(rxgroup_map[comp]);
			}
			rxgroup_map[comp].cols.push(col);
		});

		// ── Total number of data columns (for empty-row colspan) ─────────────────
		// Each regular assessment: 3 sub-cols (Marks, Reval, Moderated)
		// After regular cols: Total, Grade, Moderated Grade
		// Overall Status: 5 cols
		// Each reexam assessment: 2 sub-cols (Marks, Reval)
		// Updated Final Result: 2 cols
		var total_cols = cols.length * 3 + 3 + 5 + reexam_cols.length * 2 + 2;

		// ── CSS colours ──────────────────────────────────────────────────────────
		var C_COMP   = 'background:#dbe4ff;color:#364fc7;';       // component group
		var C_GRADE  = 'background:#e8f5e9;color:#1b5e20;';       // grade section
		var C_STATUS = 'background:#fff8e1;color:#795548;';       // overall status
		var C_REEXAM = 'background:#fce4ec;color:#880e4f;';       // re-exam
		var C_FINAL  = 'background:#e8eaf6;color:#1a237e;';       // final result

		// ── Header row 1: section-level group headers ────────────────────────────
		var th1 = '';
		groups.forEach(function (g) {
			th1 += '<th colspan="' + (g.cols.length * 3) + '" class="type-hdr" style="text-align:center;' + C_COMP + '">' +
				frappe.utils.escape_html(g.component_name) + '</th>';
		});
		// Total + Grade + Moderated Grade (span 3)
		th1 += '<th colspan="3" class="type-hdr" style="text-align:center;' + C_GRADE + '">Grade</th>';
		// Overall Status (span 5)
		th1 += '<th colspan="5" class="type-hdr" style="text-align:center;' + C_STATUS + '">Overall Status</th>';
		// Re-Exam groups
		rxgroups.forEach(function (g) {
			th1 += '<th colspan="' + (g.cols.length * 2) + '" class="type-hdr" style="text-align:center;' + C_REEXAM + '">' +
				frappe.utils.escape_html(g.component_name) + ' (Re-Exam)</th>';
		});
		// Updated Final Result (span 2)
		th1 += '<th colspan="2" class="type-hdr" style="text-align:center;' + C_FINAL + '">Updated Final Result</th>';

		// ── Header row 2: assessment labels + max marks ──────────────────────────
		var th2 = '';
		groups.forEach(function (g) {
			g.cols.forEach(function (col) {
				var lbl = frappe.utils.escape_html(col.label || col.type_name || col.assessment_type || '');
				var max = col.maximum_marks ? 'Max. ' + parseFloat(col.maximum_marks).toFixed(2) : '';
				var sync_btn = (col.enrollment === 'Auto')
					? '<br><button class="er2-sync-btn er2-sync-comp" data-comp="' + frappe.utils.escape_html(col.component || '') + '">Sync Marks</button>'
					: '';
				th2 += '<th colspan="3" class="type-hdr" style="text-align:center;">' +
					lbl +
					(max ? '<br><span style="font-size:10px;color:#6c757d;font-weight:400;">' + max + '</span>' : '') +
					sync_btn + '</th>';
			});
		});
		// Grade section row 2 labels
		th2 += '<th style="font-size:11px;color:#6c757d;min-width:60px;">Total<br>Marks</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:60px;">Grade</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:80px;">Moderated<br>Grade</th>';
		// Overall Status row 2 labels
		th2 += '<th style="font-size:11px;color:#6c757d;min-width:90px;">Enrollment<br>Status</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:90px;">Attendance<br>Status</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:80px;">Fairness<br>Status</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:60px;">SGPA</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:100px;">Remark</th>';
		// Re-Exam row 2 labels
		rxgroups.forEach(function (g) {
			g.cols.forEach(function (col) {
				var lbl = frappe.utils.escape_html(col.label || col.type_name || col.assessment_type || '');
				var max = col.maximum_marks ? 'Max. ' + parseFloat(col.maximum_marks).toFixed(2) : '';
				th2 += '<th colspan="2" class="type-hdr" style="text-align:center;">' +
					lbl + (max ? '<br><span style="font-size:10px;color:#6c757d;font-weight:400;">' + max + '</span>' : '') + '</th>';
			});
		});
		// Updated Final Result row 2 labels
		th2 += '<th style="font-size:11px;color:#6c757d;min-width:80px;">Updated<br>Final Marks</th>' +
			'<th style="font-size:11px;color:#6c757d;min-width:70px;">Updated<br>Grade</th>';

		// ── Header row 3: sub-column labels ──────────────────────────────────────
		var th3 = '';
		cols.forEach(function () {
			th3 += '<th style="font-size:11px;color:#6c757d;min-width:70px;">Marks</th>' +
				'<th style="font-size:11px;color:#6c757d;min-width:80px;">Revaluation<br>Marks</th>' +
				'<th style="font-size:11px;color:#6c757d;min-width:80px;">Moderated<br>Marks <span style="color:#e63946;cursor:pointer;font-size:10px;" title="Reset">&#9673;</span></th>';
		});
		// Grade section row 3 (empty — already set in row 2)
		th3 += '<th></th><th></th><th></th>';
		// Overall Status row 3 (empty)
		th3 += '<th></th><th></th><th></th><th></th><th></th>';
		// Re-Exam sub-column labels
		reexam_cols.forEach(function () {
			th3 += '<th style="font-size:11px;color:#6c757d;min-width:70px;">Marks</th>' +
				'<th style="font-size:11px;color:#6c757d;min-width:80px;">Revaluation<br>Marks</th>';
		});
		// Updated Final Result row 3 (empty)
		th3 += '<th></th><th></th>';

		// ── Data rows ─────────────────────────────────────────────────────────────
		var rows = '';
		S.students.forEach(function (s) {
			var sm      = S.marks[s.student] || {};
			var entries = sm.entries || {};
			var total   = sm.total   != null ? parseFloat(sm.total).toFixed(2) : '—';
			var cells   = '';

			// Regular assessment cells
			cols.forEach(function (col) {
				var key = (col.component || '') + '|' + (col.assessment_type || '');
				var e   = entries[key] || {};
				var m   = e.marks             != null ? parseFloat(e.marks).toFixed(2)             : '--';
				var rv  = e.revaluation_marks  != null ? parseFloat(e.revaluation_marks).toFixed(2) : '--';
				var mo  = e.moderated_marks    != null ? parseFloat(e.moderated_marks).toFixed(2)   : '--';
				cells += '<td>' + m + '</td><td>' + rv + '</td><td>' + mo + '</td>';
			});

			// Grade section
			cells += '<td style="font-weight:700;">' + total + '</td>' +
				'<td style="font-weight:600;color:#1b5e20;">' + frappe.utils.escape_html(sm.grade || '—') + '</td>' +
				'<td>' + frappe.utils.escape_html(sm.moderated_grade || '—') + '</td>';

			// Overall Status
			var es  = sm.enrollment_status  || '—';
			var at  = sm.attendance_status  || '—';
			var fs  = sm.fairness_status    || '—';
			var sg  = sm.consider_for_sgpa  ? '<span style="color:#28a745;font-weight:700;">&#10003;</span>' : '—';
			var rmk = sm.remark || '';
			cells += '<td>' + frappe.utils.escape_html(es) + '</td>' +
				'<td>' + frappe.utils.escape_html(at) + '</td>' +
				'<td>' + frappe.utils.escape_html(fs) + '</td>' +
				'<td style="text-align:center;">' + sg + '</td>' +
				'<td style="text-align:left;max-width:120px;">' + frappe.utils.escape_html(rmk) + '</td>';

			// Re-Exam cells
			reexam_cols.forEach(function (col) {
				var key = (col.component || '') + '|' + (col.assessment_type || '');
				var e   = entries[key] || {};
				var m   = e.marks            != null ? parseFloat(e.marks).toFixed(2)             : '--';
				var rv  = e.revaluation_marks != null ? parseFloat(e.revaluation_marks).toFixed(2) : '--';
				cells += '<td>' + m + '</td><td>' + rv + '</td>';
			});

			// Updated Final Result
			var ufm = sm.updated_final_marks != null ? parseFloat(sm.updated_final_marks).toFixed(2) : '—';
			var ug  = sm.updated_grade || '—';
			cells += '<td style="font-weight:700;">' + frappe.utils.escape_html(ufm) + '</td>' +
				'<td style="font-weight:600;color:#1a237e;">' + frappe.utils.escape_html(ug) + '</td>';

			rows += '<tr class="er2-mrow" data-student="' + frappe.utils.escape_html(s.student) + '">' + cells + '</tr>';
		});

		if (!rows) {
			rows = '<tr><td colspan="' + total_cols + '" style="text-align:center;padding:40px;color:#adb5bd;">No students found.</td></tr>';
		}

		$mtable.html(
			'<table class="er2-rtable">' +
			'<thead>' +
			'<tr>' + th1 + '</tr>' +
			'<tr style="background:#fafbfc;">' + th2 + '</tr>' +
			'<tr style="background:#f4f5f7;">' + th3 + '</tr>' +
			'</thead>' +
			'<tbody>' + rows + '</tbody>' +
			'</table>'
		);

		$mtable.find('.er2-sync-comp').on('click', function () {
			frappe.msgprint('Sync Marks for this component — coming soon.');
		});
	}

	function update_pagination() {
		var from = S.total ? (S.page - 1) * S.page_length + 1 : 0;
		var to   = Math.min(S.page * S.page_length, S.total);
		$pagInfo.text(S.total ? (from + '–' + to + ' of ' + S.total) : '0 students');
		$prevBtn.prop('disabled', S.page <= 1);
		$nextBtn.prop('disabled', to >= S.total);
	}

	// ── Hover popup ───────────────────────────────────────────────────────────
	function bind_hover() {
		$slist.find('.er2-srow')
			.on('mouseenter', function (e) {
				var student = $(this).data('student');
				clearTimeout(S.popup_timer);
				S.popup_student = student;
				S.popup_timer = setTimeout(function () {
					show_popup(student, e.clientX, e.clientY);
				}, 300);
			})
			.on('mouseleave', function () {
				clearTimeout(S.popup_timer);
				$popup.hide();
			})
			.on('mousemove', function (e) {
				position_popup(e.clientX, e.clientY);
			});
	}

	function position_popup(x, y) {
		var pw = 300;
		var left = (x + pw + 20 > window.innerWidth) ? x - pw - 10 : x + 16;
		$popup.css({ top: y + 8, left: left });
	}

	function show_popup(student, x, y) {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_student_hover_info',
			args: { student: student, course: S.course },
			callback: function (r) {
				var s = r.message || {};
				if (S.popup_student !== student) return; // stale

				function prow(lbl, val, always) {
					if (!always && !val && val !== 0) return '';
					var display = (val || val === 0) ? frappe.utils.escape_html(String(val)) : '—';
					return '<div class="er2-pop-row"><span class="er2-pop-lbl">' + lbl + ' :</span>' +
						'<span class="er2-pop-val">' + display + '</span></div>';
				}
				$popup.html(
					'<div class="er2-pop-name">' + frappe.utils.escape_html(s.student_name || student) + '</div>' +
					prow('Student ID',  s.registration_id, true) +
					prow('Email ID',    s.email) +
					prow('Programme',   s.programme) +
					prow('Batch',       s.batch, true) +
					prow('Intake',      s.intake) +
					prow('Section',     s.section, true)
				);
				position_popup(x, y);
				$popup.show();
			},
		});
	}

	// ── Popup dialogs ────────────────────────────────────────────────────────
	function show_calc_settings_popup(evaluation_schema) {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_calc_settings',
			args: { evaluation_schema: evaluation_schema },
			callback: function (r) {
				var s = r.message || {};
				var d = new frappe.ui.Dialog({
					title: 'Calculation Settings',
					fields: [
						{
							fieldname: 'calc_higher_revaluation',
							fieldtype: 'Check',
							label: 'Consider higher marks for an assessment between regular marks and revaluation marks',
							default: s.calc_higher_revaluation || 0,
						},
						{
							fieldname: 'calc_higher_makeup',
							fieldtype: 'Check',
							label: 'Consider higher marks for an assessment or component between regular evaluation marks and MakeUp Exams',
							default: s.calc_higher_makeup || 0,
						},
						{
							fieldname: 'calc_higher_reexam',
							fieldtype: 'Check',
							label: 'Consider higher marks for an assessment or component between regular evaluation marks and Re-Exam',
							default: s.calc_higher_reexam || 0,
						},
					],
					primary_action_label: 'Save',
					primary_action: function () {
						var vals = d.get_values();
						frappe.call({
							method: 'slcm.slcm.page.examination_result.examination_result.save_calc_settings',
							args: {
								evaluation_schema:     evaluation_schema,
								calc_higher_revaluation: vals.calc_higher_revaluation ? 1 : 0,
								calc_higher_makeup:    vals.calc_higher_makeup ? 1 : 0,
								calc_higher_reexam:    vals.calc_higher_reexam ? 1 : 0,
							},
							callback: function () {
								d.hide();
								frappe.show_alert({ message: 'Calculation settings saved.', indicator: 'green' });
							},
						});
					},
				});
				d.show();
			},
		});
	}

	function show_eval_schema_popup(name) {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_evaluation_schema_details',
			args: { name: name },
			callback: function (r) {
				var s = r.message || {};
				var html = '<div style="font-size:13px;">';
				html += '<div style="margin-bottom:12px;"><b>' + frappe.utils.escape_html(s.schema_name || name) + '</b>';
				if (s.description) html += '<div style="color:#6c757d;margin-top:4px;">' + frappe.utils.escape_html(s.description) + '</div>';
				html += '</div>';
				html += '<div style="display:flex;gap:24px;margin-bottom:14px;">' +
					'<div><span style="color:#8d99ae;font-size:11px;text-transform:uppercase;">Total Marks</span><div style="font-size:15px;font-weight:700;">' + (s.total_marks || 0) + '</div></div>' +
					'<div><span style="color:#8d99ae;font-size:11px;text-transform:uppercase;">Passing Marks</span><div style="font-size:15px;font-weight:700;">' + (s.passing_marks || 0) + '</div></div>' +
					'</div>';
				if (s.components && s.components.length) {
					html += '<div style="font-weight:600;margin-bottom:6px;color:#333;font-size:12px;">Components</div>' +
						'<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:14px;">' +
						'<thead><tr style="background:#f0f2f5;">' +
						'<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6;">Component</th>' +
						'<th style="padding:6px 8px;text-align:right;border:1px solid #dee2e6;">Max Marks</th>' +
						'<th style="padding:6px 8px;text-align:right;border:1px solid #dee2e6;">Weightage</th>' +
						'<th style="padding:6px 8px;text-align:right;border:1px solid #dee2e6;">Passing</th>' +
						'</tr></thead><tbody>';
					(s.components || []).forEach(function (c) {
						html += '<tr>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;">' + frappe.utils.escape_html(c.component_name || c.component) + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:right;">' + (c.effective_max_marks || '—') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:right;">' + (c.weightage != null ? c.weightage + '%' : '—') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:right;">' + (c.passing_marks || '—') + '</td>' +
							'</tr>';
					});
					html += '</tbody></table>';
				}
				if (s.assessments && s.assessments.length) {
					html += '<div style="font-weight:600;margin-bottom:6px;color:#333;font-size:12px;">Assessment Configuration</div>' +
						'<table style="width:100%;border-collapse:collapse;font-size:12px;">' +
						'<thead><tr style="background:#f0f2f5;">' +
						'<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6;">Component</th>' +
						'<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6;">Assessment Type</th>' +
						'<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6;">Label</th>' +
						'<th style="padding:6px 8px;text-align:right;border:1px solid #dee2e6;">Max Marks</th>' +
						'<th style="padding:6px 8px;text-align:right;border:1px solid #dee2e6;">Effective</th>' +
						'<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6;">Enrollment</th>' +
						'</tr></thead><tbody>';
					(s.assessments || []).forEach(function (a) {
						html += '<tr>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;">' + frappe.utils.escape_html(a.component_name || a.component || '') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;">' + frappe.utils.escape_html(a.type_name || a.assessment_type || '') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;">' + frappe.utils.escape_html(a.label || '') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:right;">' + (a.maximum_marks || '—') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:right;">' + (a.effective_marks || '—') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:center;">' + frappe.utils.escape_html(a.enrollment || '') + '</td>' +
							'</tr>';
					});
					html += '</tbody></table>';
				}
				html += '</div>';
				var d = new frappe.ui.Dialog({
					title: 'Evaluation Schema: ' + frappe.utils.escape_html(name),
					fields: [{ fieldname: 'schema_html', fieldtype: 'HTML', options: html }],
				});
				d.show();
			},
		});
	}

	function show_grade_schema_popup(name) {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_grading_schema_details',
			args: { name: name },
			callback: function (r) {
				var s = r.message || {};
				var html = '<div style="font-size:13px;">';
				html += '<div style="margin-bottom:12px;"><b>' + frappe.utils.escape_html(s.schema_name || name) + '</b>';
				if (s.description) html += '<div style="color:#6c757d;margin-top:4px;">' + frappe.utils.escape_html(s.description) + '</div>';
				html += '</div>';
				html += '<div style="display:flex;gap:24px;margin-bottom:14px;">' +
					'<div><span style="color:#8d99ae;font-size:11px;text-transform:uppercase;">Max Marks</span><div style="font-size:15px;font-weight:700;">' + (s.maximum_marks || 0) + '</div></div>' +
					'<div><span style="color:#8d99ae;font-size:11px;text-transform:uppercase;">Type</span><div style="font-size:15px;font-weight:700;">' + frappe.utils.escape_html(s.grading_type || '') + '</div></div>' +
					'</div>';
				if (s.grades && s.grades.length) {
					html += '<table style="width:100%;border-collapse:collapse;font-size:12px;">' +
						'<thead><tr style="background:#f0f2f5;">' +
						'<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6;">Grade</th>' +
						'<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6;">Meaning</th>' +
						'<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6;">Range</th>' +
						'<th style="padding:6px 8px;text-align:right;border:1px solid #dee2e6;">Grade Point</th>' +
						'<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6;">Failed</th>' +
						'<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6;">For SGPA</th>' +
						'</tr></thead><tbody>';
					(s.grades || []).forEach(function (g) {
						var range      = (g.from_operator || '>=') + ' ' + (g.marks_from || 0) + ' &amp; ' + (g.to_operator || '<') + ' ' + (g.marks_to || 0);
						var failedBadge = g.failed ? '<span style="color:#dc3545;font-weight:600;">Yes</span>' : '<span style="color:#28a745;">No</span>';
						var sgpaBadge   = g.consider_for_sgpa ? '<span style="color:#28a745;">Yes</span>' : '<span style="color:#6c757d;">No</span>';
						html += '<tr>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;font-weight:700;">' + frappe.utils.escape_html(g.grade || '') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;">' + frappe.utils.escape_html(g.qualitative_meaning || '') + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:center;">' + range + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:right;">' + (g.grade_point || 0) + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:center;">' + failedBadge + '</td>' +
							'<td style="padding:5px 8px;border:1px solid #dee2e6;text-align:center;">' + sgpaBadge + '</td>' +
							'</tr>';
					});
					html += '</tbody></table>';
				}
				html += '</div>';
				var d = new frappe.ui.Dialog({
					title: 'Grading Schema: ' + frappe.utils.escape_html(name),
					fields: [{ fieldname: 'schema_html', fieldtype: 'HTML', options: html }],
				});
				d.show();
			},
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────
	function hide_detail() {
		$info.hide().empty();
		$actbar.hide();
		$filterrow.hide();
		$split.hide();
		$popup.hide();
		$empty.show();
		S.students        = [];
		S.marks           = {};
		S.info            = null;
		S.columns         = [];
		S.reexam_columns  = [];
	}

	// Close popup on outside click
	$(document).on('click.er2popup', function (e) {
		if (!$(e.target).closest('.er2-srow, #er2-popup').length) {
			$popup.hide();
		}
	});
};
