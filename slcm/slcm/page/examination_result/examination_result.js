frappe.pages['examination-result'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Examination Result',
		single_column: true,
	});

	// ── State ─────────────────────────────────────────────────────────────────
	var S = {
		exam_plan:       null,
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
		show_status:     false,  // view/hide student assessment status columns
		selected_all:    false,  // select all across pages
		status_filter:   '',     // student status filter
		grade_filter:    '',     // grade drilldown filter
		pass_filter:     '',     // pass/fail/graded/not_graded filter
		inst_filter:     { programmes: [], batches: [], course_types: [] },
		inst_options:    null,   // cached filter options from backend
	};

	// ── CSS ───────────────────────────────────────────────────────────────────
	if (!document.getElementById('er2-style')) {
		var style = document.createElement('style');
		style.id  = 'er2-style';
		style.textContent = `
		/* ── Base ── */
		.er2-wrap { font-family: var(--font-stack,'Inter',sans-serif); padding:0; background:#f1f5f9; min-height:100vh; }

		/* ── Tabs ── */
		.er2-tabs { display:flex; gap:4px; margin-bottom:18px;
		            background:#e2e8f0; border-radius:10px; padding:4px; width:fit-content; }
		.er2-tab  { padding:8px 20px; cursor:pointer; font-size:13px; font-weight:600;
		            color:#64748b; border-radius:7px; transition:all .2s;
		            user-select:none; letter-spacing:.1px; }
		.er2-tab:hover { color:#4f46e5; background:rgba(79,70,229,.08); }
		.er2-tab.active { background:#fff; color:#4f46e5;
		                  box-shadow:0 1px 4px rgba(0,0,0,.12); }

		/* ── Top filter card ── */
		.er2-filter-card { background:#fff; border-radius:12px; padding:16px 20px;
		                   margin-bottom:16px; display:flex; gap:14px; align-items:flex-end;
		                   box-shadow:0 1px 3px rgba(0,0,0,.06); flex-wrap:wrap; }
		.er2-fgroup  { display:flex; flex-direction:column; min-width:200px; flex:1; max-width:300px; }
		.er2-flabel  { font-size:11px; color:#94a3b8; font-weight:600; margin-bottom:5px;
		               text-transform:uppercase; letter-spacing:.6px; }
		.er2-select  { height:36px; border:1.5px solid #e2e8f0; border-radius:8px;
		               padding:0 12px; font-size:13px; background:#fff; color:#1e293b;
		               outline:none; cursor:pointer; transition:border-color .2s; }
		.er2-select:focus { border-color:#4f46e5; box-shadow:0 0 0 3px rgba(79,70,229,.1); }

		/* ── Info panel (stat cards) ── */
		.er2-info    { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
		.er2-icard   { background:#fff; border-radius:12px; padding:14px 18px; flex:1;
		               min-width:160px; box-shadow:0 1px 3px rgba(0,0,0,.06);
		               border-top:3px solid #4f46e5; position:relative; overflow:hidden; }
		.er2-icard::after { content:''; position:absolute; right:-12px; top:-12px;
		                    width:60px; height:60px; border-radius:50%;
		                    background:rgba(79,70,229,.05); }
		.er2-icard.teal  { border-top-color:#0ea5e9; }
		.er2-icard.teal::after  { background:rgba(14,165,233,.05); }
		.er2-icard.green { border-top-color:#10b981; }
		.er2-icard.green::after { background:rgba(16,185,129,.05); }
		.er2-icard.amber { border-top-color:#f59e0b; }
		.er2-icard.amber::after { background:rgba(245,158,11,.05); }
		.er2-icard.rose  { border-top-color:#ef4444; }
		.er2-icard.rose::after  { background:rgba(239,68,68,.05); }
		.er2-icard.slate { border-top-color:#64748b; }
		.er2-icard.slate::after { background:rgba(100,116,139,.05); }
		.er2-icard.violet{ border-top-color:#7c3aed; }
		.er2-icard.violet::after{ background:rgba(124,58,237,.05); }
		.er2-ilabel  { font-size:10px; color:#94a3b8; text-transform:uppercase;
		               letter-spacing:.7px; font-weight:700; margin-bottom:5px; }
		.er2-ival    { font-size:13px; color:#1e293b; font-weight:600; line-height:1.4; }
		.er2-ival a  { color:#4f46e5; text-decoration:none; border-bottom:1px dashed #c7d2fe; }
		.er2-ival a:hover { color:#3730a3; }
		.er2-ival.green { color:#059669; }
		.er2-ival.orange { color:#d97706; }
		.er2-irow    { display:flex; flex-direction:column; gap:2px; }

		/* ── Action bar ── */
		.er2-actbar  { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
		               margin-bottom:12px; background:#fff; border-radius:10px;
		               padding:10px 14px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
		.er2-srch    { flex:1; min-width:200px; max-width:320px; position:relative; }
		.er2-srch input { width:100%; height:34px; border:1.5px solid #e2e8f0; border-radius:20px;
		                  padding:0 14px 0 36px; font-size:13px; outline:none; color:#1e293b;
		                  background:#f8fafc; transition:border-color .2s, background .2s; }
		.er2-srch input:focus { border-color:#4f46e5; background:#fff;
		                        box-shadow:0 0 0 3px rgba(79,70,229,.1); }
		.er2-srch-ico { position:absolute; left:11px; top:9px; color:#94a3b8; }

		/* ── Buttons ── */
		.er2-btn     { height:34px; padding:0 14px; border-radius:7px; border:1.5px solid #e2e8f0;
		               background:#fff; cursor:pointer; font-size:12.5px; font-weight:600;
		               color:#475569; display:inline-flex; align-items:center; gap:5px;
		               white-space:nowrap; transition:all .15s; }
		.er2-btn:hover { background:#f8fafc; border-color:#cbd5e1; color:#1e293b; }
		.er2-btn.primary { background:linear-gradient(135deg,#4f46e5,#6366f1);
		                   border-color:transparent; color:#fff; }
		.er2-btn.primary:hover { background:linear-gradient(135deg,#4338ca,#4f46e5); }
		.er2-btn.outline-red { border-color:#fca5a5; color:#ef4444; background:#fff5f5; }
		.er2-btn.outline-red:hover { background:#fee2e2; border-color:#f87171; }
		.er2-btn.outline-indigo { border-color:#c7d2fe; color:#4f46e5; background:#eef2ff; }
		.er2-btn.outline-indigo:hover { background:#e0e7ff; }

		/* ── Dropdowns ── */
		.er2-btn-dd  { position:relative; display:inline-flex; }
		.er2-btn-dd .dd-menu { display:none; position:absolute; top:100%; left:0; z-index:999;
		                       background:#fff; border:1.5px solid #e2e8f0; border-radius:9px;
		                       box-shadow:0 8px 24px rgba(0,0,0,.12); min-width:170px;
		                       padding:5px; margin-top:4px; }
		.er2-btn-dd:hover .dd-menu,
		.er2-btn-dd.open .dd-menu { display:block; }
		.dd-item { padding:8px 12px; font-size:12.5px; cursor:pointer; color:#475569;
		           border-radius:6px; font-weight:500; }
		.dd-item:hover { background:#f1f5f9; color:#1e293b; }
		.dd-item + .dd-item { margin-top:1px; }

		/* ── Filter row ── */
		.er2-filterrow { display:flex; align-items:center; gap:8px; margin-bottom:12px;
		                 background:#fff; border-radius:10px; padding:8px 14px;
		                 box-shadow:0 1px 3px rgba(0,0,0,.06); }
		.er2-pag     { display:flex; align-items:center; gap:6px;
		               font-size:12.5px; color:#64748b; }
		.er2-paglen-wrap { display:flex; align-items:center; gap:6px; font-size:12px; color:#64748b; margin-left:auto; }
		.er2-paglen-wrap label { font-weight:600; white-space:nowrap; }
		.er2-paglen  { height:30px; border:1.5px solid #e2e8f0; border-radius:7px;
		               padding:0 8px; font-size:12px; background:#fff; color:#1e293b;
		               outline:none; cursor:pointer; transition:border-color .2s; }
		.er2-paglen:focus { border-color:#4f46e5; box-shadow:0 0 0 3px rgba(79,70,229,.1); }
		.er2-paglen-info { font-size:12px; font-weight:600; color:#475569; white-space:nowrap; padding:0 4px; }
		.er2-pag-btn { width:28px; height:28px; border:1.5px solid #e2e8f0; border-radius:7px;
		               background:#fff; cursor:pointer; font-size:14px; display:inline-flex;
		               align-items:center; justify-content:center; color:#64748b;
		               transition:all .15s; }
		.er2-pag-btn:hover:not(:disabled) { background:#eef2ff; border-color:#c7d2fe; color:#4f46e5; }
		.er2-pag-btn:disabled { opacity:.35; cursor:default; }

		/* ── Split panel ── */
		.er2-split   { display:flex; gap:0; border-radius:12px; overflow:hidden;
		               background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.08); }
		.er2-left    { width:320px; flex-shrink:0; overflow-y:auto; overflow-x:hidden;
		               border-right:1.5px solid #f1f5f9; }
		.er2-left.collapsed { width:0; border-right:none; }
		.er2-right   { flex:1; overflow:auto; min-width:0; }

		/* ── Left panel header ── */
		.er2-lhdr    { display:flex; align-items:center; gap:8px; padding:11px 13px;
		               background:linear-gradient(135deg,#4f46e5 0%,#6366f1 100%);
		               border-bottom:none; position:sticky; top:0; z-index:10; }
		.er2-lhdr-title { font-size:13px; font-weight:700; color:#fff; flex:1; }
		.er2-lhdr input[type="checkbox"] { accent-color:#fff; width:14px; height:14px; cursor:pointer; }
		.er2-sort-btn { font-size:11px; color:rgba(255,255,255,.85); cursor:pointer; background:none;
		                border:1px solid rgba(255,255,255,.3); border-radius:5px; padding:3px 7px;
		                display:flex; align-items:center; gap:3px; transition:all .15s; }
		.er2-sort-btn:hover { background:rgba(255,255,255,.15); color:#fff; }

		/* ── Student status filter bar ── */
		.er2-status-bar { padding:6px 12px; background:#f8fafc; border-bottom:1.5px solid #f1f5f9;
		                  display:flex; align-items:center; gap:6px; }

		/* ── Student row ── */
		.er2-srow    { display:flex; align-items:center; gap:10px; padding:0 13px;
		               height:64px; min-height:64px; flex-shrink:0; box-sizing:border-box;
		               border-bottom:1.5px solid #f8fafc; cursor:pointer; transition:background .15s; }
		.er2-srow:hover { background:#f8fafc; }
		.er2-srow.selected { background:#eef2ff; }
		.er2-savatar { width:38px; height:38px; border-radius:10px; flex-shrink:0;
		               display:flex; align-items:center; justify-content:center;
		               font-size:15px; font-weight:700; color:#fff; overflow:hidden; }
		.er2-savatar img { width:100%; height:100%; object-fit:cover; }
		.er2-sinfo   { flex:1; min-width:0; }
		.er2-sname   { font-size:13px; font-weight:700; color:#1e293b; white-space:nowrap;
		               overflow:hidden; text-overflow:ellipsis; }
		.er2-sreg    { font-size:11px; color:#94a3b8; margin-top:1px; font-weight:500; }
		.er2-sbadges { display:flex; gap:4px; margin-top:4px; flex-wrap:wrap; }
		.er2-badge   { font-size:10px; font-weight:700; padding:2px 8px; border-radius:20px;
		               letter-spacing:.2px; }
		.er2-badge.active   { background:#d1fae5; color:#065f46; }
		.er2-badge.inactive { background:#fee2e2; color:#991b1b; }
		.er2-badge.blocked  { background:#fee2e2; color:#991b1b; }
		.er2-badge.regular  { background:#e0e7ff; color:#3730a3; }
		.er2-badge.dropped  { background:#fef3c7; color:#92400e; }

		/* ── Marks table ── */
		.er2-rtable  { border-collapse:collapse; min-width:100%; font-size:12px; }
		.er2-rtable th, .er2-rtable td { padding:7px 11px; border-right:1px solid #f1f5f9;
		                                  white-space:nowrap; }
		.er2-rtable th { background:#f8fafc; position:sticky; top:0; z-index:5;
		                 font-weight:700; color:#475569; text-align:center;
		                 border-bottom:1.5px solid #e2e8f0; font-size:11px;
		                 letter-spacing:.2px; }
		.er2-rtable th.type-hdr { font-size:12px; font-weight:700; letter-spacing:.3px;
		                          border-bottom:2px solid rgba(0,0,0,.08); }
		.er2-rtable td { text-align:center; color:#334155; border-bottom:1.5px solid #f1f5f9; vertical-align:middle; }
		.er2-rtable tbody tr:hover td { background:#fafbff; }
		.er2-rtable tbody tr:nth-child(even) td { background:#fafcff; }
		.er2-rtable tbody tr:nth-child(even):hover td { background:#f0f4ff; }
		.er2-mrow    { height:64px; max-height:64px; }

		/* ── Collapse button ── */
		.er2-collapse-btn { width:18px; cursor:pointer; display:flex; align-items:center;
		                    justify-content:center; background:#f1f5f9; border:none;
		                    border-left:1.5px solid #e2e8f0; color:#94a3b8; font-size:12px;
		                    align-self:stretch; flex-shrink:0; transition:all .15s; }
		.er2-collapse-btn:hover { background:#e0e7ff; color:#4f46e5; }

		/* ── Hover popup ── */
		#er2-popup   { display:none; position:fixed; z-index:9999; background:#fff;
		               border:1.5px solid #e2e8f0; border-radius:14px;
		               box-shadow:0 16px 40px rgba(0,0,0,.16); padding:0;
		               min-width:310px; max-width:400px; pointer-events:none;
		               overflow:hidden; }
		.er2-pop-head { background:linear-gradient(135deg,#4f46e5,#6366f1); padding:14px 16px; }
		.er2-pop-name { font-size:14px; font-weight:700; color:#fff; }
		.er2-pop-sub  { font-size:11px; color:rgba(255,255,255,.75); margin-top:2px; font-weight:500; }
		.er2-pop-body { padding:12px 16px; }
		.er2-pop-row  { display:flex; gap:8px; margin-bottom:5px; font-size:12.5px; }
		.er2-pop-lbl  { color:#94a3b8; min-width:95px; font-weight:600; flex-shrink:0;
		                font-size:11px; text-transform:uppercase; letter-spacing:.4px; }
		.er2-pop-val  { color:#1e293b; font-weight:600; }
		.er2-pop-divider { border:none; border-top:1.5px solid #f1f5f9; margin:10px 0; }
		.er2-pop-marks-title { font-size:10.5px; font-weight:700; color:#94a3b8; text-transform:uppercase;
		                       letter-spacing:.5px; margin-bottom:8px; }
		.er2-pop-marks-grid { display:flex; flex-wrap:wrap; gap:6px; }
		.er2-pop-mark-chip  { background:#f8fafc; border:1.5px solid #e2e8f0; border-radius:8px;
		                      padding:5px 10px; font-size:11.5px; min-width:80px; text-align:center; }
		.er2-pop-mark-chip .chip-lbl { color:#64748b; font-size:10px; font-weight:600;
		                               text-transform:uppercase; letter-spacing:.3px; display:block; }
		.er2-pop-mark-chip .chip-val { color:#1e293b; font-size:13px; font-weight:700;
		                               display:block; margin-top:2px; }
		.er2-pop-total-row { display:flex; justify-content:space-between; align-items:center;
		                     background:#eef2ff; border-radius:8px; padding:8px 12px; margin-top:8px; }
		.er2-pop-total-lbl { font-size:11px; color:#4f46e5; font-weight:700;
		                     text-transform:uppercase; letter-spacing:.4px; }
		.er2-pop-total-val { font-size:18px; font-weight:800; color:#4f46e5; }
		.er2-pop-grade-badge { background:#4f46e5; color:#fff; font-size:11px; font-weight:700;
		                       padding:2px 10px; border-radius:20px; margin-left:8px; }

		/* ── Sync btn ── */
		.er2-sync-btn { font-size:10px; background:linear-gradient(135deg,#4f46e5,#6366f1);
		                color:#fff; border:none; border-radius:5px; padding:3px 8px;
		                cursor:pointer; margin-top:3px; font-weight:600; }
		.er2-sync-btn:hover { background:linear-gradient(135deg,#4338ca,#4f46e5); }

		/* ── Toggle wrap ── */
		.er2-toggle-wrap { display:flex; align-items:center; gap:8px; padding:8px 13px;
		                   background:#f8fafc; border-bottom:1.5px solid #f1f5f9;
		                   position:sticky; top:0; z-index:10; }
		.er2-toggle-lbl { font-size:12px; font-weight:600; color:#475569; }
		.er2-toggle  { position:relative; width:36px; height:20px; }
		.er2-toggle input { opacity:0; width:0; height:0; }
		.er2-slider  { position:absolute; inset:0; border-radius:20px; background:#cbd5e1;
		               cursor:pointer; transition:background .2s; }
		.er2-slider:before { content:''; position:absolute; width:14px; height:14px;
		                     left:3px; top:3px; border-radius:50%; background:#fff;
		                     transition:transform .2s;
		                     box-shadow:0 1px 3px rgba(0,0,0,.2); }
		.er2-toggle input:checked + .er2-slider { background:#4f46e5; }
		.er2-toggle input:checked + .er2-slider:before { transform:translateX(16px); }

		/* ── Empty state ── */
		.er2-empty   { display:flex; flex-direction:column; align-items:center;
		               justify-content:center; padding:80px 20px; color:#cbd5e1; }
		.er2-empty svg { width:80px; height:80px; margin-bottom:20px; }
		.er2-empty-txt { font-size:15px; font-weight:600; color:#94a3b8; }
		.er2-empty-sub { font-size:12.5px; color:#cbd5e1; margin-top:6px; }

		/* ── Avatar colour palette ── */
		.av-0{background:linear-gradient(135deg,#4f46e5,#818cf8);}
		.av-1{background:linear-gradient(135deg,#0ea5e9,#38bdf8);}
		.av-2{background:linear-gradient(135deg,#10b981,#34d399);}
		.av-3{background:linear-gradient(135deg,#f59e0b,#fbbf24);}
		.av-4{background:linear-gradient(135deg,#ef4444,#f87171);}
		.av-5{background:linear-gradient(135deg,#8b5cf6,#a78bfa);}
		.av-6{background:linear-gradient(135deg,#ec4899,#f472b6);}
		.av-7{background:linear-gradient(135deg,#14b8a6,#2dd4bf);}

		/* ── Institutional Filter Modal ── */
		.xif-overlay { position:fixed; inset:0; background:rgba(15,23,42,.35);
		               z-index:10000; display:flex; align-items:center; justify-content:center;
		               backdrop-filter:blur(2px); }
		.xif-modal   { background:#fff; border-radius:14px; width:660px; max-width:95vw;
		               max-height:85vh; display:flex; flex-direction:column;
		               box-shadow:0 20px 60px rgba(0,0,0,.18); overflow:hidden; }
		.xif-header  { display:flex; align-items:center; justify-content:space-between;
		               padding:16px 20px; border-bottom:1.5px solid #f1f5f9; }
		.xif-title   { font-size:15px; font-weight:700; color:#0f172a; }
		.xif-close   { width:30px; height:30px; border-radius:8px; border:none;
		               background:#f1f5f9; cursor:pointer; display:flex;
		               align-items:center; justify-content:center; color:#64748b;
		               font-size:16px; transition:all .15s; }
		.xif-close:hover { background:#fee2e2; color:#ef4444; }
		.xif-body    { display:flex; flex:1; overflow:hidden; }
		.xif-types   { width:190px; flex-shrink:0; border-right:1.5px solid #f1f5f9;
		               padding:8px; background:#fafbff; }
		.xif-type    { padding:10px 14px; border-radius:8px; font-size:13px; font-weight:600;
		               color:#475569; cursor:pointer; margin-bottom:2px;
		               transition:all .15s; display:flex; align-items:center; gap:8px; }
		.xif-type:hover { background:#f1f5f9; color:#1e293b; }
		.xif-type.active { background:#eef2ff; color:#4f46e5; }
		.xif-type-badge { min-width:18px; height:18px; border-radius:20px;
		                  background:#4f46e5; color:#fff; font-size:10px; font-weight:700;
		                  display:inline-flex; align-items:center; justify-content:center;
		                  padding:0 5px; margin-left:auto; }
		.xif-panel   { flex:1; display:flex; flex-direction:column; overflow:hidden; }
		.xif-ph      { padding:14px 16px 8px; border-bottom:1.5px solid #f1f5f9; }
		.xif-ph-title{ font-size:13px; font-weight:700; color:#1e293b; margin-bottom:8px; }
		.xif-search  { width:100%; height:32px; border:1.5px solid #e2e8f0; border-radius:8px;
		               padding:0 10px 0 30px; font-size:12.5px; outline:none; color:#1e293b;
		               background:#f8fafc url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2.5'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") no-repeat 9px center;
		               box-sizing:border-box; transition:border-color .2s; }
		.xif-search:focus { border-color:#4f46e5; background-color:#fff; }
		.xif-opts    { flex:1; overflow-y:auto; padding:8px; }
		.xif-opt     { display:flex; align-items:center; gap:10px; padding:9px 12px;
		               border-radius:8px; cursor:pointer; font-size:13px; font-weight:500;
		               color:#334155; transition:background .12s; }
		.xif-opt:hover { background:#f8fafc; }
		.xif-opt.checked { background:#eef2ff; color:#3730a3; }
		.xif-opt input[type="checkbox"] { width:15px; height:15px; accent-color:#4f46e5;
		                                  cursor:pointer; flex-shrink:0; }
		.xif-empty-opts { padding:32px; text-align:center; color:#cbd5e1; font-size:13px; }
		.xif-footer  { display:flex; align-items:center; justify-content:space-between;
		               padding:12px 16px; border-top:1.5px solid #f1f5f9; background:#fafbff; }
		.xif-status  { font-size:12.5px; color:#64748b; font-weight:500; }
		.xif-status strong { color:#4f46e5; }
		.xif-actions { display:flex; gap:8px; }
		.xif-clear   { padding:0 14px; height:32px; border-radius:7px;
		               border:1.5px solid #e2e8f0; background:#fff; color:#64748b;
		               font-size:12.5px; font-weight:600; cursor:pointer; transition:all .15s; }
		.xif-clear:hover { border-color:#ef4444; color:#ef4444; background:#fff5f5; }
		.xif-apply   { padding:0 18px; height:32px; border-radius:7px; border:none;
		               background:linear-gradient(135deg,#4f46e5,#6366f1); color:#fff;
		               font-size:12.5px; font-weight:700; cursor:pointer; transition:opacity .15s; }
		.xif-apply:hover { opacity:.88; }
		/* Active filter badge on button */
		.xif-btn-active { background:linear-gradient(135deg,#eef2ff,#e0e7ff) !important;
		                  border-color:#c7d2fe !important; color:#4338ca !important; }

		/* ── Stat cards (drilldown) ── */
		.er2-stats-panel { background:#fff; border-radius:12px; padding:16px 20px;
		                   margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
		.er2-stats-cards { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }
		.er2-stat-card   { background:#fff; border-radius:12px; padding:14px 16px; flex:1;
		                   min-width:130px; box-shadow:0 1px 3px rgba(0,0,0,.06);
		                   cursor:pointer; transition:all .18s; border:2px solid transparent;
		                   display:flex; align-items:center; gap:12px; }
		.er2-stat-card:hover { box-shadow:0 4px 12px rgba(0,0,0,.1); transform:translateY(-1px); }
		.er2-stat-card.er2-sc-active { border-color:var(--sc-color,#4f46e5);
		                               background:var(--sc-bg,#eef2ff); }
		.er2-stat-icon   { width:38px; height:38px; border-radius:9px; flex-shrink:0;
		                   display:flex; align-items:center; justify-content:center;
		                   font-size:17px; background:var(--sc-bg,#eef2ff); }
		.er2-stat-body   { flex:1; min-width:0; }
		.er2-stat-val    { font-size:22px; font-weight:800; color:var(--sc-color,#4f46e5);
		                   line-height:1.1; }
		.er2-stat-lbl    { font-size:10px; color:#94a3b8; font-weight:700; text-transform:uppercase;
		                   letter-spacing:.6px; margin-top:2px; }
		.er2-stats-meta  { display:flex; gap:18px; flex-wrap:wrap; align-items:center; }
		.er2-stats-avg   { font-size:12.5px; color:#475569; font-weight:500; }
		.er2-gd-wrap     { display:flex; gap:5px; flex-wrap:wrap; }
		.er2-gd-badge    { font-size:11px; font-weight:700; padding:3px 10px; border-radius:20px;
		                   background:#f1f5f9; color:#475569; cursor:pointer; transition:all .15s;
		                   border:1.5px solid transparent; }
		.er2-gd-badge:hover  { background:#eef2ff; color:#4f46e5; }
		.er2-gd-badge.er2-gd-active { background:#eef2ff; color:#4f46e5; border-color:#c7d2fe; }

		/* ── Editable marks input ── */
		.er2-mi { width:68px; height:26px; border:1.5px solid #e2e8f0; border-radius:6px;
		          padding:0 5px; font-size:12px; color:#334155; text-align:center;
		          background:#fff; outline:none; transition:border-color .15s; }
		.er2-mi:focus   { border-color:#4f46e5; box-shadow:0 0 0 2px rgba(79,70,229,.12); }
		.er2-mi:disabled { background:#f8fafc; color:#94a3b8; cursor:not-allowed; }

		/* ── Lock button states ── */
		.er2-btn.outline-green { border-color:#a7f3d0; color:#059669; background:#f0fdf4; }
		.er2-btn.outline-green:hover { background:#dcfce7; border-color:#6ee7b7; }

		/* ── Page header ── */
		.er2-page-header { background:#fff; border-radius:12px; padding:20px 24px;
		                   margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.06);
		                   display:flex; align-items:center; gap:16px; }
		.er2-page-icon   { width:46px; height:46px; border-radius:12px; flex-shrink:0;
		                   display:flex; align-items:center; justify-content:center; }
		.er2-page-title  { font-size:17px; font-weight:800; color:#0f172a; line-height:1.2; }
		.er2-page-sub    { font-size:12px; color:#94a3b8; margin-top:3px; font-weight:500; }

		/* ── Page nav tabs ── */
		.er2-page-nav    { display:flex; gap:4px; margin-bottom:16px; background:#e2e8f0;
		                   border-radius:10px; padding:4px; width:fit-content; }
		.er2-pnav-btn    { padding:8px 18px; cursor:pointer; font-size:13px; font-weight:600;
		                   color:#64748b; border-radius:7px; transition:all .2s;
		                   user-select:none; letter-spacing:.1px; border:none;
		                   background:transparent; display:inline-flex; align-items:center; gap:5px; }
		.er2-pnav-btn:hover  { color:#4f46e5; background:rgba(79,70,229,.08); }
		.er2-pnav-btn.active { background:#fff; color:#4f46e5;
		                       box-shadow:0 1px 4px rgba(0,0,0,.12); }
		`;
		document.head.appendChild(style);
	}

	// ── Render shell ──────────────────────────────────────────────────────────
	var $body = $(page.main);
	$body.html(`
		<div class="er2-wrap" style="padding:20px 24px;">

			<!-- Page header -->
			<div class="er2-page-header">
				<div class="er2-page-icon" style="background:linear-gradient(135deg,#4f46e5,#6366f1);">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2">
						<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
						<rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
					</svg>
				</div>
				<div>
					<div class="er2-page-title">Course Results</div>
					<div class="er2-page-sub">View and manage student marks, grades and assessment results per course</div>
				</div>
			</div>

			<!-- Page navigation -->
			<div class="er2-page-nav">
				<button class="er2-pnav-btn active">
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
			</div>

			<!-- Course Results -->
			<div id="er2-tab-course">

				<!-- Top filter card -->
				<div class="er2-filter-card">
					<div class="er2-fgroup" style="max-width:240px;">
						<span class="er2-flabel">
							<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>
							Exam Plan
						</span>
						<select class="er2-select" id="er2-exam-plan">
							<option value="">Choose Exam Plan</option>
						</select>
					</div>
					<div class="er2-fgroup" style="max-width:260px;">
						<span class="er2-flabel">
							<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
							Department
						</span>
						<select class="er2-select" id="er2-dept">
							<option value="">Choose Department</option>
						</select>
					</div>
					<div class="er2-fgroup" style="max-width:320px;">
						<span class="er2-flabel">
							<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-1px;margin-right:3px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
							Course
						</span>
						<select class="er2-select" id="er2-course" disabled>
							<option value="">Choose Course</option>
						</select>
					</div>
					<div style="margin-left:auto;display:flex;gap:8px;align-items:flex-end;">
						<div class="er2-btn-dd">
							<button class="er2-btn outline-indigo" id="er2-sync-btn">
								<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
								Sync Students
								<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
							</button>
							<div class="dd-menu">
								<div class="dd-item" id="er2-sync-enroll">
									<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;vertical-align:-2px;color:#4f46e5;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
									Sync from Enrollment
								</div>
								<div class="dd-item" id="er2-sync-class">
									<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;vertical-align:-2px;color:#0ea5e9;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
									Add Class Students
								</div>
							</div>
						</div>
						<button class="er2-btn outline-red" id="er2-lock-btn">
							<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
							Lock
						</button>
					</div>
				</div>

				<!-- Course info panel (hidden until course selected) -->
				<div id="er2-info-panel" style="display:none;"></div>

				<!-- Statistics panel (hidden until course selected) -->
				<div id="er2-stats-panel" class="er2-stats-panel" style="display:none;"></div>

				<!-- Action bar (hidden until course selected) -->
				<div id="er2-actbar" class="er2-actbar" style="display:none;">
					<div class="er2-srch">
						<span class="er2-srch-ico">
							<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
						</span>
						<input type="text" id="er2-search" placeholder="Search student name or ID…">
					</div>
					<button class="er2-btn" id="er2-moderation-btn">
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
						Result Moderation
					</button>
					<div class="er2-btn-dd" id="er2-grades-dd">
						<button class="er2-btn outline-indigo">
							<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
							Manage Grades
							<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
						</button>
						<div class="dd-menu">
							<div class="dd-item" id="er2-grade-edit">Edit Grades</div>
							<div class="dd-item" id="er2-grade-bulk-upload">Bulk Upload</div>
							<div class="dd-item" id="er2-grade-report">Grade Report</div>
						</div>
					</div>
					<div class="er2-btn-dd" id="er2-marks-dd">
						<button class="er2-btn outline-indigo">
							<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>
							Manage Marks
							<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
						</button>
						<div class="dd-menu">
							<div class="dd-item" id="er2-marks-import">
								<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" style="margin-right:6px;vertical-align:-2px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
								Import Marks
							</div>
							<div class="dd-item" id="er2-marks-export">
								<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" style="margin-right:6px;vertical-align:-2px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
								Export Marks (Excel)
							</div>
						</div>
					</div>
					<div class="er2-btn-dd" id="er2-status-dd">
						<button class="er2-btn">
							<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
							Manage Status
							<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
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
					<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
					<select class="er2-select" id="er2-exam-filter" style="max-width:190px;height:30px;font-size:12px;">
						<option value="">All Exam Types</option>
					</select>
					<div class="er2-paglen-wrap">
						<label for="er2-paglen">Show</label>
						<select class="er2-paglen" id="er2-paglen">
							<option value="10">10</option>
							<option value="20" selected>20</option>
							<option value="50">50</option>
							<option value="100">100</option>
							<option value="500">500</option>
						</select>
						<label>records</label>
					</div>
					<div class="er2-pag" id="er2-pag">
						<span class="er2-paglen-info" id="er2-pag-info"></span>
						<button class="er2-pag-btn" id="er2-prev">&#8249;</button>
						<button class="er2-pag-btn" id="er2-next">&#8250;</button>
					</div>
					<button class="er2-btn" id="er2-inst-filter" style="margin-left:4px;height:30px;font-size:12px;">
						<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
						Institutional Filter
					</button>
				</div>

				<!-- Empty state -->
				<div id="er2-empty" class="er2-empty">
					<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
						<circle cx="60" cy="60" r="56" fill="#eef2ff" stroke="#c7d2fe" stroke-width="2"/>
						<rect x="35" y="30" width="50" height="60" rx="6" fill="#fff" stroke="#c7d2fe" stroke-width="2"/>
						<rect x="43" y="44" width="34" height="3" rx="1.5" fill="#c7d2fe"/>
						<rect x="43" y="53" width="26" height="3" rx="1.5" fill="#e0e7ff"/>
						<rect x="43" y="62" width="30" height="3" rx="1.5" fill="#e0e7ff"/>
						<rect x="43" y="71" width="20" height="3" rx="1.5" fill="#e0e7ff"/>
						<circle cx="84" cy="84" r="18" fill="#4f46e5"/>
						<path d="M76 84h16M84 76v16" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
					</svg>
					<div class="er2-empty-txt">Select a Department &amp; Course</div>
					<div class="er2-empty-sub">Choose from the filters above to view examination results</div>
				</div>

				<!-- Split panel -->
				<div id="er2-split" class="er2-split" style="display:none;max-height:calc(100vh - 340px);">
					<!-- Left: student list -->
					<div id="er2-left" class="er2-left">
						<div class="er2-lhdr">
							<input type="checkbox" id="er2-chk-all" title="Select All">
							<div class="er2-btn-dd" id="er2-select-dd" style="flex:1;min-width:0;">
								<span class="er2-lhdr-title" id="er2-student-count-lbl"
								      style="cursor:pointer;user-select:none;">
									Students (0)
									<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="vertical-align:-1px;"><polyline points="6 9 12 15 18 9"/></svg>
								</span>
								<div class="dd-menu" style="min-width:220px;">
									<div class="dd-item" id="er2-sel-page">
										<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" style="margin-right:6px;vertical-align:-2px;"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
										Select All For This Page
									</div>
									<div class="dd-item" id="er2-sel-all">
										<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" stroke-width="2" style="margin-right:6px;vertical-align:-2px;"><polyline points="20 6 9 17 4 12"/></svg>
										Select All Across All Pages
									</div>
									<div class="dd-item" id="er2-sel-none">
										<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" style="margin-right:6px;vertical-align:-2px;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
										Select None
									</div>
								</div>
							</div>
							<button class="er2-sort-btn" id="er2-sort-btn">
								<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 5H21M11 9H17M11 13H13"/><path d="M3 7l4-4 4 4M7 3v14"/></svg>
								<span id="er2-sort-lbl">Sort</span>
							</button>
						</div>
						<div class="er2-status-bar">
							<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
							<select id="er2-status-filter" style="font-size:11px;font-weight:600;border:1.5px solid #e2e8f0;border-radius:6px;padding:3px 7px;color:#475569;background:#fff;outline:none;cursor:pointer;">
								<option value="">All Students</option>
								<option value="Active">Active</option>
								<option value="Inactive">Inactive</option>
								<option value="Dropped">Dropped</option>
							</select>
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
		</div>

		<!-- Hover popup -->
		<div id="er2-popup"></div>
	`);

	// ── DOM refs ──────────────────────────────────────────────────────────────
	var $examPlan = $body.find('#er2-exam-plan');
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
	var $pagLen   = $body.find('#er2-paglen');
	var $cntLbl   = $body.find('#er2-student-count-lbl');
	var $collapse    = $body.find('#er2-collapse-btn');
	var $popup       = $('#er2-popup');
	var $examFilter  = $body.find('#er2-exam-filter');
	var $statsPanel  = $body.find('#er2-stats-panel');

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

	// ── Load exam plans ───────────────────────────────────────────────────────
	frappe.call({
		method: 'slcm.slcm.page.examination_result.examination_result.get_exam_plans',
		callback: function (r) {
			(r.message || []).forEach(function (ep) {
				var label = frappe.utils.escape_html(ep.exam_name || ep.name);
				if (ep.status) label += ' [' + frappe.utils.escape_html(ep.status) + ']';
				$examPlan.append('<option value="' + ep.name + '">' + label + '</option>');
			});
		},
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

	// ── Exam Plan change ─────────────────────────────────────────────────────
	$examPlan.on('change', function () {
		S.exam_plan  = $(this).val();
		S.department = null;
		S.course     = null;
		S.page       = 1;
		$dept.val('').find('option:not(:first)').remove();
		$course.val('').prop('disabled', true).find('option:not(:first)').remove();
		hide_detail();
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_departments',
			args: { exam_plan: S.exam_plan || '' },
			callback: function (r) {
				(r.message || []).forEach(function (d) {
					$dept.append('<option value="' + d.name + '">' +
						frappe.utils.escape_html(d.department_name) + '</option>');
				});
			},
		});
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
			args: { department: S.department, exam_plan: S.exam_plan || '' },
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
		S.course       = $(this).val();
		S.page         = 1;
		S.search       = '';
		S.inst_filter  = { programmes: [], batches: [], course_types: [] };
		S.inst_options = null;
		$search.val('');
		$body.find('#er2-inst-filter').removeClass('xif-btn-active').find('.xif-count').remove();
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

	// ── Page length ──────────────────────────────────────────────────────────
	$pagLen.on('change', function () {
		S.page_length = parseInt($(this).val(), 10) || 20;
		S.page        = 1;
		if (S.course) load_students();
	});

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

	// ── Student status filter ─────────────────────────────────────────────────
	$body.find('#er2-status-filter').on('change', function () {
		S.status_filter = $(this).val();
		S.page = 1;
		if (S.course) load_students();
	});

	// ── Select dropdown ───────────────────────────────────────────────────────
	$body.find('#er2-sel-page').on('click', function () {
		S.selected_all = false;
		$body.find('.er2-chk').prop('checked', true);
		$body.find('#er2-chk-all').prop('checked', true);
	});
	$body.find('#er2-sel-all').on('click', function () {
		S.selected_all = true;
		$body.find('.er2-chk').prop('checked', true);
		$body.find('#er2-chk-all').prop('checked', true);
		frappe.show_alert({ message: 'All ' + S.total + ' students selected across all pages.', indicator: 'blue' });
	});
	$body.find('#er2-sel-none').on('click', function () {
		S.selected_all = false;
		$body.find('.er2-chk').prop('checked', false);
		$body.find('#er2-chk-all').prop('checked', false);
	});
	$body.find('#er2-chk-all').on('change', function () {
		var checked = $(this).prop('checked');
		$body.find('.er2-chk').prop('checked', checked);
		if (!checked) S.selected_all = false;
	});

	// ── Institutional Filter ──────────────────────────────────────────────────
	$body.find('#er2-inst-filter').on('click', function () {
		if (!S.course) { frappe.show_alert({ message: 'Select a course first.', indicator: 'orange' }); return; }
		if (S.inst_options) {
			show_inst_filter_dialog(S.inst_options);
		} else {
			frappe.call({
				method: 'slcm.slcm.page.examination_result.examination_result.get_institutional_filter_options',
				args: { course: S.course },
				callback: function (r) {
					S.inst_options = r.message || { programmes: [], batches: [], course_types: [] };
					show_inst_filter_dialog(S.inst_options);
				},
			});
		}
	});

	// ── Stub buttons ─────────────────────────────────────────────────────────
	$body.find('#er2-moderation-btn').on('click', function () {
		frappe.msgprint('Result Moderation — coming soon.');
	});

	// ── Manage Grades ─────────────────────────────────────────────────────────
	$body.find('#er2-grade-edit').on('click', function () {
		if (!S.course || !S.info) { frappe.msgprint('Select a course first.'); return; }
		var ids = S.students.map(function (s) { return s.student; });
		if (!ids.length) { frappe.msgprint('No students on this page.'); return; }
		frappe.confirm(
			'Auto-calculate grades for all ' + ids.length + ' student(s) on this page using the Grade Schema?',
			function () {
				var done = 0;
				frappe.show_alert({ message: 'Calculating grades…', indicator: 'blue' });
				var promises = ids.map(function (sid) {
					return new Promise(function (resolve) {
						frappe.call({
							method: 'slcm.slcm.page.examination_result.examination_result.save_marks',
							// Trigger recalc by calling with a no-op: reload marks after
							// Actually just call _recalculate via a dedicated call below
							args: {
								course: S.course, exam_plan: S.info.exam_plan || '',
								student: sid, component: '', assessment_type: '',
								marks_field: 'marks', value: null,
							},
							error: function () { resolve(); },
							callback: function (r) {
								done++;
								if (r.message) {
									if (!S.marks[sid]) S.marks[sid] = { entries: {} };
									S.marks[sid].total = r.message.total;
									S.marks[sid].grade = r.message.grade;
								}
								resolve();
							},
						});
					});
				});
				Promise.all(promises).then(function () {
					render_marks_table();
					load_stats();
					frappe.show_alert({ message: 'Grades recalculated for ' + done + ' students.', indicator: 'green' });
				});
			}
		);
	});

	$body.find('#er2-grade-report').on('click', function () {
		if (!S.course || !S.info) { frappe.msgprint('Select a course first.'); return; }
		load_stats(true);
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
		if (!S.course || !S.info) { frappe.msgprint('Select a course first.'); return; }
		var isLocked = S.info.status === 'LOCKED';
		var msg = isLocked
			? 'Unlock this course to allow marks entry?'
			: 'Lock this course? Faculty will not be able to edit marks after locking.';
		frappe.confirm(msg, function () {
			frappe.call({
				method: 'slcm.slcm.page.examination_result.examination_result.toggle_lock',
				args: { course: S.course, exam_plan: S.info.exam_plan || '' },
				callback: function (r) {
					var res = r.message || {};
					S.info.status = res.status;
					update_lock_btn();
					render_marks_table();
					frappe.show_alert({
						message: res.status === 'LOCKED' ? 'Course locked.' : 'Course unlocked.',
						indicator: res.status === 'LOCKED' ? 'red' : 'green',
					});
				},
			});
		});
	});

	// ── Import / Export Marks ─────────────────────────────────────────────────
	$body.find('#er2-marks-export').on('click', function () {
		if (!S.course || !S.info) { frappe.msgprint('Select a course first.'); return; }
		frappe.show_alert({ message: 'Preparing Excel…', indicator: 'blue' });
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.export_marks_excel',
			args: { course: S.course, exam_plan: S.info.exam_plan || '' },
			callback: function (r) {
				if (r.message && r.message.file_url) {
					window.open(r.message.file_url);
				}
			},
		});
	});

	$body.find('#er2-marks-import').on('click', function () {
		if (!S.course || !S.info) { frappe.msgprint('Select a course first.'); return; }
		var d = new frappe.ui.Dialog({
			title: 'Import Marks from Excel',
			fields: [
				{
					fieldname: 'info_html',
					fieldtype: 'HTML',
					options: '<p style="font-size:12px;color:#64748b;margin:0 0 10px;">Upload the filled marks template. Use <b>Export Marks (Excel)</b> first to get the correct column format.</p>',
				},
				{ fieldname: 'upload_file', fieldtype: 'Attach', label: 'Excel File (.xlsx)', reqd: 1 },
				{
					fieldname: 'note',
					fieldtype: 'HTML',
					options: '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px 14px;margin-top:6px;font-size:12px;color:#14532d;">' +
						'Rows are matched by Registration ID or Email. Existing marks will be overwritten.' +
						'</div>',
				},
			],
			primary_action_label: 'Import',
			primary_action: function (vals) {
				if (!vals.upload_file) { frappe.msgprint('Please attach a file.'); return; }
				d.hide();
				frappe.call({
					method: 'slcm.slcm.page.examination_result.examination_result.import_marks_excel',
					args: { course: S.course, exam_plan: S.info.exam_plan || '', file_url: vals.upload_file },
					callback: function (r) {
						var res = r.message || {};
						var msg = 'Imported: ' + (res.updated || 0) + ' students updated.';
						if (res.errors && res.errors.length) {
							msg += ' Errors: ' + res.errors.slice(0, 5).join(', ');
						}
						frappe.msgprint(msg);
						load_students();
						load_stats();
					},
				});
			},
		});
		d.show();
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
			args: { course: S.course, exam_plan: S.exam_plan || '' },
			callback: function (r) {
				S.info           = r.message || {};
				S.columns        = S.info.columns || [];
				S.reexam_columns = S.info.reexam_columns || [];
				render_info_panel();
				populate_exam_filter();
				update_lock_btn();
				$info.show();
				$actbar.show();
				$filterrow.show();
				$statsPanel.show();
				$empty.hide();
				$split.show();
				$cntLbl.html('Students (' + S.info.student_count + ') <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" style="vertical-align:-1px;"><polyline points="6 9 12 15 18 9"/></svg>');
				load_students();
				load_stats();
			},
		});
	}

	function update_lock_btn() {
		var isLocked = S.info && S.info.status === 'LOCKED';
		var $btn = $body.find('#er2-lock-btn');
		if (isLocked) {
			$btn.removeClass('outline-red').addClass('outline-indigo').html(
				'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:4px;"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>' +
				'Unlock'
			);
		} else {
			$btn.removeClass('outline-indigo').addClass('outline-red').html(
				'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:4px;"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>' +
				'Lock'
			);
		}
	}

	function load_stats(show_panel) {
		if (!S.info || !S.info.exam_plan) return;
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_course_statistics',
			args: { course: S.course, exam_plan: S.info.exam_plan },
			callback: function (r) {
				var st = r.message || {};
				var graded = (st.passed || 0) + (st.failed || 0);

				// Build grade dist badges
				var distHtml = '';
				(st.grade_dist || []).forEach(function (g) {
					distHtml += '<span style="display:inline-flex;align-items:center;gap:4px;' +
						'background:#f1f5f9;border-radius:6px;padding:2px 9px;font-size:12px;margin:2px;">' +
						'<b style="color:#1e293b;">' + frappe.utils.escape_html(g.grade || '') + '</b>' +
						'<span style="color:#64748b;">' + (g.count || 0) + '</span></span>';
				});

				// Extra info row
				var extra = '';
				if (st.avg_marks !== undefined) {
					extra += '<span style="font-size:12px;color:#64748b;font-weight:500;margin-right:16px;">&#x2205; Avg: <b>' + st.avg_marks + '</b></span>';
				}
				if (st.topper && st.topper.name) {
					extra += '<span style="font-size:12px;color:#64748b;font-weight:500;">&#127942; Topper: <b>' + frappe.utils.escape_html(st.topper.name) + '</b>' +
						(st.topper.marks ? ' (' + st.topper.marks + ')' : '') + '</span>';
				}

				$statsPanel.html(
					'<div class="er2-stats-cards">' +
					_stat_card('#4f46e5', '&#127979;', st.total || 0,    'Total Students') +
					_stat_card('#0ea5e9', '&#9998;',   graded,            'Graded') +
					_stat_card('#10b981', '&#10003;',  st.passed || 0,    'Passed') +
					_stat_card('#ef4444', '&#10007;',  st.failed || 0,    'Failed') +
					_stat_card('#f59e0b', '&#8987;',   st.not_graded || 0,'Not Graded') +
					(distHtml ? '<div class="er2-stat-card" style="--sc-color:#7c3aed;flex:2.5;">' +
						'<div class="er2-stat-icon" style="background:#ede9fe;color:#7c3aed;font-size:16px;">&#127775;</div>' +
						'<div class="er2-stat-body">' +
						'<div class="er2-stat-lbl">Grade Distribution</div>' +
						'<div style="display:flex;flex-wrap:wrap;gap:2px;margin-top:4px;">' + distHtml + '</div>' +
						'</div></div>' : '') +
					'</div>' +
					(extra ? '<div class="er2-stats-meta">' + extra + '</div>' : '')
				);

				if (show_panel) {
					$statsPanel[0].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
				}
			},
		});
	}

	function _stat_card(color, icon, num, lbl) {
		return '<div class="er2-stat-card" style="--sc-color:' + color + ';">' +
			'<div class="er2-stat-icon" style="background:' + color + '22;color:' + color + ';font-size:16px;">' + icon + '</div>' +
			'<div class="er2-stat-body">' +
			'<div class="er2-stat-val">' + num + '</div>' +
			'<div class="er2-stat-lbl">' + lbl + '</div>' +
			'</div></div>';
	}

	function load_students() {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_course_students_paged',
			args: {
				course:            S.course,
				search:            S.search,
				page:              S.page,
				page_length:       S.page_length,
				sort_by:           S.sort_by,
				sort_order:        S.sort_order,
				status_filter:     S.status_filter,
				inst_programmes:   JSON.stringify(S.inst_filter.programmes),
				inst_batches:      JSON.stringify(S.inst_filter.batches),
				inst_course_types: JSON.stringify(S.inst_filter.course_types),
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

		function card(accent, icon, label, val) {
			return '<div class="er2-icard ' + accent + '">' +
				'<div class="er2-ilabel">' + icon + ' ' + label + '</div>' +
				'<div class="er2-ival">' + val + '</div>' +
				'</div>';
		}

		var on_badge  = '<span style="display:inline-flex;align-items:center;gap:4px;background:#d1fae5;color:#065f46;font-weight:700;padding:2px 9px;border-radius:20px;font-size:11px;">&#9679; ON</span>';
		var off_badge = '<span style="display:inline-flex;align-items:center;gap:4px;background:#f1f5f9;color:#94a3b8;font-weight:700;padding:2px 9px;border-radius:20px;font-size:11px;">&#9675; OFF</span>';

		var view_val = o.view_access ? on_badge : off_badge;
		var edit_val = o.edit_access
			? on_badge + (o.edit_deadline ? '<span style="font-size:11px;color:#64748b;margin-left:6px;">' + frappe.utils.escape_html(o.edit_deadline) + '</span>' : '')
			: off_badge;
		var mask_val = o.mask_student_info
			? on_badge + '<span style="font-size:11px;color:#64748b;margin-left:6px;">Admin Access</span>'
			: off_badge;

		var eval_link = o.evaluation_schema
			? '<a href="#" class="er2-schema-link" data-schema="eval" data-name="' + frappe.utils.escape_html(o.evaluation_schema) + '">' + frappe.utils.escape_html(o.evaluation_schema) + '</a>'
			: '<span style="color:#94a3b8;">—</span>';
		var grade_link = o.grade_schema
			? '<a href="#" class="er2-schema-link" data-schema="grade" data-name="' + frappe.utils.escape_html(o.grade_schema) + '">' + frappe.utils.escape_html(o.grade_schema) + '</a>'
			: '<span style="color:#94a3b8;">—</span>';
		var calc_link = o.evaluation_schema
			? '<a href="#" id="er2-calc-settings-link" style="color:#4f46e5;font-size:12px;font-weight:600;text-decoration:none;border-bottom:1px dashed #c7d2fe;">Calculation Settings</a>'
			: '<span style="color:#94a3b8;">—</span>';

		var course_lbl = frappe.utils.escape_html((o.course_name || '') + (o.course_code ? ' [' + o.course_code + ']' : ''));

		$info.html(
			'<div class="er2-info">' +
			card('', '&#128100;', 'Students Enrolled',
				'<span style="font-size:22px;font-weight:800;color:#4f46e5;line-height:1.1;">' + (o.student_count || 0) + '</span>') +
			card('teal', '&#128218;', 'Course',
				'<span style="font-weight:700;color:#0369a1;">' + course_lbl + '</span>' +
				'<span style="display:block;font-size:11px;color:#94a3b8;margin-top:2px;font-weight:500;">' +
				(o.credit_value ? o.credit_value + ' Credits' : '') + '</span>') +
			card('green', '&#9999;&#65039;', 'Evaluation Schema', eval_link +
				'<span style="display:block;margin-top:4px;">' + calc_link + '</span>') +
			card('amber', '&#127775;', 'Grade Schema', grade_link) +
			card('rose', '&#128065;&#65039;', 'View Access', view_val) +
			card('slate', '&#9998;', 'Edit Access', edit_val) +
			card('violet', '&#128373;&#65039;', 'Student Masking', mask_val) +
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
		S.students.forEach(function (s, idx) {
			var status_cls = s.account_status === 'Blocked' ? 'blocked' :
				s.student_status === 'Dropped' ? 'dropped' :
				s.student_status === 'Inactive' ? 'inactive' : 'active';
			var status_txt = s.student_status || 'Active';
			var initials   = (s.student_name || 'S').charAt(0).toUpperCase();
			var av_cls     = 'av-' + (idx % 8);
			var dot_color  = status_cls === 'active' ? '#10b981' : status_cls === 'dropped' ? '#f59e0b' : '#ef4444';
			var avatarContent = s.passport_size_photo
				? '<img src="' + frappe.utils.escape_html(s.passport_size_photo) + '" alt="">'
				: initials;
			html +=
				'<div class="er2-srow" data-student="' + frappe.utils.escape_html(s.student) + '">' +
				'  <input type="checkbox" class="er2-chk" style="flex-shrink:0;accent-color:#4f46e5;width:14px;height:14px;cursor:pointer;">' +
				'  <div class="er2-savatar ' + av_cls + '">' + avatarContent + '</div>' +
				'  <div class="er2-sinfo">' +
				'    <div class="er2-sname">' + frappe.utils.escape_html(s.student_name || s.student) + '</div>' +
				'    <div class="er2-sreg">' + frappe.utils.escape_html(s.registration_id || s.student || '') + '</div>' +
				'    <div class="er2-sbadges">' +
				'      <span class="er2-badge ' + status_cls + '">' +
				'        <span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:' + dot_color + ';margin-right:4px;vertical-align:1px;"></span>' +
				frappe.utils.escape_html(status_txt) + '</span>' +
				'      <span class="er2-badge regular">Regular</span>' +
				'    </div>' +
				'  </div>' +
				'</div>';
		});
		if (!html) {
			html = '<div style="padding:40px;text-align:center;color:#94a3b8;font-size:12.5px;font-weight:500;">' +
				'<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" style="display:block;margin:0 auto 10px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>' +
				'No students found</div>';
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
		var C_COMP   = 'background:linear-gradient(90deg,#eef2ff,#e0e7ff);color:#3730a3;border-bottom:2px solid #818cf8;';
		var C_GRADE  = 'background:linear-gradient(90deg,#ecfdf5,#d1fae5);color:#065f46;border-bottom:2px solid #34d399;';
		var C_STATUS = 'background:linear-gradient(90deg,#fffbeb,#fef3c7);color:#92400e;border-bottom:2px solid #fbbf24;';
		var C_REEXAM = 'background:linear-gradient(90deg,#fdf2f8,#fce7f3);color:#9d174d;border-bottom:2px solid #f472b6;';
		var C_FINAL  = 'background:linear-gradient(90deg,#eff6ff,#dbeafe);color:#1e40af;border-bottom:2px solid #60a5fa;';

		// ── Header row 1: section-level group headers ────────────────────────────
		var th1 = '';
		groups.forEach(function (g) {
			th1 += '<th colspan="' + (g.cols.length * 3) + '" class="type-hdr" style="text-align:center;' + C_COMP + '">' +
				frappe.utils.escape_html(g.component_name) + '</th>';
		});
		// Total + Grade + Moderated Grade (span 3)
		th1 += '<th colspan="3" class="type-hdr" style="text-align:center;' + C_GRADE + '">Grade</th>';
		// Overall Status (span 5)
		th1 += '<th colspan="5" class="type-hdr er2-status-hdr" style="text-align:center;' + C_STATUS + '">' +
			'Overall Status</th>';
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
		th2 += '<th class="er2-status-col" style="font-size:11px;color:#6c757d;min-width:90px;">Enrollment<br>Status</th>' +
			'<th class="er2-status-col" style="font-size:11px;color:#6c757d;min-width:90px;">Attendance<br>Status</th>' +
			'<th class="er2-status-col" style="font-size:11px;color:#6c757d;min-width:80px;">Fairness<br>Status</th>' +
			'<th class="er2-status-col" style="font-size:11px;color:#6c757d;min-width:60px;">SGPA</th>' +
			'<th class="er2-status-col" style="font-size:11px;color:#6c757d;min-width:120px;">Remarks</th>';
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
		th3 += '<th class="er2-status-col"></th>' +
			'<th class="er2-status-col"></th>' +
			'<th class="er2-status-col"></th>' +
			'<th class="er2-status-col"></th>' +
			'<th class="er2-status-col"></th>';
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

			var canEdit = S.info && S.info.edit_access && S.info.status !== 'LOCKED';

			// Regular assessment cells
			cols.forEach(function (col) {
				var key  = (col.component || '') + '|' + (col.assessment_type || '');
				var e    = entries[key] || {};
				var mVal = e.marks            != null ? parseFloat(e.marks).toFixed(2)             : '';
				var rvVal= e.revaluation_marks != null ? parseFloat(e.revaluation_marks).toFixed(2) : '';
				var moVal= e.moderated_marks   != null ? parseFloat(e.moderated_marks).toFixed(2)   : '';
				var comp = frappe.utils.escape_html(col.component      || '');
				var atyp = frappe.utils.escape_html(col.assessment_type || '');
				var stu  = frappe.utils.escape_html(s.student);
				if (canEdit) {
					cells += '<td style="padding:4px 6px;">' +
						'<input type="number" step="0.01" min="0" class="er2-mi" ' +
						'data-student="' + stu + '" data-comp="' + comp + '" data-atype="' + atyp + '" data-field="marks" ' +
						'value="' + frappe.utils.escape_html(mVal) + '" placeholder="—" ' +
						'style="width:70px;height:26px;border:1.5px solid #e2e8f0;border-radius:6px;padding:0 6px;font-size:12px;font-weight:600;text-align:center;outline:none;">' +
						'</td>' +
						'<td style="padding:4px 6px;">' +
						'<input type="number" step="0.01" min="0" class="er2-mi" ' +
						'data-student="' + stu + '" data-comp="' + comp + '" data-atype="' + atyp + '" data-field="revaluation_marks" ' +
						'value="' + frappe.utils.escape_html(rvVal) + '" placeholder="—" ' +
						'style="width:70px;height:26px;border:1.5px solid #e2e8f0;border-radius:6px;padding:0 6px;font-size:12px;font-weight:600;text-align:center;outline:none;">' +
						'</td>' +
						'<td style="padding:4px 6px;">' +
						'<input type="number" step="0.01" min="0" class="er2-mi" ' +
						'data-student="' + stu + '" data-comp="' + comp + '" data-atype="' + atyp + '" data-field="moderated_marks" ' +
						'value="' + frappe.utils.escape_html(moVal) + '" placeholder="—" ' +
						'style="width:70px;height:26px;border:1.5px solid #e2e8f0;border-radius:6px;padding:0 6px;font-size:12px;font-weight:600;text-align:center;outline:none;">' +
						'</td>';
				} else {
					cells += '<td>' + (mVal  || '—') + '</td>' +
					         '<td>' + (rvVal || '—') + '</td>' +
					         '<td>' + (moVal || '—') + '</td>';
				}
			});

			// Grade section
			cells += '<td style="font-weight:700;" class="er2-total-cell" data-student="' + frappe.utils.escape_html(s.student) + '">' + total + '</td>' +
				'<td style="font-weight:700;color:#059669;" class="er2-grade-cell" data-student="' + frappe.utils.escape_html(s.student) + '">' + frappe.utils.escape_html(sm.grade || '—') + '</td>' +
				'<td>' + frappe.utils.escape_html(sm.moderated_grade || '—') + '</td>';

			// Overall Status
			var es   = sm.enrollment_status  || '—';
			var at   = sm.attendance_status  || '—';
			var fs   = sm.fairness_status    || '—';
			var sg   = sm.consider_for_sgpa  ? '<span style="color:#28a745;font-weight:700;">&#10003;</span>' : '—';
			var rmk  = frappe.utils.escape_html(sm.remark || '');
			cells += '<td class="er2-status-col">' + frappe.utils.escape_html(es) + '</td>' +
				'<td class="er2-status-col">' + frappe.utils.escape_html(at) + '</td>' +
				'<td class="er2-status-col">' + frappe.utils.escape_html(fs) + '</td>' +
				'<td class="er2-status-col" style="text-align:center;">' + sg + '</td>' +
				'<td class="er2-status-col er2-remark-cell" style="text-align:left;min-width:140px;">' +
				'<textarea class="er2-remark-input" data-student="' + frappe.utils.escape_html(s.student) + '" ' +
				'placeholder="Add remarks" style="width:100%;font-size:11px;border:1px solid #dee2e6;' +
				'border-radius:3px;padding:3px 5px;resize:vertical;min-height:36px;background:#fff;">' +
				rmk + '</textarea>' +
				'<span class="er2-remark-save" data-student="' + frappe.utils.escape_html(s.student) + '" ' +
				'style="font-size:10px;color:#e63946;cursor:pointer;display:none;">&#9998; Save</span>' +
				'</td>';

			// Re-Exam cells
			reexam_cols.forEach(function (col) {
				var key  = (col.component || '') + '|' + (col.assessment_type || '');
				var e    = entries[key] || {};
				var mVal = e.marks            != null ? parseFloat(e.marks).toFixed(2)             : '';
				var rvVal= e.revaluation_marks != null ? parseFloat(e.revaluation_marks).toFixed(2) : '';
				var comp = frappe.utils.escape_html(col.component      || '');
				var atyp = frappe.utils.escape_html(col.assessment_type || '');
				var stu  = frappe.utils.escape_html(s.student);
				if (canEdit) {
					cells +=
						'<td style="padding:4px 6px;"><input type="number" step="0.01" min="0" class="er2-mi" ' +
						'data-student="' + stu + '" data-comp="' + comp + '" data-atype="' + atyp + '" data-field="marks" ' +
						'value="' + frappe.utils.escape_html(mVal) + '" placeholder="—" ' +
						'style="width:70px;height:26px;border:1.5px solid #fce7f3;border-radius:6px;padding:0 6px;font-size:12px;font-weight:600;text-align:center;outline:none;"></td>' +
						'<td style="padding:4px 6px;"><input type="number" step="0.01" min="0" class="er2-mi" ' +
						'data-student="' + stu + '" data-comp="' + comp + '" data-atype="' + atyp + '" data-field="revaluation_marks" ' +
						'value="' + frappe.utils.escape_html(rvVal) + '" placeholder="—" ' +
						'style="width:70px;height:26px;border:1.5px solid #fce7f3;border-radius:6px;padding:0 6px;font-size:12px;font-weight:600;text-align:center;outline:none;"></td>';
				} else {
					cells += '<td>' + (mVal  || '—') + '</td><td>' + (rvVal || '—') + '</td>';
				}
			});

			// Updated Final Result
			var ufmVal = (sm.updated_final_marks != null && sm.updated_final_marks !== 0)
				? parseFloat(sm.updated_final_marks).toFixed(2) : '';
			var ugVal  = sm.updated_grade || '';
			var stu2   = frappe.utils.escape_html(s.student);
			if (canEdit) {
				cells +=
					'<td style="padding:4px 6px;"><input type="number" step="0.01" min="0" class="er2-uf-marks" ' +
					'data-student="' + stu2 + '" ' +
					'value="' + frappe.utils.escape_html(ufmVal) + '" placeholder="—" ' +
					'style="width:80px;height:26px;border:1.5px solid #bfdbfe;border-radius:6px;padding:0 6px;font-size:12px;font-weight:700;text-align:center;outline:none;"></td>' +
					'<td style="padding:4px 6px;"><input type="text" class="er2-uf-grade" ' +
					'data-student="' + stu2 + '" ' +
					'value="' + frappe.utils.escape_html(ugVal) + '" placeholder="—" ' +
					'style="width:60px;height:26px;border:1.5px solid #bfdbfe;border-radius:6px;padding:0 6px;font-size:12px;font-weight:700;text-align:center;outline:none;color:#1a237e;"></td>';
			} else {
				cells +=
					'<td style="font-weight:700;">' + frappe.utils.escape_html(ufmVal || '—') + '</td>' +
					'<td style="font-weight:700;color:#1a237e;">' + frappe.utils.escape_html(ugVal || '—') + '</td>';
			}

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

		// ── Inline marks entry ─────────────────────────────────────────────────
		var _saveTimer = {};
		$mtable.find('.er2-mi').on('focus', function () {
			$(this).css('border-color', '#4f46e5');
		}).on('blur', function () {
			$(this).css('border-color', '#e2e8f0');
		}).on('change', function () {
			var $inp    = $(this);
			var student = $inp.data('student');
			var comp    = $inp.data('comp')  || '';
			var atype   = $inp.data('atype') || '';
			var field   = $inp.data('field');
			var val     = $inp.val().trim();
			var $tr     = $mtable.find('tr[data-student="' + student + '"]');

			// Yellow flash while pending
			$tr.css('background', '#fefce8');
			clearTimeout(_saveTimer[student + field + comp + atype]);
			_saveTimer[student + field + comp + atype] = setTimeout(function () {
				frappe.call({
					method: 'slcm.slcm.page.examination_result.examination_result.save_marks',
					args: {
						course:          S.course,
						exam_plan:       S.info.exam_plan || '',
						student:         student,
						component:       comp,
						assessment_type: atype,
						marks_field:     field,
						value:           val === '' ? null : parseFloat(val),
					},
					callback: function (r) {
						$tr.css('background', '');
						if (r.message) {
							var total = r.message.total;
							var grade = r.message.grade;
							// Update in-place
							$mtable.find('.er2-total-cell[data-student="' + student + '"]')
								.text(total != null ? parseFloat(total).toFixed(2) : '—');
							$mtable.find('.er2-grade-cell[data-student="' + student + '"]')
								.text(grade || '—');
							// Update state
							if (!S.marks[student]) S.marks[student] = { entries: {} };
							S.marks[student].total = total;
							S.marks[student].grade = grade;
							// Refresh stats bar
							load_stats();
						}
					},
					error: function () {
						$tr.css('background', '#fff1f2');
					},
				});
			}, 500);
		});

		// Remarks: show save button on typing
		$mtable.find('.er2-remark-input').on('input', function () {
			$(this).siblings('.er2-remark-save').show();
		});
		$mtable.find('.er2-remark-save').on('click', function () {
			var student = $(this).data('student');
			var $inp    = $(this).siblings('.er2-remark-input');
			var remark  = $inp.val();
			var $btn    = $(this);
			frappe.call({
				method: 'slcm.slcm.page.examination_result.examination_result.save_student_remark',
				args: {
					course:    S.course,
					exam_plan: S.info.exam_plan || '',
					student:   student,
					remark:    remark,
				},
				callback: function () {
					$btn.hide();
					frappe.show_alert({ message: 'Remark saved.', indicator: 'green' });
				},
			});
		});

		// ── Sync student-list top offset with marks thead height ──────────────────
		// After the table renders (with sticky 3-row thead), measure the total
		// non-scrollable header area in both panels and add a spacer so that
		// student row[i] aligns pixel-perfectly with marks data row[i].
		setTimeout(function () {
			var $thead   = $mtable.find('table thead');
			var theadH   = $thead.length ? $thead.outerHeight(true) : 0;
			var lhdrH    = $left.find('.er2-lhdr').outerHeight(true)      || 0;
			var stbarH   = $left.find('.er2-status-bar').outerHeight(true) || 0;
			var leftHdrH = lhdrH + stbarH;
			var spacerH  = Math.max(0, theadH - leftHdrH);
			$slist.find('.er2-align-spacer').remove();
			if (spacerH > 0) {
				$slist.prepend(
					'<div class="er2-align-spacer" style="height:' + spacerH + 'px;flex-shrink:0;"></div>'
				);
			}
		}, 30);
	}

	function update_pagination() {
		var from     = S.total ? (S.page - 1) * S.page_length + 1 : 0;
		var to       = Math.min(S.page * S.page_length, S.total);
		var totalPgs = S.total ? Math.ceil(S.total / S.page_length) : 1;
		if (S.total) {
			$pagInfo.html(
				from + '&ndash;' + to + ' of <strong>' + S.total + '</strong>' +
				(totalPgs > 1 ? ' &nbsp;(Page ' + S.page + '/' + totalPgs + ')' : '')
			);
		} else {
			$pagInfo.text('0 students');
		}
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
		var pw  = $popup.outerWidth(true)  || 340;
		var ph  = $popup.outerHeight(true) || 200;
		var vw  = window.innerWidth;
		var vh  = window.innerHeight;
		var left = (x + pw + 20 > vw) ? x - pw - 10 : x + 16;
		var top  = (y + ph + 10 > vh) ? y - ph - 10 : y + 8;
		left = Math.max(8, Math.min(left, vw - pw - 8));
		top  = Math.max(8, top);
		$popup.css({ top: top, left: left });
	}

	function show_popup(student, x, y) {
		frappe.call({
			method: 'slcm.slcm.page.examination_result.examination_result.get_student_hover_info',
			args: { student: student, course: S.course },
			callback: function (r) {
				var s = r.message || {};
				if (S.popup_student !== student) return; // stale

				function prow(lbl, val) {
					if (!val && val !== 0) return '';
					return '<div class="er2-pop-row">' +
						'<span class="er2-pop-lbl">' + lbl + '</span>' +
						'<span class="er2-pop-val">' + frappe.utils.escape_html(String(val)) + '</span>' +
						'</div>';
				}

				// ── Student info section ──
				var infoHtml =
					prow('Student ID',   s.registration_id) +
					prow('Email',        s.email) +
					prow('Programme',    s.programme) +
					prow('Batch',        s.batch) +
					prow('Department',   s.department) +
					prow('Term',         s.current_term) +
					prow('Section',      s.section);

				$popup.html(
					'<div class="er2-pop-head">' +
					'<div class="er2-pop-name">' + frappe.utils.escape_html(s.student_name || student) + '</div>' +
					'<div class="er2-pop-sub">' + frappe.utils.escape_html(s.registration_id || '') + '</div>' +
					'</div>' +
					'<div class="er2-pop-body">' + infoHtml + '</div>'
				);
				$popup.css('max-width', '340px');
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

	// ── Institutional Filter Dialog ───────────────────────────────────────────
	function show_inst_filter_dialog(opts) {
		// Working copy of selections (deep copy)
		var sel = {
			programmes:   S.inst_filter.programmes.slice(),
			batches:      S.inst_filter.batches.slice(),
			course_types: S.inst_filter.course_types.slice(),
		};

		var TYPES = [
			{ key: 'programmes',   label: 'Department & Programme',
			  icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
			  items: opts.programmes },
			{ key: 'batches',      label: 'Batch',
			  icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
			  items: opts.batches },
			{ key: 'course_types', label: 'Course Type',
			  icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
			  items: opts.course_types },
		];

		var activeType = 0;

		function count_all() {
			return sel.programmes.length + sel.batches.length + sel.course_types.length;
		}

		function render_types() {
			var html = '';
			TYPES.forEach(function (t, i) {
				var cnt = sel[t.key].length;
				html += '<div class="xif-type' + (i === activeType ? ' active' : '') + '" data-idx="' + i + '">' +
					t.icon + ' ' + t.label +
					(cnt ? '<span class="xif-type-badge">' + cnt + '</span>' : '') +
					'</div>';
			});
			$modal.find('.xif-types').html(html);
			$modal.find('.xif-type').on('click', function () {
				activeType = parseInt($(this).data('idx'));
				render_types();
				render_panel();
			});
		}

		function render_panel(search_val) {
			var t     = TYPES[activeType];
			var items = (t.items || []).filter(function (v) {
				return !search_val || String(v).toLowerCase().includes(search_val.toLowerCase());
			});
			$modal.find('.xif-ph-title').text(t.label);
			var html = '';
			if (!items.length) {
				html = '<div class="xif-empty-opts">No options available</div>';
			} else {
				items.forEach(function (v) {
					var checked = sel[t.key].indexOf(String(v)) !== -1;
					html += '<div class="xif-opt' + (checked ? ' checked' : '') + '" data-val="' + frappe.utils.escape_html(String(v)) + '">' +
						'<input type="checkbox"' + (checked ? ' checked' : '') + '>' +
						'<span>' + frappe.utils.escape_html(String(v)) + '</span>' +
						'</div>';
				});
			}
			$modal.find('.xif-opts').html(html);
			$modal.find('.xif-opt').on('click', function (e) {
				e.preventDefault();
				var val = $(this).data('val');
				var key = TYPES[activeType].key;
				var idx = sel[key].indexOf(String(val));
				if (idx === -1) sel[key].push(String(val));
				else            sel[key].splice(idx, 1);
				render_types();
				render_panel($modal.find('.xif-search').val());
				update_footer();
			});
		}

		function update_footer() {
			var total = count_all();
			var parts = [];
			if (sel.programmes.length)   parts.push(sel.programmes.length + ' Programme(s)');
			if (sel.batches.length)      parts.push(sel.batches.length + ' Batch(es)');
			if (sel.course_types.length) parts.push(sel.course_types.length + ' Course Type(s)');
			$modal.find('.xif-status').html(
				total ? '<strong>' + total + ' filter' + (total > 1 ? 's' : '') + '</strong> selected: ' + parts.join(', ')
				      : 'No Filters Applied'
			);
		}

		// Build modal HTML
		var $overlay = $('<div class="xif-overlay"></div>');
		var $modal = $(`
			<div class="xif-modal">
				<div class="xif-header">
					<span class="xif-title">
						<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2.5" style="vertical-align:-3px;margin-right:6px;"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
						Filter by
					</span>
					<button class="xif-close">&#10005;</button>
				</div>
				<div class="xif-body">
					<div class="xif-types"></div>
					<div class="xif-panel">
						<div class="xif-ph">
							<div class="xif-ph-title"></div>
							<input class="xif-search" type="text" placeholder="Search…">
						</div>
						<div class="xif-opts"></div>
					</div>
				</div>
				<div class="xif-footer">
					<span class="xif-status">No Filters Applied</span>
					<div class="xif-actions">
						<button class="xif-clear">Clear All</button>
						<button class="xif-apply">Apply</button>
					</div>
				</div>
			</div>
		`);

		$overlay.append($modal);
		$('body').append($overlay);

		render_types();
		render_panel();
		update_footer();

		// Search
		$modal.find('.xif-search').on('input', function () {
			render_panel($(this).val());
		});

		// Clear all
		$modal.find('.xif-clear').on('click', function () {
			sel.programmes   = [];
			sel.batches      = [];
			sel.course_types = [];
			render_types();
			render_panel($modal.find('.xif-search').val());
			update_footer();
		});

		// Apply
		$modal.find('.xif-apply').on('click', function () {
			S.inst_filter = { programmes: sel.programmes, batches: sel.batches, course_types: sel.course_types };
			S.page = 1;
			// Update button badge
			var total = count_all();
			var $btn = $body.find('#er2-inst-filter');
			if (total) {
				$btn.addClass('xif-btn-active').find('.xif-count').remove();
				$btn.append('<span class="xif-count" style="background:#4f46e5;color:#fff;border-radius:20px;font-size:10px;font-weight:700;padding:1px 6px;margin-left:4px;">' + total + '</span>');
			} else {
				$btn.removeClass('xif-btn-active').find('.xif-count').remove();
			}
			$overlay.remove();
			load_students();
		});

		// Close
		$modal.find('.xif-close').on('click', function () { $overlay.remove(); });
		$overlay.on('click', function (e) {
			if ($(e.target).is($overlay)) $overlay.remove();
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────
	function hide_detail() {
		$info.hide().empty();
		$actbar.hide();
		$filterrow.hide();
		$statsPanel.hide().empty();
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
