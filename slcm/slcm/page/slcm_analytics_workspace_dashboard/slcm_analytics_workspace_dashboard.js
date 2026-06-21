// Copyright (c) 2026, TFSS and contributors
// SLCM Analytics Workspace Dashboard — Personalized, workspace-driven analytics
'use strict';

frappe.pages['slcm-analytics-workspace-dashboard'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'SLCM Analytics Workspace Dashboard',
		single_column: true,
	});
	new SLCMWorkspaceAnalyticsDashboard(wrapper);
};

// ── Palette & constants ───────────────────────────────────────────────────────

const SAWD_PALETTE = {
	primary:   ['#1e3a8a', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe'],
	success:   ['#065f46', '#059669', '#10b981', '#34d399', '#6ee7b7', '#a7f3d0'],
	warning:   ['#92400e', '#d97706', '#f59e0b', '#fbbf24', '#fcd34d', '#fde68a'],
	danger:    ['#7f1d1d', '#dc2626', '#ef4444', '#f87171', '#fca5a5', '#fee2e2'],
	info:      ['#164e63', '#0891b2', '#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc'],
	neutral:   ['#0f172a', '#1e293b', '#334155', '#475569', '#64748b', '#94a3b8'],
	mixed:     ['#1e3a8a','#059669','#d97706','#dc2626','#0891b2','#7c3aed','#db2777','#ea580c'],
	status: {
		'Active':         '#059669',
		'Inactive':       '#94a3b8',
		'Graduated':      '#1e3a8a',
		'Dropped':        '#dc2626',
		'Dormant':        '#d97706',
		'Present':        '#059669',
		'Absent':         '#dc2626',
		'OD':             '#d97706',
		'Paid':           '#059669',
		'Unpaid':         '#dc2626',
		'Partially Paid': '#d97706',
		'Accepted':       '#059669',
		'Rejected':       '#dc2626',
		'Pending':        '#d97706',
	},
};

const SAWD_PAGE_METHOD = 'slcm.slcm.page.slcm_analytics_workspace_dashboard.slcm_analytics_workspace_dashboard';

// Module metadata (icon + label for config panel)
const SAWD_MODULE_META = {
	overview:    { icon: '📊', label: 'Overview',    desc: 'Institution-wide KPI summary' },
	admission:   { icon: '🎯', label: 'Admission',   desc: 'Application pipeline & offers' },
	students:    { icon: '🎓', label: 'Students',    desc: 'Enrollment & demographics' },
	programme:   { icon: '📚', label: 'Programme',   desc: 'Programs, cohorts & offerings' },
	attendance:  { icon: '📋', label: 'Attendance',  desc: 'Session records & trends' },
	examination: { icon: '📝', label: 'Examination', desc: 'Exams, marks & results' },
	fees:        { icon: '💰', label: 'Fees',        desc: 'Collection, invoices & trends' },
	hostel:      { icon: '🏠', label: 'Hostel',      desc: 'Occupancy & complaints' },
	placement:   { icon: '💼', label: 'Placement',   desc: 'Opportunities & offer pipeline' },
	idcard:      { icon: '🪪', label: 'ID Card',     desc: 'Card generation & issuance' },
	venue:       { icon: '🏛️', label: 'Venue',       desc: 'Booking requests & usage' },
	promotion:   { icon: '🎖️', label: 'Promotion',   desc: 'Criteria checks & outcomes' },
	ticketing:   { icon: '🎫', label: 'Ticketing',   desc: 'Support tickets & SLA' },
};

// Examination module: 3 inner workspace sub-tabs
const SAWD_EXAM_SUBTABS = [
	{ key: 'exam_planner',  label: 'Exam Planner',          icon: '📅', workspace: 'Exam Planner' },
	{ key: 'transcript',    label: 'Transcript Management',  icon: '📄', workspace: 'Transcript Management' },
	{ key: 'exam_result',   label: 'Exam Result',            icon: '🏆', workspace: 'Exam Result' },
];

// ── Utility helpers ───────────────────────────────────────────────────────────

const sawd_fmt_number = (n) => {
	if (n == null || isNaN(n)) return '—';
	if (n >= 1_00_00_000) return (n / 1_00_00_000).toFixed(1) + 'Cr';
	if (n >= 1_00_000)    return (n / 1_00_000).toFixed(1) + 'L';
	if (n >= 1_000)       return (n / 1_000).toFixed(1) + 'K';
	return String(Math.round(n));
};

const sawd_fmt_currency = (n) => {
	if (n == null || isNaN(n)) return '₹—';
	if (n >= 1_00_00_000) return '₹' + (n / 1_00_00_000).toFixed(2) + 'Cr';
	if (n >= 1_00_000)    return '₹' + (n / 1_00_000).toFixed(2) + 'L';
	if (n >= 1_000)       return '₹' + (n / 1_000).toFixed(1) + 'K';
	return '₹' + n.toLocaleString('en-IN');
};

const sawd_status_color = (label) =>
	SAWD_PALETTE.status[label] || SAWD_PALETTE.mixed[Math.abs((label || '').charCodeAt(0)) % SAWD_PALETTE.mixed.length];

const sawd_labels_and_values = (data, lk = 'label', vk = 'value') => ({
	labels:   (data || []).map(r => r[lk] || 'Unknown'),
	datasets: [{ values: (data || []).map(r => r[vk] || 0) }],
});

const sawd_rate_badge = (rate) => {
	const cls = rate >= 75 ? 'badge-success' : rate >= 50 ? 'badge-warning' : 'badge-danger';
	return `<span class="sawd-rate-badge ${cls}">${rate}%</span>`;
};

// ── Main Dashboard Class ──────────────────────────────────────────────────────

class SLCMWorkspaceAnalyticsDashboard {
	constructor(wrapper) {
		this.$wrapper = $(wrapper);
		this.$body    = this.$wrapper.find('.page-content');
		this.$body.css({ padding: 0, background: 'var(--sawd-bg)' });

		this.filters          = { academic_year: null, term: null, program: null, cohort: null, student_status: null };
		this.active_tab       = 'overview';
		this.active_exam_subtab = 'exam_planner';
		this.workspace_modules = [];   // [{key, label, icon, enabled, available}, ...]
		this._filter_options  = null;
		this._drilldown_open  = false;
		this._config_open     = false;

		this._inject_styles();
		this._build_skeleton();
		this._load_workspace_config();
	}

	// ── Styles ────────────────────────────────────────────────────────────────

	_inject_styles() {
		if ($('#sawd-styles').length) return;
		$(`<style id="sawd-styles">
		/* ── Design tokens ───────────────────────────────────────────── */
		:root {
			--sawd-bg:        #f0f4f8;
			--sawd-surface:   #ffffff;
			--sawd-surface2:  #f8fafc;
			--sawd-border:    #e2e8f0;
			--sawd-primary:   #1e3a8a;
			--sawd-primary-l: #2563eb;
			--sawd-primary-xl:#dbeafe;
			--sawd-success:   #059669;
			--sawd-warning:   #d97706;
			--sawd-danger:    #dc2626;
			--sawd-info:      #0891b2;
			--sawd-purple:    #7c3aed;
			--sawd-text1:     #0f172a;
			--sawd-text2:     #334155;
			--sawd-text3:     #64748b;
			--sawd-text4:     #94a3b8;
			--sawd-radius:    14px;
			--sawd-radius-sm: 8px;
			--sawd-shadow:    0 1px 4px rgba(15,23,42,.08), 0 4px 16px rgba(15,23,42,.06);
			--sawd-shadow-lg: 0 8px 32px rgba(15,23,42,.14);
			--sawd-transition: all .22s cubic-bezier(.4,0,.2,1);
		}

		/* ── Page layout ─────────────────────────────────────────────── */
		.sawd-page { padding:20px 24px 80px; min-height:100vh; }

		/* ── Header ──────────────────────────────────────────────────── */
		.sawd-header {
			display:flex; align-items:center; gap:16px; margin-bottom:20px;
		}
		.sawd-header-icon {
			width:52px; height:52px; border-radius:14px; flex-shrink:0;
			background:linear-gradient(135deg,#1e3a8a,#3b5bdb);
			display:flex; align-items:center; justify-content:center;
			color:#fff; font-size:22px;
			box-shadow:0 4px 14px rgba(30,58,138,.4);
		}
		.sawd-header-text .sawd-suptitle {
			font-size:10px; font-weight:700; text-transform:uppercase;
			letter-spacing:.8px; color:var(--sawd-text3);
		}
		.sawd-header-text .sawd-title {
			font-size:22px; font-weight:800; color:var(--sawd-text1); line-height:1.15;
			letter-spacing:-.4px;
		}
		.sawd-header-right { margin-left:auto; display:flex; align-items:center; gap:10px; }
		.sawd-last-updated { font-size:11px; color:var(--sawd-text4); }

		/* ── Buttons ─────────────────────────────────────────────────── */
		.sawd-btn {
			padding:7px 16px; border-radius:7px; font-size:13px; font-weight:600;
			cursor:pointer; border:1px solid transparent; transition:var(--sawd-transition);
			display:inline-flex; align-items:center; gap:6px;
		}
		.sawd-btn-primary  { background:var(--sawd-primary); color:#fff; border-color:var(--sawd-primary); }
		.sawd-btn-primary:hover { background:#1e40af; }
		.sawd-btn-ghost    { background:transparent; color:var(--sawd-text3); border-color:var(--sawd-border); }
		.sawd-btn-ghost:hover  { background:var(--sawd-surface2); color:var(--sawd-text1); }
		.sawd-btn-configure {
			display:flex; align-items:center; gap:6px;
			padding:8px 16px; border-radius:8px; border:1px solid var(--sawd-border);
			background:var(--sawd-surface); color:var(--sawd-text2);
			font-size:13px; font-weight:600; cursor:pointer;
			transition:var(--sawd-transition);
		}
		.sawd-btn-configure:hover { background:var(--sawd-primary); color:#fff; border-color:var(--sawd-primary); }
		.sawd-refresh-btn {
			display:flex; align-items:center; gap:6px;
			padding:8px 16px; border-radius:8px; border:1px solid var(--sawd-border);
			background:var(--sawd-surface); color:var(--sawd-text2);
			font-size:13px; font-weight:600; cursor:pointer; transition:var(--sawd-transition);
		}
		.sawd-refresh-btn:hover { background:var(--sawd-primary); color:#fff; border-color:var(--sawd-primary); }

		/* ── Workspace badge strip ───────────────────────────────────── */
		.sawd-ws-badge-strip {
			display:flex; align-items:center; gap:6px; flex-wrap:wrap;
			margin-bottom:16px;
		}
		.sawd-ws-badge-label {
			font-size:11px; font-weight:700; text-transform:uppercase;
			letter-spacing:.6px; color:var(--sawd-text3); margin-right:4px;
		}
		.sawd-ws-badge {
			display:inline-flex; align-items:center; gap:4px;
			padding:3px 10px; border-radius:20px;
			background:var(--sawd-primary-xl); color:var(--sawd-primary);
			font-size:11px; font-weight:600; border:1px solid #bfdbfe;
		}

		/* ── Filter bar ──────────────────────────────────────────────── */
		.sawd-filter-bar {
			background:var(--sawd-surface); border-radius:var(--sawd-radius);
			border:1px solid var(--sawd-border); border-left:4px solid var(--sawd-primary);
			padding:16px 20px; margin-bottom:20px; box-shadow:var(--sawd-shadow);
			display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap;
		}
		.sawd-filter-group { display:flex; flex-direction:column; gap:4px; flex:1; min-width:160px; }
		.sawd-filter-label {
			font-size:10px; font-weight:700; text-transform:uppercase;
			letter-spacing:.6px; color:var(--sawd-text3);
		}
		.sawd-filter-actions { display:flex; gap:8px; align-items:flex-end; padding-bottom:2px; }

		/* ── Tab navigation ──────────────────────────────────────────── */
		.sawd-tabs {
			display:flex; gap:4px; flex-wrap:wrap;
			background:var(--sawd-surface); border-radius:var(--sawd-radius);
			padding:6px; margin-bottom:20px;
			border:1px solid var(--sawd-border); box-shadow:var(--sawd-shadow);
		}
		.sawd-tab {
			display:flex; align-items:center; gap:7px;
			padding:8px 16px; border-radius:9px; font-size:13px; font-weight:600;
			color:var(--sawd-text3); cursor:pointer;
			transition:var(--sawd-transition); user-select:none; border:1px solid transparent;
		}
		.sawd-tab:hover { color:var(--sawd-primary); background:var(--sawd-primary-xl); }
		.sawd-tab.active {
			background:var(--sawd-primary); color:#fff;
			box-shadow:0 2px 8px rgba(30,58,138,.3);
		}
		.sawd-tab .tab-icon { font-size:14px; }
		.sawd-tabs-empty {
			padding:10px 14px; font-size:13px; color:var(--sawd-text4);
			font-style:italic;
		}

		/* ── KPI grid ────────────────────────────────────────────────── */
		.sawd-kpi-grid {
			display:grid; grid-template-columns:repeat(auto-fill, minmax(200px,1fr));
			gap:14px; margin-bottom:20px;
		}
		.sawd-kpi-card {
			background:var(--sawd-surface); border-radius:var(--sawd-radius);
			padding:20px; border:1px solid var(--sawd-border);
			box-shadow:var(--sawd-shadow); position:relative; overflow:hidden;
			transition:var(--sawd-transition);
		}
		.sawd-kpi-card:hover { transform:translateY(-2px); box-shadow:var(--sawd-shadow-lg); }
		.sawd-kpi-card.has-drilldown { cursor:pointer; }
		.sawd-kpi-accent {
			position:absolute; top:0; left:0; right:0; height:3px;
			border-radius:var(--sawd-radius) var(--sawd-radius) 0 0;
		}
		.sawd-kpi-icon { width:40px; height:40px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:18px; margin-bottom:12px; }
		.sawd-kpi-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; color:var(--sawd-text3); margin-bottom:6px; }
		.sawd-kpi-value { font-size:28px; font-weight:800; color:var(--sawd-text1); line-height:1; letter-spacing:-.5px; margin-bottom:4px; }
		.sawd-kpi-sub   { font-size:12px; color:var(--sawd-text3); }
		.sawd-kpi-drill-hint { font-size:10px; color:var(--sawd-text4); margin-top:6px; }
		.kpi-primary .sawd-kpi-accent { background:var(--sawd-primary); }
		.kpi-primary .sawd-kpi-icon   { background:#dbeafe; color:var(--sawd-primary); }
		.kpi-success .sawd-kpi-accent { background:var(--sawd-success); }
		.kpi-success .sawd-kpi-icon   { background:#d1fae5; color:var(--sawd-success); }
		.kpi-warning .sawd-kpi-accent { background:var(--sawd-warning); }
		.kpi-warning .sawd-kpi-icon   { background:#fef3c7; color:var(--sawd-warning); }
		.kpi-danger  .sawd-kpi-accent { background:var(--sawd-danger); }
		.kpi-danger  .sawd-kpi-icon   { background:#fee2e2; color:var(--sawd-danger); }
		.kpi-info    .sawd-kpi-accent { background:var(--sawd-info); }
		.kpi-info    .sawd-kpi-icon   { background:#cffafe; color:var(--sawd-info); }
		.kpi-purple  .sawd-kpi-accent { background:var(--sawd-purple); }
		.kpi-purple  .sawd-kpi-icon   { background:#ede9fe; color:var(--sawd-purple); }

		/* ── Chart grid ──────────────────────────────────────────────── */
		.sawd-chart-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; margin-bottom:16px; }
		.sawd-chart-wide { grid-column:1/-1; }
		.sawd-chart-card {
			background:var(--sawd-surface); border-radius:var(--sawd-radius);
			border:1px solid var(--sawd-border); box-shadow:var(--sawd-shadow);
			overflow:hidden;
		}
		.sawd-chart-header { padding:16px 18px 12px; border-bottom:1px solid var(--sawd-border); display:flex; align-items:flex-start; gap:10px; }
		.sawd-chart-title  { font-size:14px; font-weight:700; color:var(--sawd-text1); }
		.sawd-chart-subtitle { font-size:11px; color:var(--sawd-text3); margin-top:2px; }
		.sawd-chart-body   { padding:12px 14px; min-height:200px; }
		.sawd-chart-tip    { padding:8px 16px; font-size:11px; color:var(--sawd-text4); border-top:1px solid var(--sawd-border); }
		.sawd-chart-badge  { margin-left:auto; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; background:var(--sawd-primary-xl); color:var(--sawd-primary); white-space:nowrap; }

		/* ── Section separator ───────────────────────────────────────── */
		.sawd-section-title {
			font-size:13px; font-weight:700; color:var(--sawd-text3);
			text-transform:uppercase; letter-spacing:.6px;
			margin:24px 0 12px; display:flex; align-items:center; gap:8px;
		}
		.sawd-section-title::after { content:''; flex:1; height:1px; background:var(--sawd-border); }

		/* ── Progress bars ───────────────────────────────────────────── */
		.sawd-progress-list { padding:4px 0; }
		.sawd-progress-item { margin-bottom:10px; }
		.sawd-progress-label { display:flex; justify-content:space-between; margin-bottom:4px; font-size:12px; }
		.sawd-progress-name  { color:var(--sawd-text2); font-weight:500; }
		.sawd-progress-val   { color:var(--sawd-text1); font-weight:700; }
		.sawd-progress-track { height:8px; background:var(--sawd-surface2); border-radius:4px; overflow:hidden; }
		.sawd-progress-fill  { height:100%; border-radius:4px; transition:width .6s cubic-bezier(.4,0,.2,1); }
		.sawd-rate-badge { padding:2px 7px; border-radius:5px; font-size:11px; font-weight:700; }
		.badge-success { background:#d1fae5; color:#065f46; }
		.badge-warning { background:#fef3c7; color:#92400e; }
		.badge-danger  { background:#fee2e2; color:#7f1d1d; }

		/* ── Funnel & horizontal bars ────────────────────────────────── */
		.sawd-funnel { display:flex; flex-direction:column; gap:6px; padding:4px 0; }
		.sawd-funnel-step { display:flex; align-items:center; gap:12px; cursor:pointer; }
		.sawd-funnel-bar-wrap { flex:1; height:36px; background:var(--sawd-surface2); border-radius:6px; overflow:hidden; position:relative; }
		.sawd-funnel-bar { height:100%; border-radius:6px; display:flex; align-items:center; padding-left:12px; transition:width .6s cubic-bezier(.4,0,.2,1); min-width:30px; }
		.sawd-funnel-bar-label { font-size:12px; font-weight:700; color:#fff; white-space:nowrap; text-shadow:0 1px 2px rgba(0,0,0,.3); }
		.sawd-funnel-meta  { text-align:right; min-width:60px; font-size:12px; font-weight:700; color:var(--sawd-text2); }
		.sawd-funnel-name  { min-width:120px; font-size:12px; color:var(--sawd-text2); font-weight:600; }

		/* ── Gauge ───────────────────────────────────────────────────── */
		.sawd-gauge-wrap { text-align:center; padding:20px 0; }
		.sawd-gauge-ring { width:140px; height:140px; margin:0 auto 12px; position:relative; }
		.sawd-gauge-ring svg { width:100%; height:100%; transform:rotate(-90deg); }
		.sawd-gauge-bg   { fill:none; stroke:#f1f5f9; stroke-width:14; }
		.sawd-gauge-fill { fill:none; stroke-width:14; stroke-linecap:round; transition:stroke-dasharray .8s cubic-bezier(.4,0,.2,1); }
		.sawd-gauge-text { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }
		.sawd-gauge-pct  { font-size:26px; font-weight:800; color:var(--sawd-text1); }
		.sawd-gauge-lbl  { font-size:10px; color:var(--sawd-text3); font-weight:600; text-transform:uppercase; }

		/* ── Summary card (fees) ─────────────────────────────────────── */
		.sawd-summary-card {
			background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 100%);
			border-radius:var(--sawd-radius); padding:22px 24px;
			color:#fff; margin-bottom:16px; position:relative; overflow:hidden;
		}
		.sawd-summary-card::before { content:''; position:absolute; right:-20px; top:-30px; width:160px; height:160px; border-radius:50%; background:rgba(255,255,255,.06); }
		.sawd-sc-grid  { display:grid; grid-template-columns:repeat(3,1fr); gap:20px; }
		.sawd-sc-item .sc-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.6px; opacity:.7; margin-bottom:6px; }
		.sawd-sc-item .sc-value { font-size:24px; font-weight:800; letter-spacing:-.5px; }
		.sawd-sc-item .sc-sub   { font-size:11px; opacity:.65; margin-top:3px; }

		/* ── Tables ──────────────────────────────────────────────────── */
		.sawd-table-wrap { overflow-x:auto; }
		.sawd-table { width:100%; border-collapse:collapse; font-size:13px; }
		.sawd-table thead tr { border-bottom:2px solid var(--sawd-border); }
		.sawd-table thead th { padding:10px 12px; text-align:left; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; color:var(--sawd-text3); white-space:nowrap; }
		.sawd-table tbody tr { border-bottom:1px solid var(--sawd-border); transition:var(--sawd-transition); }
		.sawd-table tbody tr.sawd-row-link { cursor:pointer; }
		.sawd-table tbody tr.sawd-row-link:hover { background:var(--sawd-surface2); }
		.sawd-table tbody td { padding:9px 12px; color:var(--sawd-text2); vertical-align:middle; }
		.sawd-table tbody td:first-child { font-weight:600; color:var(--sawd-text1); }

		/* ── Pagination ──────────────────────────────────────────────── */
		.sawd-pagination { display:flex; align-items:center; justify-content:space-between; padding:12px 0; margin-top:12px; font-size:12px; color:var(--sawd-text3); }
		.sawd-page-btns  { display:flex; gap:6px; }
		.sawd-page-btn   { padding:5px 12px; border-radius:6px; border:1px solid var(--sawd-border); background:var(--sawd-surface); cursor:pointer; font-size:12px; font-weight:600; color:var(--sawd-text2); transition:var(--sawd-transition); }
		.sawd-page-btn:hover:not(:disabled) { background:var(--sawd-primary); color:#fff; border-color:var(--sawd-primary); }
		.sawd-page-btn:disabled { opacity:.4; cursor:not-allowed; }
		.sawd-page-size-wrap { display:flex; align-items:center; gap:6px; }
		.sawd-page-size-select { padding:4px 8px; border-radius:6px; border:1px solid var(--sawd-border); background:var(--sawd-surface); font-size:12px; font-weight:600; cursor:pointer; }

		/* ── Skeleton loaders ────────────────────────────────────────── */
		@keyframes sawd-shimmer { 0%,100%{opacity:1} 50%{opacity:.4} }
		.sawd-skeleton { background:var(--sawd-border); border-radius:8px; animation:sawd-shimmer 1.5s ease infinite; }
		.sawd-skeleton-kpi   { height:130px; }
		.sawd-skeleton-chart { height:240px; }

		/* ── Empty / error ───────────────────────────────────────────── */
		.sawd-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 20px; color:var(--sawd-text4); }
		.sawd-empty-icon  { font-size:36px; margin-bottom:12px; opacity:.5; }
		.sawd-empty-title { font-size:14px; font-weight:600; color:var(--sawd-text3); }
		.sawd-empty-sub   { font-size:12px; margin-top:4px; }

		/* ── Export / viewlist buttons ───────────────────────────────── */
		.sawd-export-btn  { display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:7px; font-size:12px; font-weight:600; border:1px solid var(--sawd-border); background:var(--sawd-surface); color:var(--sawd-text2); cursor:pointer; transition:var(--sawd-transition); }
		.sawd-export-btn:hover { background:var(--sawd-success); color:#fff; border-color:var(--sawd-success); }
		.sawd-viewlist-btn { display:inline-flex; align-items:center; gap:6px; padding:6px 14px; border-radius:7px; font-size:12px; font-weight:600; border:1px solid var(--sawd-primary); background:var(--sawd-primary); color:#fff; cursor:pointer; transition:var(--sawd-transition); }
		.sawd-viewlist-btn:hover { opacity:.85; }
		.sawd-viewlist-btn:disabled { opacity:.35; cursor:not-allowed; }

		/* ── Drilldown panel ─────────────────────────────────────────── */
		.sawd-drilldown-overlay {
			position:fixed; inset:0; background:rgba(15,23,42,.35);
			backdrop-filter:blur(2px); z-index:999; opacity:0; pointer-events:none;
			transition:opacity .25s ease;
		}
		.sawd-drilldown-overlay.open { opacity:1; pointer-events:all; }
		.sawd-drilldown-panel {
			position:fixed; top:0; right:-680px; width:640px; max-width:95vw; height:100vh;
			background:var(--sawd-surface); box-shadow:var(--sawd-shadow-lg);
			z-index:1000; display:flex; flex-direction:column;
			transition:right .3s cubic-bezier(.4,0,.2,1);
		}
		.sawd-drilldown-panel.open { right:0; }
		.sawd-drilldown-header { display:flex; align-items:center; gap:12px; padding:16px 20px; border-bottom:1px solid var(--sawd-border); flex-shrink:0; }
		.sawd-drilldown-title  { font-size:16px; font-weight:700; color:var(--sawd-text1); }
		.sawd-drilldown-breadcrumb { font-size:11px; color:var(--sawd-text4); margin-top:2px; }
		.sawd-drilldown-close  { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--sawd-border); background:var(--sawd-surface2); cursor:pointer; font-size:16px; display:flex; align-items:center; justify-content:center; transition:var(--sawd-transition); }
		.sawd-drilldown-close:hover { background:var(--sawd-danger); color:#fff; border-color:var(--sawd-danger); }
		.sawd-drilldown-body   { flex:1; overflow-y:auto; padding:16px 20px; }
		.sawd-drilldown-stats  { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:16px; }
		.sawd-drilldown-stat   { background:var(--sawd-surface2); border-radius:10px; padding:12px; text-align:center; border:1px solid var(--sawd-border); }
		.dds-value { font-size:22px; font-weight:800; color:var(--sawd-primary); }
		.dds-label { font-size:11px; color:var(--sawd-text3); margin-top:2px; }
		.sawd-dd-search-bar  { padding:12px 24px 8px; flex-shrink:0; border-bottom:1px solid var(--sawd-border); display:flex; align-items:center; gap:10px; }
		.sawd-dd-search-wrap { flex:1; position:relative; }
		.sawd-dd-search-icon { position:absolute; left:11px; top:50%; transform:translateY(-50%); color:var(--sawd-text3); font-size:13px; pointer-events:none; }
		.sawd-dd-search-input { width:100%; padding:7px 12px 7px 32px; border:1.5px solid var(--sawd-border); border-radius:8px; font-size:13px; color:var(--sawd-text1); background:var(--sawd-surface2); outline:none; transition:var(--sawd-transition); }
		.sawd-dd-search-input:focus { border-color:var(--sawd-primary); background:var(--sawd-surface); }
		.sawd-dd-search-clear { position:absolute; right:9px; top:50%; transform:translateY(-50%); background:none; border:none; cursor:pointer; color:var(--sawd-text3); font-size:14px; padding:2px 4px; display:none; }
		.sawd-dd-search-count { font-size:11px; color:var(--sawd-text3); white-space:nowrap; min-width:80px; text-align:right; }

		/* ── ✦ Configuration Drawer ──────────────────────────────────── */
		.sawd-config-overlay {
			position:fixed; inset:0; background:rgba(15,23,42,.4);
			backdrop-filter:blur(3px); z-index:1100; opacity:0; pointer-events:none;
			transition:opacity .25s ease;
		}
		.sawd-config-overlay.open { opacity:1; pointer-events:all; }
		.sawd-config-panel {
			position:fixed; top:0; left:-520px; width:480px; max-width:92vw; height:100vh;
			background:var(--sawd-surface); box-shadow:var(--sawd-shadow-lg);
			z-index:1101; display:flex; flex-direction:column;
			transition:left .3s cubic-bezier(.4,0,.2,1);
		}
		.sawd-config-panel.open { left:0; }
		.sawd-config-header {
			padding:20px 24px 16px; border-bottom:1px solid var(--sawd-border); flex-shrink:0;
			background:linear-gradient(135deg,#1e3a8a,#2563eb); color:#fff;
		}
		.sawd-config-header-top { display:flex; align-items:center; justify-content:space-between; }
		.sawd-config-title { font-size:18px; font-weight:800; letter-spacing:-.3px; }
		.sawd-config-subtitle { font-size:12px; opacity:.75; margin-top:4px; }
		.sawd-config-close {
			width:32px; height:32px; border-radius:8px; border:1px solid rgba(255,255,255,.3);
			background:rgba(255,255,255,.1); cursor:pointer; font-size:16px;
			display:flex; align-items:center; justify-content:center;
			color:#fff; transition:var(--sawd-transition);
		}
		.sawd-config-close:hover { background:rgba(255,255,255,.2); }
		.sawd-config-body { flex:1; overflow-y:auto; padding:20px 24px; }
		.sawd-config-section-label {
			font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.7px;
			color:var(--sawd-text3); margin-bottom:10px; margin-top:4px;
		}
		.sawd-config-module-list { display:flex; flex-direction:column; gap:8px; margin-bottom:20px; }
		.sawd-config-module-item {
			display:flex; align-items:center; gap:12px;
			padding:12px 14px; border-radius:10px; border:1.5px solid var(--sawd-border);
			background:var(--sawd-surface2); cursor:pointer; transition:var(--sawd-transition);
			position:relative;
		}
		.sawd-config-module-item:hover { border-color:var(--sawd-primary-l); background:#fff; }
		.sawd-config-module-item.is-enabled { border-color:var(--sawd-primary); background:var(--sawd-primary-xl); }
		.sawd-config-module-item.is-locked { opacity:.45; cursor:not-allowed; }
		.sawd-config-module-icon { font-size:22px; flex-shrink:0; width:36px; text-align:center; }
		.sawd-config-module-info { flex:1; min-width:0; }
		.sawd-config-module-name { font-size:14px; font-weight:700; color:var(--sawd-text1); }
		.sawd-config-module-desc { font-size:11px; color:var(--sawd-text3); margin-top:2px; }
		.sawd-config-module-toggle {
			width:40px; height:22px; border-radius:11px; border:none; cursor:pointer;
			position:relative; transition:background .2s; flex-shrink:0;
			background:var(--sawd-border);
		}
		.sawd-config-module-toggle.on { background:var(--sawd-primary); }
		.sawd-config-module-toggle::after {
			content:''; position:absolute; top:3px; left:3px;
			width:16px; height:16px; border-radius:50%; background:#fff;
			transition:transform .2s; box-shadow:0 1px 3px rgba(0,0,0,.2);
		}
		.sawd-config-module-toggle.on::after { transform:translateX(18px); }
		.sawd-config-module-item.is-locked .sawd-config-module-toggle { background:var(--sawd-border); opacity:.5; }
		.sawd-config-ws-tag {
			font-size:10px; color:var(--sawd-text4); margin-top:3px;
			display:flex; align-items:center; gap:3px;
		}
		.sawd-config-footer {
			padding:16px 24px; border-top:1px solid var(--sawd-border); flex-shrink:0;
			display:flex; gap:10px; background:var(--sawd-surface);
		}
		.sawd-config-save-btn {
			flex:1; padding:10px; border-radius:8px; border:none;
			background:var(--sawd-primary); color:#fff; font-size:14px; font-weight:700;
			cursor:pointer; transition:var(--sawd-transition);
		}
		.sawd-config-save-btn:hover { background:#1e40af; }
		.sawd-config-cancel-btn {
			padding:10px 20px; border-radius:8px; border:1px solid var(--sawd-border);
			background:var(--sawd-surface); color:var(--sawd-text2); font-size:14px; font-weight:600;
			cursor:pointer; transition:var(--sawd-transition);
		}
		.sawd-config-cancel-btn:hover { background:var(--sawd-surface2); }
		.sawd-config-select-all { font-size:12px; color:var(--sawd-primary-l); cursor:pointer; font-weight:600; text-decoration:underline; }

		/* ── Workspace quick-links bar ───────────────────────────────── */
		.sawd-ws-shortcut-bar {
			display:flex; align-items:center; gap:0; flex-wrap:wrap;
			margin-bottom:16px; padding:0;
			background:var(--sawd-surface); border-radius:var(--sawd-radius-sm);
			border:1px solid var(--sawd-border);
			box-shadow:var(--sawd-shadow);
			overflow:hidden;
		}
		.sawd-ws-sc-header {
			display:flex; align-items:center; gap:6px;
			padding:9px 14px; background:var(--sawd-primary-xl);
			border-right:1px solid var(--sawd-border);
			font-size:10px; font-weight:800; text-transform:uppercase;
			letter-spacing:.7px; color:var(--sawd-primary);
			white-space:nowrap; flex-shrink:0;
		}
		.sawd-ws-sc-list {
			display:flex; align-items:center; gap:4px;
			flex-wrap:wrap; padding:6px 10px; flex:1;
		}
		.sawd-ws-sc-chip {
			display:inline-flex; align-items:center; gap:5px;
			padding:4px 12px; border-radius:6px;
			font-size:12px; font-weight:600;
			color:var(--sawd-text2);
			background:var(--sawd-surface2);
			border:1px solid var(--sawd-border);
			cursor:pointer; text-decoration:none;
			transition:var(--sawd-transition); white-space:nowrap;
		}
		.sawd-ws-sc-chip:hover {
			background:var(--sawd-primary); color:#fff;
			border-color:var(--sawd-primary); text-decoration:none;
		}
		.sawd-ws-sc-chip i { font-size:11px; opacity:.8; }

		/* ── Workspace shortcut action grid (empty-state fallback) ──── */
		.sawd-sc-action-grid {
			display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
			gap:12px; margin-top:4px;
		}
		.sawd-sc-action-card {
			display:flex; align-items:center; gap:14px;
			padding:16px 18px; border-radius:var(--sawd-radius-sm);
			background:var(--sawd-surface); border:1px solid var(--sawd-border);
			box-shadow:var(--sawd-shadow); cursor:pointer;
			transition:var(--sawd-transition); text-decoration:none;
		}
		.sawd-sc-action-card:hover {
			transform:translateY(-2px); box-shadow:var(--sawd-shadow-lg);
			border-color:var(--sawd-primary); background:var(--sawd-primary-xl);
		}
		.sawd-sc-action-icon {
			width:38px; height:38px; border-radius:9px; flex-shrink:0;
			background:var(--sawd-primary-xl); color:var(--sawd-primary);
			display:flex; align-items:center; justify-content:center; font-size:16px;
		}
		.sawd-sc-action-card:hover .sawd-sc-action-icon {
			background:var(--sawd-primary); color:#fff;
		}
		.sawd-sc-action-info { min-width:0; }
		.sawd-sc-action-label {
			font-size:13px; font-weight:700; color:var(--sawd-text1);
			white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
		}
		.sawd-sc-action-type {
			font-size:10px; color:var(--sawd-text3); margin-top:2px;
			font-weight:600; text-transform:uppercase; letter-spacing:.4px;
		}
		.sawd-sc-action-card:hover .sawd-sc-action-label { color:var(--sawd-primary); }

		/* ── Examination inner sub-tabs ──────────────────────────────── */
		.sawd-exam-subtab-bar {
			display:flex; gap:4px; flex-wrap:wrap; align-items:center;
			background:var(--sawd-surface2); border-radius:var(--sawd-radius-sm);
			padding:6px 10px; margin-bottom:16px;
			border:1px solid var(--sawd-border);
			border-left:4px solid #7c3aed;
		}
		.sawd-exam-subtab-label {
			font-size:10px; font-weight:700; text-transform:uppercase;
			letter-spacing:.6px; color:var(--sawd-text3); margin-right:6px; flex-shrink:0;
		}
		.sawd-exam-subtab {
			display:flex; align-items:center; gap:6px;
			padding:6px 14px; border-radius:7px; font-size:12px; font-weight:600;
			color:var(--sawd-text3); cursor:pointer;
			transition:var(--sawd-transition); user-select:none;
			border:1px solid transparent;
		}
		.sawd-exam-subtab:hover { color:#7c3aed; background:#ede9fe; }
		.sawd-exam-subtab.active {
			background:#7c3aed; color:#fff;
			box-shadow:0 2px 8px rgba(124,58,237,.3);
		}
		.sawd-exam-subtab .tab-icon { font-size:13px; }

		/* ── Animations ──────────────────────────────────────────────── */
		@keyframes sawd-fadein { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
		.sawd-animate { animation:sawd-fadein .3s ease; }

		/* ── Responsive ──────────────────────────────────────────────── */
		@media (max-width:768px) {
			.sawd-page  { padding:12px 14px 60px; }
			.sawd-kpi-grid   { grid-template-columns:repeat(2,1fr); }
			.sawd-chart-grid { grid-template-columns:1fr; }
			.sawd-tabs  { overflow-x:auto; flex-wrap:nowrap; }
			.sawd-tab   { flex-shrink:0; }
			.sawd-sc-grid    { grid-template-columns:1fr; }
			.sawd-drilldown-panel { width:100%; }
			.sawd-drilldown-stats { grid-template-columns:1fr 1fr; }
			.sawd-config-panel { width:100%; max-width:100vw; }
		}
		</style>`).appendTo('head');
	}

	// ── Skeleton while loading workspace config ────────────────────────────────

	_build_skeleton() {
		this.$body.html(`
		<div class="sawd-page">
			<div class="sawd-header">
				<div class="sawd-header-icon">🗂️</div>
				<div class="sawd-header-text">
					<div class="sawd-suptitle">Personalized Analytics</div>
					<div class="sawd-title">SLCM Analytics Workspace Dashboard</div>
				</div>
				<div class="sawd-header-right">
					<span class="sawd-last-updated" id="sawd-last-updated"></span>
					<button class="sawd-refresh-btn" id="sawd-refresh" style="display:none">
						<i class="fa fa-refresh"></i> Refresh
					</button>
					<button class="sawd-btn-configure" id="sawd-configure" style="display:none">
						⚙️ Configure Workspace
					</button>
					<button class="sawd-btn-configure" id="sawd-edit-workspace" style="display:none; margin-left: 10px;">
						✏️ Edit Workspace
					</button>
				</div>
			</div>
			<div id="sawd-ws-badges" style="display:none"></div>
			<div id="sawd-filter-bar" style="display:none" class="sawd-filter-bar">
				<div class="sawd-filter-group"><div class="sawd-filter-label">Academic Year</div><div id="sawd-f-ay"></div></div>
				<div class="sawd-filter-group"><div class="sawd-filter-label">Term</div><div id="sawd-f-term"></div></div>
				<div class="sawd-filter-group"><div class="sawd-filter-label">Program</div><div id="sawd-f-prog"></div></div>
				<div class="sawd-filter-group"><div class="sawd-filter-label">Cohort</div><div id="sawd-f-cohort"></div></div>
				<div class="sawd-filter-group"><div class="sawd-filter-label">Student Status</div><div id="sawd-f-sstatus"></div></div>
				<div class="sawd-filter-actions">
					<button class="sawd-btn sawd-btn-primary" id="sawd-apply-filters"><i class="fa fa-filter"></i> Apply</button>
					<button class="sawd-btn sawd-btn-ghost"  id="sawd-reset-filters"><i class="fa fa-times"></i> Reset</button>
				</div>
			</div>
			<div id="sawd-tabs-container"></div>
			<div id="sawd-tab-content">
				<div class="sawd-kpi-grid">
					${Array(4).fill('<div class="sawd-skeleton sawd-skeleton-kpi"></div>').join('')}
				</div>
				<div class="sawd-chart-grid">
					${Array(4).fill('<div class="sawd-skeleton sawd-skeleton-chart"></div>').join('')}
				</div>
			</div>
		</div>

		<!-- Drilldown overlay -->
		<div class="sawd-drilldown-overlay" id="sawd-dd-overlay"></div>
		<div class="sawd-drilldown-panel" id="sawd-dd-panel">
			<div class="sawd-drilldown-header">
				<div>
					<div class="sawd-drilldown-title" id="sawd-dd-title">Detail View</div>
					<div class="sawd-drilldown-breadcrumb" id="sawd-dd-breadcrumb"></div>
				</div>
				<button class="sawd-viewlist-btn" id="sawd-dd-viewlist" style="display:none"><i class="fa fa-list"></i> View List</button>
				<button class="sawd-export-btn"   id="sawd-dd-export"><i class="fa fa-download"></i> Export</button>
				<button class="sawd-drilldown-close" id="sawd-dd-close">✕</button>
			</div>
			<div class="sawd-dd-search-bar">
				<div class="sawd-dd-search-wrap">
					<span class="sawd-dd-search-icon">🔍</span>
					<input type="text" id="sawd-dd-search" class="sawd-dd-search-input" placeholder="Search in results...">
					<button class="sawd-dd-search-clear" id="sawd-dd-search-clear">✕</button>
				</div>
				<span class="sawd-dd-search-count" id="sawd-dd-search-count"></span>
			</div>
			<div class="sawd-drilldown-body" id="sawd-dd-body">
				<div class="sawd-empty"><div class="sawd-empty-icon">📊</div><div class="sawd-empty-title">Click a chart segment to drill down</div></div>
			</div>
		</div>

		<!-- Config drawer -->
		<div class="sawd-config-overlay" id="sawd-config-overlay"></div>
		<div class="sawd-config-panel"   id="sawd-config-panel">
			<div class="sawd-config-header">
				<div class="sawd-config-header-top">
					<div class="sawd-config-title">⚙️ Configure Workspace</div>
					<button class="sawd-config-close" id="sawd-config-close">✕</button>
				</div>
				<div class="sawd-config-subtitle">Choose which analytics modules appear on your dashboard. Changes apply instantly.</div>
			</div>
			<div class="sawd-config-body" id="sawd-config-body">
				<div class="sawd-empty"><div class="sawd-empty-icon">⏳</div><div class="sawd-empty-title">Loading modules…</div></div>
			</div>
			<div class="sawd-config-footer">
				<button class="sawd-config-save-btn"   id="sawd-config-save">✓ Apply Changes</button>
				<button class="sawd-config-cancel-btn" id="sawd-config-cancel">Cancel</button>
			</div>
		</div>
		`);

		this._bind_events();
	}

	// ── Event bindings ────────────────────────────────────────────────────────

	_bind_events() {
		const self = this;

		// Tab switching
		this.$body.on('click', '.sawd-tab', function () {
			const tab = $(this).data('tab');
			self.$body.find('.sawd-tab').removeClass('active');
			$(this).addClass('active');
			self.active_tab = tab;
			self._load_tab(tab);
		});

		// Filters
		this.$body.on('click', '#sawd-apply-filters', () => this._apply_filters());
		this.$body.on('click', '#sawd-reset-filters',  () => this._reset_filters());
		this.$body.on('click', '#sawd-refresh',        () => this._load_tab(this.active_tab, true));

		// Configure button
		this.$body.on('click', '#sawd-configure', () => this._open_config_panel());

		// Edit Workspace button
		this.$body.on('click', '#sawd-edit-workspace', () => {
			if (this.active_tab === 'examination') {
				// Route to the active exam sub-tab's workspace
				const sub = SAWD_EXAM_SUBTABS.find(t => t.key === this.active_exam_subtab);
				if (sub) frappe.set_route('workspace', sub.workspace);
			} else {
				const mod = this.workspace_modules.find(m => m.key === this.active_tab);
				if (mod && mod.workspace) {
					if (this.active_tab_is_dashboard) {
						frappe.set_route('dashboard-view', mod.workspace);
					} else {
						frappe.set_route('workspace', mod.workspace);
					}
				}
			}
		});

		// Examination inner sub-tab switching
		this.$body.on('click', '.sawd-exam-subtab', (e) => {
			const $tab = $(e.currentTarget);
			const key  = $tab.data('subtab');
			const ws   = $tab.data('workspace');
			$('.sawd-exam-subtab').removeClass('active');
			$tab.addClass('active');
			this.active_exam_subtab = key;
			this._update_exam_edit_btn();
			this._load_workspace_dashboard(key, ws);
		});

		// Config drawer close
		this.$body.on('click', '#sawd-config-close, #sawd-config-overlay, #sawd-config-cancel',
			() => this._close_config_panel());

		// Config save
		this.$body.on('click', '#sawd-config-save', () => this._save_config());

		// Module toggle inside config panel (click anywhere on item)
		this.$body.on('click', '.sawd-config-module-item:not(.is-locked)', function () {
			const $toggle = $(this).find('.sawd-config-module-toggle');
			$toggle.toggleClass('on');
			$(this).toggleClass('is-enabled');
		});

		// Select all / none shortcuts
		this.$body.on('click', '#sawd-config-select-all',  () => this._config_select_all(true));
		this.$body.on('click', '#sawd-config-select-none', () => this._config_select_all(false));

		// Drilldown panel
		this.$body.on('click', '#sawd-dd-close, #sawd-dd-overlay', () => this._close_drilldown());

		this.$body.on('click', '.sawd-kpi-card.has-drilldown', function () {
			const dt = $(this).data('dt');
			if (dt) {
				frappe.set_route('List', dt);
			} else {
				self._open_drilldown(
					$(this).data('dd-module'),
					$(this).data('dd-dim'),
					$(this).data('dd-val'),
					{},
					$(this).data('dd-title') || '',
				);
			}
		});

		this.$body.on('click', '#sawd-dd-viewlist', () => {
			const r = this._drilldown_list_route;
			if (r) frappe.set_route('List', r.dt, r.filters);
		});

		this.$body.on('click', '#sawd-dd-export', () => this._export_drilldown());

		$(document).on('input', '#sawd-dd-search', function () {
			const q = $(this).val().toLowerCase().trim();
			let visible = 0;
			const $rows = $('.sawd-table tbody tr');
			$rows.each(function () {
				const match = !q || $(this).text().toLowerCase().includes(q);
				$(this).toggle(match);
				if (match) visible++;
			});
			$('#sawd-dd-search-count').text(q ? `${visible} / ${$rows.length} shown` : '');
			$('#sawd-dd-search-clear').toggle(!!q);
		});
		$(document).on('click', '#sawd-dd-search-clear', function () {
			$('#sawd-dd-search').val('').trigger('input');
		});
	}

	// ── Workspace config loading ──────────────────────────────────────────────

	_load_workspace_config() {
		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_workspace_modules`,
			callback: (r) => {
				if (r.exc || !r.message) {
					this._show_error_state('Failed to load workspace configuration.');
					return;
				}
				this.workspace_modules = r.message.modules || [];
				this._render_ws_badges();
				this._build_tabs();
				$('#sawd-filter-bar').show();
				$('#sawd-configure').show();
				$('#sawd-refresh').show();
				this._load_filter_options();
			},
		});
	}

	// ── Workspace badge strip ─────────────────────────────────────────────────

	_render_ws_badges() {
		const enabled = this.workspace_modules.filter(m => m.enabled);
		if (!enabled.length) { $('#sawd-ws-badges').hide(); return; }

		const badges = enabled.map(m =>
			`<span class="sawd-ws-badge">${m.icon} ${m.label}</span>`
		).join('');
		$('#sawd-ws-badges').html(`
			<div class="sawd-ws-badge-strip">
				<span class="sawd-ws-badge-label">Active modules:</span>
				${badges}
			</div>
		`).show();
	}

	// ── Dynamic tab building ──────────────────────────────────────────────────

	_build_tabs() {
		const enabled = this.workspace_modules.filter(m => m.enabled);

		if (!enabled.length) {
			$('#sawd-tabs-container').html(`
				<div class="sawd-tabs">
					<span class="sawd-tabs-empty">
						No modules enabled — click <strong>⚙️ Configure Workspace</strong> to add some.
					</span>
				</div>`);
			$('#sawd-tab-content').html(`
				<div class="sawd-empty">
					<div class="sawd-empty-icon">🗂️</div>
					<div class="sawd-empty-title">Your workspace is empty</div>
					<div class="sawd-empty-sub">Use <strong>⚙️ Configure Workspace</strong> to select analytics modules.</div>
				</div>`);
			return;
		}

		// Ensure active_tab is still valid; fall back to first enabled
		const keys = enabled.map(m => m.key);
		if (!keys.includes(this.active_tab)) {
			this.active_tab = keys[0];
		}

		const tab_html = enabled.map(m => `
			<div class="sawd-tab${m.key === this.active_tab ? ' active' : ''}" data-tab="${m.key}">
				<span class="tab-icon">${m.icon}</span> ${m.label}
			</div>
		`).join('');

		$('#sawd-tabs-container').html(`<div class="sawd-tabs">${tab_html}</div>`);
	}

	// ── Configuration panel ───────────────────────────────────────────────────

	_open_config_panel() {
		const $body = $('#sawd-config-body');

		// Segregate: overview (always on) vs configurable modules
		const locked = this.workspace_modules.filter(m => m.key === 'overview');
		const available = this.workspace_modules.filter(m => m.key !== 'overview' && m.available);
		const unavailable = this.workspace_modules.filter(m => m.key !== 'overview' && !m.available);

		const render_item = (m, force_enabled = false) => {
			const on = force_enabled || m.enabled;
			const locked_item = force_enabled;
			return `
			<div class="sawd-config-module-item${on ? ' is-enabled' : ''}${locked_item ? ' is-locked' : ''}" data-key="${m.key}">
				<div class="sawd-config-module-icon">${m.icon}</div>
				<div class="sawd-config-module-info">
					<div class="sawd-config-module-name">${m.label}</div>
					<div class="sawd-config-module-desc">${SAWD_MODULE_META[m.key]?.desc || ''}</div>
					${m.workspace ? `<div class="sawd-config-ws-tag">🔗 ${m.workspace}</div>` : ''}
				</div>
				<button class="sawd-config-module-toggle${on ? ' on' : ''}" title="${locked_item ? 'Always enabled' : (on ? 'Click to disable' : 'Click to enable')}"></button>
			</div>`;
		};

		let html = `
			<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
				<div class="sawd-config-section-label">Always Visible</div>
			</div>
			<div class="sawd-config-module-list">${locked.map(m => render_item(m, true)).join('')}</div>`;

		if (available.length) {
			html += `
			<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
				<div class="sawd-config-section-label">Workspace Modules</div>
				<span style="display:flex;gap:10px">
					<a id="sawd-config-select-all"  href="#">Enable all</a>
					<a id="sawd-config-select-none" href="#">Disable all</a>
				</span>
			</div>
			<div class="sawd-config-module-list">${available.map(m => render_item(m)).join('')}</div>`;
		}

		if (unavailable.length) {
			html += `
			<div class="sawd-config-section-label" style="margin-top:12px">Unavailable (workspace not installed)</div>
			<div class="sawd-config-module-list">${unavailable.map(m => render_item(m, false)).join('')}</div>`;
		}

		$body.html(html);
		$('#sawd-config-overlay, #sawd-config-panel').addClass('open');
		this._config_open = true;
	}

	_close_config_panel() {
		$('#sawd-config-overlay, #sawd-config-panel').removeClass('open');
		this._config_open = false;
	}

	_config_select_all(enable) {
		$('#sawd-config-body .sawd-config-module-item:not(.is-locked)').each(function () {
			if (enable) { $(this).addClass('is-enabled'); $(this).find('.sawd-config-module-toggle').addClass('on'); }
			else        { $(this).removeClass('is-enabled'); $(this).find('.sawd-config-module-toggle').removeClass('on'); }
		});
	}

	_save_config() {
		const keys = ['overview'];
		$('#sawd-config-body .sawd-config-module-item:not(.is-locked)').each(function () {
			if ($(this).find('.sawd-config-module-toggle').hasClass('on')) {
				keys.push($(this).data('key'));
			}
		});

		frappe.call({
			method: `${SAWD_PAGE_METHOD}.save_workspace_config`,
			args: { enabled_modules: keys },
			callback: (r) => {
				if (r.exc) { frappe.show_alert({ message: 'Failed to save configuration', indicator: 'red' }); return; }

				// Update local state
				const saved = new Set(r.message.enabled_modules || keys);
				this.workspace_modules.forEach(m => { m.enabled = saved.has(m.key); });

				this._close_config_panel();
				this._render_ws_badges();
				this._build_tabs();
				this._load_tab(this.active_tab, true);

				frappe.show_alert({ message: 'Workspace configuration saved', indicator: 'green' });
			},
		});
	}

	// ── Filter helpers ────────────────────────────────────────────────────────

	_load_filter_options() {
		const make_select = (container_id, options, vk, lk, placeholder, onchange) => {
			const $el = $('<select class="form-control input-xs"></select>');
			$el.append(`<option value="">${placeholder}</option>`);
			options.forEach(opt => $el.append(`<option value="${opt[vk]}">${opt[lk] || opt[vk]}</option>`));
			$el.on('change', () => onchange && onchange($el.val()));
			$('#' + container_id).html($el);
			return $el;
		};

		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_filter_options`,
			callback: (r) => {
				if (r.exc || !r.message) return;
				const opts = r.message;
				this._filter_options = opts;

				this.$ay = make_select('sawd-f-ay', opts.academic_years, 'name', 'name', 'All Years', (v) => {
					this.filters.academic_year = v || null;
					this._refresh_cohort_filter();
					this._refresh_term_filter();
				});
				this.$term = make_select('sawd-f-term', opts.terms || [], 'name', 'term_name', 'All Terms', (v) => {
					this.filters.term = v || null;
				});
				this.$prog = make_select('sawd-f-prog', opts.programs, 'name', 'program_name', 'All Programs', (v) => {
					this.filters.program = v || null;
					this._refresh_cohort_filter();
				});
				this.$cohort = make_select('sawd-f-cohort', opts.cohorts, 'name', 'cohort_name', 'All Cohorts', (v) => {
					this.filters.cohort = v || null;
				});
				this.$sstatus = make_select('sawd-f-sstatus', opts.student_statuses || [], 'value', 'label', 'All Statuses', (v) => {
					this.filters.student_status = v || null;
				});

				this._load_tab(this.active_tab);
			},
		});
	}

	_refresh_cohort_filter() {
		if (!this._filter_options) return;
		let cohorts = this._filter_options.cohorts;
		if (this.filters.academic_year) cohorts = cohorts.filter(c => c.academic_year === this.filters.academic_year);
		if (this.filters.program)       cohorts = cohorts.filter(c => c.program === this.filters.program);
		const $s = this.$cohort;
		$s.html('<option value="">All Cohorts</option>');
		cohorts.forEach(c => $s.append(`<option value="${c.name}">${c.cohort_name}</option>`));
		$s.val(''); this.filters.cohort = null;
	}

	_refresh_term_filter() {
		if (!this._filter_options) return;
		let terms = this._filter_options.terms || [];
		if (this.filters.academic_year) terms = terms.filter(t => t.academic_year === this.filters.academic_year);
		const $s = this.$term;
		$s.html('<option value="">All Terms</option>');
		terms.forEach(t => $s.append(`<option value="${t.name}">${t.term_name || t.name}</option>`));
		$s.val(''); this.filters.term = null;
	}

	_apply_filters() {
		this.filters.academic_year  = this.$ay?.val()      || null;
		this.filters.term           = this.$term?.val()    || null;
		this.filters.program        = this.$prog?.val()    || null;
		this.filters.cohort         = this.$cohort?.val()  || null;
		this.filters.student_status = this.$sstatus?.val() || null;
		this._load_tab(this.active_tab, true);
	}

	_reset_filters() {
		this.filters = { academic_year: null, term: null, program: null, cohort: null, student_status: null };
		this.$ay?.val(''); this.$term?.val(''); this.$prog?.val('');
		this.$cohort?.val(''); this.$sstatus?.val('');
		this._refresh_cohort_filter();
		this._refresh_term_filter();
		this._load_tab(this.active_tab, true);
	}

	// ── Misc ──────────────────────────────────────────────────────────────────

	_show_error_state(msg) {
		$('#sawd-tab-content').html(`
		<div class="sawd-empty">
			<div class="sawd-empty-icon">⚠️</div>
			<div class="sawd-empty-title">${msg}</div>
		</div>`);
	}

	_show_loading(sections = 4) {
		const s = Array(sections).fill('<div class="sawd-skeleton sawd-skeleton-chart"></div>').join('');
		const k = Array(4).fill('<div class="sawd-skeleton sawd-skeleton-kpi"></div>').join('');
		$('#sawd-tab-content').html(`<div class="sawd-kpi-grid">${k}</div><div class="sawd-chart-grid">${s}</div>`);
	}

	_show_error() {
		$('#sawd-tab-content').html(`
		<div class="sawd-chart-card"><div class="sawd-empty">
			<div class="sawd-empty-icon">⚠️</div>
			<div class="sawd-empty-title">Failed to load analytics</div>
			<div class="sawd-empty-sub">Check the console for details or try refreshing.</div>
		</div></div>`);
	}

	// ── Tab loader dispatcher (PART 2 will add full tab methods) ─────────────

	_load_tab(tab, force = false) {
		const $content = $('#sawd-tab-content');
		$content.addClass('sawd-animate');
		setTimeout(() => $content.removeClass('sawd-animate'), 400);
		$('#sawd-last-updated').text('Updated ' + frappe.datetime.now_time());

		// Remove exam sub-tabs when switching away from examination
		if (tab !== 'examination') {
			$('#sawd-exam-subtabs').remove();
		}

		const mod = this.workspace_modules.find(m => m.key === tab);
		if (tab === 'overview') {
			$('#sawd-edit-workspace').hide();
			this._load_overview();
		} else if (tab === 'examination') {
			$('#sawd-edit-workspace').show();
			this._load_examination_tab();
		} else if (mod && mod.workspace) {
			$('#sawd-edit-workspace').show();
			this._load_workspace_dashboard(tab, mod.workspace);
		} else {
			$('#sawd-edit-workspace').hide();
			this._show_error();
		}
	}

	// ── Examination inner sub-tabs ────────────────────────────────────────────

	_load_examination_tab() {
		// Remove and re-render the sub-tab bar so it's always fresh
		$('#sawd-exam-subtabs').remove();

		const subtabs_html = SAWD_EXAM_SUBTABS.map(t => `
			<div class="sawd-exam-subtab${t.key === this.active_exam_subtab ? ' active' : ''}"
				data-subtab="${t.key}" data-workspace="${t.workspace}">
				<span class="tab-icon">${t.icon}</span> ${t.label}
			</div>
		`).join('');

		const $bar = $(`
			<div id="sawd-exam-subtabs" class="sawd-exam-subtab-bar">
				<span class="sawd-exam-subtab-label">📝 Examination:</span>
				${subtabs_html}
			</div>
		`);

		$('#sawd-tabs-container').after($bar);

		this._update_exam_edit_btn();

		const active = SAWD_EXAM_SUBTABS.find(t => t.key === this.active_exam_subtab);
		if (active) {
			this._load_workspace_dashboard(active.key, active.workspace);
		}
	}

	_update_exam_edit_btn() {
		const sub = SAWD_EXAM_SUBTABS.find(t => t.key === this.active_exam_subtab);
		if (sub) {
			$('#sawd-edit-workspace').show().text(`✏️ Edit ${sub.label}`);
		}
	}

	// ── Workspace shortcut grid (fallback when workspace has no charts/cards) ──

	_load_workspace_shortcut_grid(workspace_name) {
		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_workspace_shortcut_links`,
			args: { workspace_label: workspace_name },
			callback: (r) => {
				const shortcuts = (r.message || []).filter(s => s.label && s.link_to || s.url);
				if (!shortcuts.length) {
					const edit_url = `/app/workspace/${workspace_name}`;
					$('#sawd-tab-content').html(`
						<div class="sawd-empty">
							<div class="sawd-empty-icon">📊</div>
							<div class="sawd-empty-title">No content configured</div>
							<div class="sawd-empty-sub">
								<a href="${edit_url}" target="_blank"
									style="text-decoration:underline;color:var(--sawd-primary);font-weight:600">
									Open ${workspace_name} workspace settings
								</a> to add charts and cards.
							</div>
						</div>`);
					return;
				}

				const TYPE_ICON = {
					'DocType': '📋', 'List': '📋', 'Single': '📝',
					'Page':    '📄', 'Report': '📊', 'URL': '🔗',
					'Dashboard': '📈',
				};

				const cards_html = shortcuts.map(s => {
					const icon     = TYPE_ICON[s.type] || '🔗';
					const fa_icon  = s.icon ? `<i class="fa fa-${s.icon}"></i>` : icon;
					const type_lbl = s.type || 'Link';
					const href     = s.type === 'URL' ? (s.url || '#') : '#';
					const dt       = (s.type === 'DocType' || s.type === 'List') ? s.link_to : '';
					const pg       = s.type === 'Page' ? s.link_to : '';
					const rp       = s.type === 'Report' ? s.link_to : '';
					return `
					<div class="sawd-sc-action-card"
						data-type="${s.type || ''}" data-dt="${dt}"
						data-page="${pg}" data-report="${rp}" data-url="${href}">
						<div class="sawd-sc-action-icon">${fa_icon}</div>
						<div class="sawd-sc-action-info">
							<div class="sawd-sc-action-label">${s.label || s.link_to}</div>
							<div class="sawd-sc-action-type">${type_lbl}</div>
						</div>
					</div>`;
				}).join('');

				$('#sawd-tab-content').html(`
					<div class="sawd-section-title">🔗 ${workspace_name} — Quick Actions</div>
					<div class="sawd-sc-action-grid">${cards_html}</div>
				`);

				$('#sawd-tab-content .sawd-sc-action-card').on('click', function () {
					const type = $(this).data('type');
					const dt   = $(this).data('dt');
					const pg   = $(this).data('page');
					const rp   = $(this).data('report');
					const url  = $(this).data('url');
					if (type === 'DocType' || type === 'List')  frappe.set_route('List', dt);
					else if (type === 'Single')                 frappe.set_route('Form', dt);
					else if (type === 'Page' && pg)             frappe.set_route(pg);
					else if (type === 'Report' && rp)           frappe.set_route('query-report', rp);
					else if (type === 'URL' && url && url !== '#') window.open(url, '_blank');
				});
			},
		});
	}

	_load_workspace_dashboard(tab_key, workspace_name) {
		this._show_loading(4);
		this._render_ws_shortcuts(tab_key);

		frappe.call({
			method: 'slcm.slcm.page.slcm_analytics_workspace_dashboard.slcm_analytics_workspace_dashboard.get_workspace_dashboard_details',
			args: {
				workspace_name: workspace_name,
				filters: this.filters
			},
			callback: (r) => {
				if (r.exc) {
					this._show_error();
					return;
				}
				const cards = r.message.cards || [];
				const charts = r.message.charts || [];

				this.active_tab_is_dashboard = !!r.message.is_dashboard;
				if (this.active_tab_is_dashboard) {
					$('#sawd-edit-workspace').text('✏️ Edit Dashboard');
				} else {
					$('#sawd-edit-workspace').text('✏️ Edit Workspace');
				}

				if (!cards.length && !charts.length) {
					this._load_workspace_shortcut_grid(workspace_name);
					return;
				}

				// Build HTML
				let html = '';

				if (cards.length) {
					const cards_html = cards.map(c => this._render_dynamic_card(c)).join('');
					html += `<div class="sawd-kpi-grid">${cards_html}</div>`;
				}

				if (charts.length) {
					const charts_html = charts.map((ch, idx) => {
						const container_id = `sawd-dynamic-chart-${idx}`;
						let subtitle = '';
						if (ch.chart_type === 'Report') {
							subtitle = `Based on ${ch.report_name} Report`;
						} else if (ch.document_type) {
							subtitle = `Based on ${ch.document_type}`;
						}
						return this._chart_card_dynamic(container_id, ch.label, subtitle);
					}).join('');
					html += `<div class="sawd-chart-grid">${charts_html}</div>`;
				}

				$('#sawd-tab-content').html(html);

				// Render charts using frappe.Chart
				charts.forEach((ch, idx) => {
					const container_id = `sawd-dynamic-chart-${idx}`;
					this._render_dynamic_chart(container_id, ch);
				});
			}
		});
	}

	_render_dynamic_card(card) {
		const color = card.color || 'var(--sawd-primary)';
		const formatted_val = sawd_fmt_number(card.value);
		let diff_html = '';
		if (card.show_percentage_stats && card.diff !== null && card.diff !== undefined) {
			const arrow = card.diff >= 0 ? '▲' : '▼';
			const text_cls = card.diff >= 0 ? 'text-success' : 'text-danger';
			diff_html = `<div class="sawd-kpi-sub ${text_cls}" style="font-weight:600;margin-top:4px;">${arrow} ${Math.abs(card.diff).toFixed(1)}% vs last ${card.stats_time_interval.toLowerCase().replace('ly', '')}</div>`;
		}
		return `
		<div class="sawd-kpi-card has-drilldown" data-dt="${card.document_type || ''}">
			<div class="sawd-kpi-accent" style="background:${color}"></div>
			<div class="sawd-kpi-label">${card.label}</div>
			<div class="sawd-kpi-value">${formatted_val}</div>
			${diff_html}
			${card.document_type ? `<div class="sawd-kpi-drill-hint"><i class="fa fa-list" style="font-size:9px"></i> Click to view List</div>` : ''}
		</div>`;
	}

	_chart_card_dynamic(id, title, subtitle) {
		return `
		<div class="sawd-chart-card">
			<div class="sawd-chart-header">
				<div class="sawd-chart-title-wrap">
					<div class="sawd-chart-title">${title}</div>
					${subtitle ? `<div class="sawd-chart-subtitle">${subtitle}</div>` : ''}
				</div>
			</div>
			<div class="sawd-chart-body" id="${id}"><div class="sawd-skeleton" style="height:180px"></div></div>
		</div>`;
	}

	_render_dynamic_chart(container_id, chart) {
		const container = document.getElementById(container_id);
		if (!container) return;

		if (chart.chart_type === 'Report') {
			this._render_report_chart(container_id, chart);
			return;
		}

		if (!chart.chart_data || !chart.chart_data.labels || !chart.chart_data.labels.length) {
			container.innerHTML = this._empty_html('No data available');
			return;
		}

		const type = (chart.type || 'bar').toLowerCase();

		try {
			new frappe.Chart(container, {
				data: chart.chart_data,
				type: type,
				height: 240,
				colors: SAWD_PALETTE.mixed,
			});

			container.addEventListener('data-select', (e) => {
				if (!e.detail) return;
				const idx = e.detail.index != null ? e.detail.index : null;
				const lbl = idx != null ? chart.chart_data.labels[idx] : null;
				if (lbl && chart.document_type) {
					const filters = {};
					if (chart.group_by_field) {
						filters[chart.group_by_field] = lbl;
					}
					frappe.set_route('List', chart.document_type, filters);
				}
			});
		} catch (e) {
			container.innerHTML = this._empty_html('Failed to render chart');
		}
	}

	_render_report_chart(container_id, ch) {
		const container = document.getElementById(container_id);
		if (!container) return;

		let report_filters = {};
		if (ch.filters_json) {
			try {
				report_filters = JSON.parse(ch.filters_json);
			} catch (e) {}
		}

		if (this.filters) {
			const mapping = {
				academic_year: 'academic_year',
				term: 'academic_term',
				program: 'program',
				cohort: 'cohort',
				student_status: 'status'
			};
			for (let [k, val] of Object.entries(this.filters)) {
				if (val !== null && val !== undefined && val !== "") {
					const target_key = mapping[k] || k;
					report_filters[target_key] = val;
				}
			}
		}

		frappe.call({
			method: 'frappe.desk.query_report.run',
			args: {
				report_name: ch.report_name,
				filters: report_filters,
				are_default_filters: false
			},
			callback: (r) => {
				if (r.exc || !r.message) {
					container.innerHTML = this._empty_html('Failed to load report data');
					return;
				}

				let chart_data = null;
				if (r.message.chart && ch.use_report_chart) {
					chart_data = r.message.chart;
				} else {
					const result = r.message.result || [];
					const columns = r.message.columns || [];
					const y_fields = (ch.y_axis || []).map(y => y.y_field);

					let chart_fields = [];
					columns.forEach(col => {
						let field = frappe.report_utils.prepare_field_from_column(col);
						if (y_fields.includes(field.fieldname)) {
							chart_fields.push(field);
						}
					});

					if (chart_fields.length && result.length) {
						chart_data = frappe.report_utils.make_chart_options(columns, result, chart_fields).data;
					}
				}

				if (!chart_data || !chart_data.labels || !chart_data.labels.length) {
					container.innerHTML = this._empty_html('No data available');
					return;
				}

				container.innerHTML = '';
				new frappe.Chart(`#${container_id}`, {
					data: chart_data,
					type: (ch.type || 'bar').toLowerCase(),
					height: 240,
					colors: SAWD_PALETTE.mixed,
				});
			}
		});
	}

	// ── Workspace shortcut bar ────────────────────────────────────────────────
	// Renders quick-navigation links pulled live from the Frappe Workspace
	// definition for the active tab's module.

	_render_ws_shortcuts(tab_key) {
		const mod = this.workspace_modules.find(m => m.key === tab_key);
		const shortcuts = mod && mod.shortcuts;
		$('#sawd-ws-shortcut-bar').remove();
		if (!shortcuts || !shortcuts.length) return;

		const items = shortcuts.map(s => {
			const icon = s.icon ? `<i class="fa fa-${s.icon}"></i>` : '🔗';
			const href = s.type === 'URL' ? (s.url || '#') : '#';
			const dt   = (s.type === 'DocType' || s.type === 'List') ? s.link_to : '';
			const pg   = s.type === 'Page' ? s.link_to : '';
			return `<a class="sawd-ws-sc-chip" href="${href}"
				data-dt="${dt}" data-page="${pg}" data-type="${s.type || ''}">
				${icon} ${s.label || s.link_to}
			</a>`;
		}).join('');

		const bar = `
		<div id="sawd-ws-shortcut-bar" class="sawd-ws-shortcut-bar">
			<div class="sawd-ws-sc-header">
				<i class="fa fa-link"></i> Quick Links
			</div>
			<div class="sawd-ws-sc-list">${items}</div>
		</div>`;
		$('#sawd-tab-content').before(bar);

		$('#sawd-ws-shortcut-bar .sawd-ws-sc-chip').on('click', function (e) {
			const type = $(this).data('type');
			const dt   = $(this).data('dt');
			const pg   = $(this).data('page');
			if (type === 'DocType' || type === 'List') {
				e.preventDefault(); frappe.set_route('List', dt);
			} else if (type === 'Single') {
				e.preventDefault(); frappe.set_route('Form', dt);
			} else if (type === 'Page' && pg) {
				e.preventDefault(); frappe.set_route(pg);
			}
		});
	}

	// ── Tab: Overview ─────────────────────────────────────────────────────────

	_load_overview() {
		this._show_loading(4);
		this._render_ws_shortcuts('overview');

		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_overview_stats`,
			args: this.filters,
			callback: (r) => {
				if (r.exc || !r.message) { this._show_error(); return; }
				const d = r.message;

				$('#sawd-tab-content').html(`
					<div class="sawd-kpi-grid" id="sawd-ov-adm-kpis">
						${Array(6).fill('<div class="sawd-skeleton sawd-skeleton-kpi"></div>').join('')}
					</div>
					<div class="sawd-section-title">Key Performance Indicators</div>
					<div class="sawd-chart-grid">
						${this._chart_card('sawd-ov-student-status','Student Status Distribution','Real-time student lifecycle','','')}
						${this._chart_card('sawd-ov-fee-trend','Fee Collection vs Outstanding','Financial health snapshot','','')}
						${this._rate_card('sawd-ov-rates','System Performance Rates')}
						${this._chart_card('sawd-ov-hostel','Hostel Utilization','Bed occupancy overview','','')}
					</div>
				`);

				this._render_overview_charts(d);
			},
		});
	}

	_render_overview_charts(d) {
		// ── Top KPI cards — pull from admission analytics ────────────────────
		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_admission_analytics`,
			args: this.filters,
			callback: (r) => {
				if (r.exc || !r.message) return;
				const ad = r.message;
				const acc = ad.acceptance_rate >= 60 ? 'success' : ad.acceptance_rate >= 30 ? 'warning' : 'danger';

				$('#sawd-ov-adm-kpis').html(`
					${this._kpi('Total Applicants', ad.total_applicants, '🎯', 'primary', `${ad.active_cycles} active cycles`, { module:'admission', dimension:'app_status', value:'all' })}
					${this._kpi('Offer Acceptance', ad.acceptance_rate + '%', '📨', acc, `${ad.accepted_offers} of ${ad.total_offers} offers`, { module:'admission', dimension:'offer_status', value:'Accepted' })}
					${this._kpi('Active Students', d.active_students, '🎓', 'success', `${d.total_students} total enrolled`, { module:'students', dimension:'student_status', value:'Active' })}
					${this._kpi('Attendance Rate', d.attendance_rate + '%', '📋', d.attendance_rate >= 75 ? 'success' : d.attendance_rate >= 50 ? 'warning' : 'danger', `${sawd_fmt_number(d.total_attendance_records)} records`, { module:'attendance', dimension:'status', value:'Present' })}
					${this._kpi('Fee Collection', d.fee_collection_rate + '%', '💰', d.fee_collection_rate >= 80 ? 'success' : 'warning', sawd_fmt_currency(d.total_collected) + ' collected', { module:'fees', dimension:'payment_status', value:'Paid' })}
					${this._kpi('Placement Offers', d.total_placement_offers, '💼', 'purple', `${d.accepted_placement_offers} accepted`, { module:'placement', dimension:'offer_status', value:'Accepted' })}
				`);

				// Re-bind drilldown for dynamically injected cards
				const self = this;
				$('#sawd-ov-adm-kpis').find('.sawd-kpi-card.has-drilldown').off('click').on('click', function () {
					self._open_drilldown($(this).data('dd-module'), $(this).data('dd-dim'), $(this).data('dd-val'), {}, $(this).data('dd-title') || '');
				});
			},
		});

		// ── Student status donut ─────────────────────────────────────────────
		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_student_analytics`,
			args: this.filters,
			callback: (r) => {
				if (r.exc || !r.message) return;
				this._render_donut('#sawd-ov-student-status .sawd-chart-body', r.message.status_distribution, 'students', 'student_status');
			},
		});

		// ── Fee bar ──────────────────────────────────────────────────────────
		this._render_bar('#sawd-ov-fee-trend .sawd-chart-body', {
			labels: ['Billed', 'Collected', 'Outstanding'],
			datasets: [{ values: [d.total_billed, d.total_collected, d.total_outstanding] }],
		}, { colors: ['#2563eb', '#059669', '#dc2626'], format_value: sawd_fmt_currency });

		// ── Rates progress list ──────────────────────────────────────────────
		$('#sawd-ov-rates .sawd-chart-body').html(`
			<div class="sawd-progress-list" style="padding:8px 0">
				${this._progress_bar('Attendance Rate',      d.attendance_rate,          '#059669')}
				${this._progress_bar('Fee Collection Rate',  d.fee_collection_rate,      '#2563eb')}
				${this._progress_bar('Hostel Occupancy',     d.hostel_occupancy_rate,    '#0891b2')}
				${this._progress_bar('Placement Acceptance', d.placement_acceptance_rate,'#7c3aed')}
			</div>
		`);

		// ── Hostel gauge ─────────────────────────────────────────────────────
		this._render_gauge('#sawd-ov-hostel .sawd-chart-body', d.hostel_occupancy_rate,
			`${d.hostel_allocated} of ${d.total_beds} beds`);
	}

	// ── Tab: Students ─────────────────────────────────────────────────────────

	_load_students() {
		this._show_loading(5);
		this._render_ws_shortcuts('students');

		frappe.call({
			method: `${SAWD_PAGE_METHOD}.get_student_analytics`,
			args: this.filters,
			callback: (r) => {
				if (r.exc || !r.message) { this._show_error(); return; }
				const d = r.message;

				const total      = (d.status_distribution || []).reduce((s, x) => s + (x.value || 0), 0);
				const active_row = (d.status_distribution || []).find(x => x.label === 'Active');
				const active_pct = active_row ? Math.round(active_row.value / total * 100) : 0;

				$('#sawd-tab-content').html(`
					<div class="sawd-kpi-grid">
						${this._kpi('Total Enrolled', total,            '🎓', 'primary', 'across all cohorts',   { module:'students', dimension:'student_status', value:'Active' })}
						${this._kpi('Active Rate',    active_pct + '%', '✅', active_pct >= 80 ? 'success' : 'warning', 'of all students', { module:'students', dimension:'student_status', value:'Active' })}
						${this._kpi('Programs',       d.program_distribution.length, '📚', 'info', 'with enrollments', { module:'students', dimension:'programs_list', value:'all' })}
						${this._kpi('Cohorts',        d.cohort_distribution.length,  '🗂️', 'purple','active cohorts', { module:'students', dimension:'cohorts_list', value:'all' })}
					</div>

					<div class="sawd-section-title">Enrollment Breakdown</div>
					<div class="sawd-chart-grid">
						${this._chart_card('sawd-st-status',  'Student Status',      'Lifecycle distribution',  'Click segment to drill down', '')}
						${this._chart_card('sawd-st-gender',  'Gender Distribution', 'Demographic breakdown',   'Click to explore', '')}
						${this._chart_card('sawd-st-quota',   'Quota Category',      'Reservation breakdown',   '', '')}
						${this._chart_card('sawd-st-scholar', 'Scholarship Split',   'Scholarship coverage',    '', '')}
					</div>

					<div class="sawd-section-title">Program & Cohort Analysis</div>
					<div class="sawd-chart-grid">
						<div class="sawd-chart-wide">
							${this._chart_card('sawd-st-program','Program-wise Enrollment','Student count per program','Click bar to drill down','')}
						</div>
					</div>
					<div class="sawd-chart-grid">
						${this._chart_card('sawd-st-admission','Admission Type',      'Regular vs PACE vs Other','','') }
						${this._chart_card('sawd-st-cohort',   'Top Cohorts',         'Enrollment per cohort',    '','') }
						${this._chart_card('sawd-st-regstatus','Registration Status', 'Workflow progress',        '','') }
					</div>
				`);

				this._render_donut('#sawd-st-status .sawd-chart-body',    d.status_distribution,    'students', 'student_status');
				this._render_donut('#sawd-st-gender .sawd-chart-body',    d.gender_distribution,    'students', 'gender');
				this._render_donut('#sawd-st-quota .sawd-chart-body',     d.quota_distribution,     'students', 'quota');
				this._render_donut('#sawd-st-scholar .sawd-chart-body',   d.scholarship_distribution,'students', 'scholarship');
				this._render_bar_horizontal('#sawd-st-program .sawd-chart-body',   d.program_distribution,       { module:'students', dimension:'program' });
				this._render_donut('#sawd-st-admission .sawd-chart-body', d.admission_type,         'students', 'admission_type');
				this._render_bar_horizontal('#sawd-st-cohort .sawd-chart-body',    d.cohort_distribution.slice(0,8), { module:'students', dimension:'cohort' });
				this._render_funnel('#sawd-st-regstatus .sawd-chart-body', d.registration_status,   { module:'students', dimension:'reg_status' });
			},
		});
	}

	// ── Chart primitive helpers ───────────────────────────────────────────────

	_render_donut($sel, data, module, dimension) {
		const container = document.querySelector($sel);
		if (!container) return;
		if (!data || !data.length) { container.innerHTML = this._empty_html(); return; }
		const colors = data.map(d => sawd_status_color(d.label));
		try {
			new frappe.Chart(container, {
				data: sawd_labels_and_values(data),
				type: 'donut', height: 220, colors,
			});
			container.addEventListener('data-select', (e) => {
				if (!e.detail) return;
				const idx = e.detail.index != null ? e.detail.index : null;
				const lbl = idx != null ? data[idx]?.label : null;
				if (lbl && module && dimension) this._open_drilldown(module, dimension, lbl, data[idx]);
			});
		} catch (err) { container.innerHTML = this._empty_html('Chart unavailable'); }
	}

	_render_bar($sel, chartData, opts = {}) {
		const container = typeof $sel === 'string' ? document.querySelector($sel) : $sel;
		if (!container) return;
		try {
			new frappe.Chart(container, {
				data: chartData, type: 'bar', height: opts.height || 220,
				colors: opts.colors || SAWD_PALETTE.primary,
				barOptions: { spaceRatio: 0.4 },
			});
		} catch (e) { container.innerHTML = this._empty_html(); }
	}

	_render_bar_horizontal($sel, data, dd_opts = {}) {
		const container = document.querySelector($sel);
		if (!container) return;
		if (!data || !data.length) { container.innerHTML = this._empty_html(); return; }
		const max = Math.max(...data.map(x => x.value || 0));
		const html = data.map((d, i) => {
			const pct   = max ? (d.value / max * 100) : 0;
			const color = SAWD_PALETTE.mixed[i % SAWD_PALETTE.mixed.length];
			return `
			<div class="sawd-funnel-step" data-label="${d.label}" data-value="${d.value}">
				<div class="sawd-funnel-name">${d.label}</div>
				<div class="sawd-funnel-bar-wrap">
					<div class="sawd-funnel-bar" style="width:${pct}%;background:${color}">
						<span class="sawd-funnel-bar-label">${sawd_fmt_number(d.value)}</span>
					</div>
				</div>
				<div class="sawd-funnel-meta">${sawd_fmt_number(d.value)}</div>
			</div>`;
		}).join('');
		container.innerHTML = `<div class="sawd-funnel" style="padding:4px 0;max-height:280px;overflow-y:auto">${html}</div>`;
		if (dd_opts.module && dd_opts.dimension) {
			container.querySelectorAll('.sawd-funnel-step').forEach(el => {
				el.addEventListener('click', () => {
					this._open_drilldown(dd_opts.module, dd_opts.dimension, el.dataset.label, { label: el.dataset.label, value: el.dataset.value });
				});
			});
		}
	}

	_render_funnel($sel, data, dd_opts = {}) {
		const container = document.querySelector($sel);
		if (!container) return;
		if (!data || !data.length) { container.innerHTML = this._empty_html(); return; }
		const max      = Math.max(...data.map(x => x.value || 0));
		const colors   = ['#1e3a8a', '#2563eb', '#0891b2', '#059669'];
		const clickable = dd_opts.module && dd_opts.dimension;
		const html = data.map((d, i) => {
			const pct = max ? Math.max((d.value / max * 100), 10) : 10;
			return `
			<div class="sawd-funnel-step${clickable ? ' sawd-drillable' : ''}"
				data-label="${d.label}" data-value="${d.value}"
				style="${clickable ? 'cursor:pointer' : ''}">
				<div class="sawd-funnel-name">${d.label}</div>
				<div class="sawd-funnel-bar-wrap">
					<div class="sawd-funnel-bar" style="width:${pct}%;background:${colors[i % colors.length]}">
						<span class="sawd-funnel-bar-label">${sawd_fmt_number(d.value)}</span>
					</div>
				</div>
				<div class="sawd-funnel-meta">${sawd_fmt_number(d.value)}</div>
			</div>`;
		}).join('');
		container.innerHTML = `<div class="sawd-funnel" style="padding:4px 0">${html}</div>`;
		if (clickable) {
			container.querySelectorAll('.sawd-funnel-step.sawd-drillable').forEach(el => {
				el.addEventListener('click', () => {
					this._open_drilldown(dd_opts.module, dd_opts.dimension, el.dataset.label, {}, el.dataset.label);
				});
			});
		}
	}

	_render_gauge($sel, rate, subtitle = '') {
		const container = document.querySelector($sel);
		if (!container) return;
		const r = 54, C = 2 * Math.PI * r;
		const filled = C * (Math.min(rate, 100) / 100);
		const color  = rate >= 80 ? '#059669' : rate >= 60 ? '#d97706' : '#dc2626';
		container.innerHTML = `
		<div class="sawd-gauge-wrap">
			<div class="sawd-gauge-ring">
				<svg viewBox="0 0 120 120">
					<circle class="sawd-gauge-bg" cx="60" cy="60" r="${r}" />
					<circle class="sawd-gauge-fill" cx="60" cy="60" r="${r}"
						stroke="${color}"
						style="stroke-dasharray:${filled}px ${C}px" />
				</svg>
				<div class="sawd-gauge-text">
					<div class="sawd-gauge-pct" style="color:${color}">${rate}%</div>
					<div class="sawd-gauge-lbl">Utilized</div>
				</div>
			</div>
			${subtitle ? `<div style="font-size:12px;color:var(--sawd-text3);text-align:center">${subtitle}</div>` : ''}
		</div>`;
	}

	// ── KPI card HTML helper ──────────────────────────────────────────────────

	_kpi(label, value, icon, variant, sub, dd = null) {
		const attrs = dd
			? ` class="sawd-kpi-card kpi-${variant} has-drilldown"
				data-dd-module="${dd.module}" data-dd-dim="${dd.dimension}"
				data-dd-val="${dd.value}" data-dd-title="${label}"`
			: ` class="sawd-kpi-card kpi-${variant}"`;
		const hint = dd ? `<div class="sawd-kpi-drill-hint"><i class="fa fa-search" style="font-size:9px"></i> Click to explore</div>` : '';
		return `
		<div${attrs}>
			<div class="sawd-kpi-accent"></div>
			<div class="sawd-kpi-icon">${icon}</div>
			<div class="sawd-kpi-label">${label}</div>
			<div class="sawd-kpi-value">${value}</div>
			${sub ? `<div class="sawd-kpi-sub">${sub}</div>` : ''}
			${hint}
		</div>`;
	}

	_chart_card(id, title, subtitle, tip, badge) {
		return `
		<div class="sawd-chart-card" id="${id}">
			<div class="sawd-chart-header">
				<div class="sawd-chart-title-wrap">
					<div class="sawd-chart-title">${title}</div>
					${subtitle ? `<div class="sawd-chart-subtitle">${subtitle}</div>` : ''}
				</div>
				${badge ? `<div class="sawd-chart-badge">${badge}</div>` : ''}
			</div>
			<div class="sawd-chart-body"><div class="sawd-skeleton" style="height:180px"></div></div>
			${tip ? `<div class="sawd-chart-tip">💡 ${tip}</div>` : ''}
		</div>`;
	}

	_rate_card(id, title) {
		return `
		<div class="sawd-chart-card" id="${id}">
			<div class="sawd-chart-header">
				<div class="sawd-chart-title-wrap">
					<div class="sawd-chart-title">${title}</div>
					<div class="sawd-chart-subtitle">Live performance snapshot</div>
				</div>
			</div>
			<div class="sawd-chart-body"></div>
		</div>`;
	}

	_progress_bar(label, value, color) {
		const rate = Math.min(Math.max(value || 0, 0), 100);
		return `
		<div class="sawd-progress-item">
			<div class="sawd-progress-label">
				<span class="sawd-progress-name">${label}</span>
				<span class="sawd-progress-val">${sawd_rate_badge(rate)}</span>
			</div>
			<div class="sawd-progress-track">
				<div class="sawd-progress-fill" style="width:${rate}%;background:${color}"></div>
			</div>
		</div>`;
	}

	_empty_html(msg = 'No data available') {
		return `
		<div class="sawd-empty">
			<div class="sawd-empty-icon">📭</div>
			<div class="sawd-empty-title">${msg}</div>
		</div>`;
	}

	// CONTINUED IN PART 3 →
}
