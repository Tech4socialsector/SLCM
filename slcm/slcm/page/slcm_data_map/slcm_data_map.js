frappe.pages['slcm-data-map'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'SLCM Data Entry Map',
		single_column: true,
	});

	const page = wrapper.page;

	// ── Print button — opens isolated print window ────────────────────────────
	page.add_inner_button('🖨 Print', () => {
		const content = document.querySelector('.sdm-wrap');
		if (!content) return;

		const win = window.open('', '_blank', 'width=1200,height=800');
		win.document.write(`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>SLCM Data Entry Map</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff; color: #1a202c; padding: 20px; }
.sdm-wrap { max-width: 100%; }
.sdm-header { text-align: center; margin-bottom: 24px; }
.sdm-header h1 { font-size: 22px; font-weight: 800; margin-bottom: 4px; }
.sdm-header p { font-size: 11px; color: #666; }
.sdm-quickstart { background: #1e3a5f; border-radius: 10px; padding: 14px 18px; margin-bottom: 24px; color: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.sdm-quickstart h3 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; margin-bottom: 10px; opacity: .75; }
.sdm-qs-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
.sdm-qs-item { background: rgba(255,255,255,.2); border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: 600; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.sdm-qs-arrow { font-size: 13px; opacity: .6; }
.sdm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.sdm-card { border-radius: 10px; border: 1px solid #dde; overflow: hidden; break-inside: avoid; }
.sdm-card-header { padding: 10px 14px 8px; display: flex; align-items: center; gap: 8px; }
.sdm-stage-badge { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 800; color: #fff; flex-shrink: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.sdm-card-title { font-size: 12px; font-weight: 700; flex: 1; }
.sdm-card-emoji { font-size: 15px; }
.sdm-dep-note { font-size: 9px; color: #888; font-style: italic; padding: 0 14px 6px; }
.sdm-divider { height: 1px; background: #eee; margin: 0 14px; }
.sdm-doc-list { padding: 8px 14px 10px; display: flex; flex-direction: column; gap: 3px; }
.sdm-doc-item { display: flex; align-items: center; gap: 6px; padding: 3px 0; text-decoration: none; color: inherit; }
.sdm-doc-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.sdm-doc-name { font-size: 11px; font-weight: 500; }
.sdm-doc-arrow { display: none; }
@media print {
  body { padding: 10px; }
  .sdm-grid { grid-template-columns: repeat(3, 1fr); }
  .sdm-card { break-inside: avoid; }
}
</style>
</head>
<body>${content.outerHTML}</body>
</html>`);
		win.document.close();
		win.focus();
		setTimeout(() => { win.print(); win.close(); }, 500);
	});

	// ── Styles ────────────────────────────────────────────────────────────────
	if (!document.getElementById('sdm-styles')) {
		const style = document.createElement('style');
		style.id = 'sdm-styles';
		style.textContent = `
		/* ── Layout ──────────────────────────────────────────────── */
		.sdm-wrap {
			max-width: 1200px;
			margin: 0 auto;
			padding: 24px 20px 60px;
			font-family: var(--font-stack);
		}
		.sdm-header {
			text-align: center;
			margin-bottom: 32px;
		}
		.sdm-header h1 {
			font-size: 26px;
			font-weight: 800;
			color: var(--text-color);
			margin: 0 0 6px;
		}
		.sdm-header p {
			color: var(--text-muted);
			font-size: 13px;
			margin: 0;
		}

		/* ── Quick start banner ───────────────────────────────────── */
		.sdm-quickstart {
			background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
			border-radius: 14px;
			padding: 20px 24px;
			margin-bottom: 36px;
			color: #fff;
		}
		.sdm-quickstart h3 {
			font-size: 13px;
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: .8px;
			margin: 0 0 12px;
			color: #facc15;
			opacity: 1;
		}
		.sdm-qs-flow {
			display: flex;
			align-items: center;
			flex-wrap: wrap;
			gap: 6px;
		}
		.sdm-qs-item {
			background: rgba(255,255,255,.18);
			border-radius: 8px;
			padding: 6px 14px;
			font-size: 12.5px;
			font-weight: 600;
			cursor: pointer;
			transition: background .15s;
			white-space: nowrap;
			color: #fff;
			text-decoration: none;
		}
		.sdm-qs-item:hover { background: rgba(255,255,255,.32); color: #fff; }
		.sdm-qs-arrow {
			font-size: 16px;
			opacity: .6;
		}

		/* ── Stage grid ───────────────────────────────────────────── */
		.sdm-grid {
			display: grid;
			grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
			gap: 20px;
		}

		/* ── Stage card ───────────────────────────────────────────── */
		.sdm-card {
			border-radius: 14px;
			border: 1.5px solid var(--border-color);
			background: var(--card-bg);
			overflow: hidden;
			box-shadow: 0 1px 6px rgba(0,0,0,.06);
			transition: box-shadow .2s, transform .2s;
		}
		.sdm-card:hover {
			box-shadow: 0 6px 24px rgba(0,0,0,.1);
			transform: translateY(-2px);
		}
		.sdm-card-header {
			padding: 14px 18px 12px;
			display: flex;
			align-items: center;
			gap: 10px;
		}
		.sdm-stage-badge {
			width: 28px;
			height: 28px;
			border-radius: 50%;
			display: flex;
			align-items: center;
			justify-content: center;
			font-size: 11px;
			font-weight: 800;
			color: #fff;
			flex-shrink: 0;
		}
		.sdm-card-title {
			font-size: 13.5px;
			font-weight: 700;
			color: var(--text-color);
			flex: 1;
		}
		.sdm-card-emoji {
			font-size: 18px;
		}
		.sdm-dep-note {
			font-size: 10px;
			color: var(--text-muted);
			font-style: italic;
			padding: 0 18px 8px;
		}
		.sdm-divider {
			height: 1px;
			background: var(--border-color);
			margin: 0 18px;
		}
		.sdm-doc-list {
			padding: 10px 18px 14px;
			display: flex;
			flex-direction: column;
			gap: 5px;
		}
		.sdm-doc-item {
			display: flex;
			align-items: center;
			gap: 8px;
			padding: 5px 10px;
			border-radius: 7px;
			cursor: pointer;
			transition: background .15s;
			text-decoration: none;
		}
		.sdm-doc-item:hover {
			background: var(--fg-hover-color, #f0f4ff);
		}
		.sdm-doc-dot {
			width: 7px;
			height: 7px;
			border-radius: 50%;
			flex-shrink: 0;
		}
		.sdm-doc-name {
			font-size: 12.5px;
			color: var(--text-color);
			font-weight: 500;
			flex: 1;
		}
		.sdm-doc-item:hover .sdm-doc-name {
			color: var(--primary);
		}
		.sdm-doc-arrow {
			font-size: 11px;
			color: var(--text-muted);
			opacity: 0;
			transition: opacity .15s;
		}
		.sdm-doc-item:hover .sdm-doc-arrow { opacity: 1; }
		.sdm-doc-count {
			font-size: 10px;
			background: var(--bg-blue, #e8f0fe);
			color: var(--primary);
			border-radius: 10px;
			padding: 1px 7px;
			font-weight: 700;
			min-width: 22px;
			text-align: center;
		}
		.sdm-doc-count.has-data {
			background: #dcfce7;
			color: #15803d;
		}
		.sdm-doc-count.no-data {
			background: #f1f5f9;
			color: #94a3b8;
		}

		/* ── Wide card (quick start min path) ───────────────────── */
		.sdm-card-wide {
			grid-column: 1 / -1;
		}

		/* ── Print ───────────────────────────────────────────────── */
		@media print {
			/* Hide all Frappe chrome */
			.navbar,
			.page-head,
			.layout-side-section,
			.sidebar-toggle-btn,
			.layout-main-section-wrapper > .page-head,
			.frappe-app > header,
			body > header,
			#navbar-main,
			.desk-sidebar,
			.page-toolbar,
			.page-actions,
			.page-head-content,
			.container-fluid.page-head,
			.standard-actions,
			.page-title,
			.custom-actions,
			.inner-toolbar,
			.col-md-2,
			.layout-side-section,
			[class*="sidebar"],
			.page-body > .container > .row > .col-md-2
			{ display: none !important; }

			/* Full-width content */
			html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
			.layout-main, .layout-main-section,
			.page-content, .layout-main-section-wrapper,
			.container, .row, [class*="col-"] {
				width: 100% !important;
				max-width: 100% !important;
				padding: 0 !important;
				margin: 0 !important;
				float: none !important;
			}

			/* Map styles */
			.sdm-wrap { padding: 10px !important; max-width: 100% !important; }
			.sdm-header p { display: block !important; }
			.sdm-quickstart { background: #1e3a5f !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
			.sdm-grid { grid-template-columns: repeat(3, 1fr) !important; gap: 10px !important; }
			.sdm-card { break-inside: avoid; box-shadow: none !important; border: 1px solid #ccc !important; }
			.sdm-card:hover { transform: none !important; }
			.sdm-stage-badge { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
			.sdm-doc-dot { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
			.sdm-doc-arrow { display: none !important; }
			.sdm-qs-item { background: rgba(255,255,255,.18) !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
		}
		`;
		document.head.appendChild(style);
	}

	// ── Stage definitions ─────────────────────────────────────────────────────
	const STAGES = [
		{
			num: 1,
			emoji: '🔧',
			title: 'Master Lookups',
			note: 'No dependencies — start here',
			color: '#6366f1',
			docs: [
				{ name: 'Gender',             dt: 'Gender' },
				{ name: 'Student Category',   dt: 'Student Category' },
				{ name: 'Skill',              dt: 'Skill' },
				{ name: 'Designation',        dt: 'Designation' },
				{ name: 'Condonation Reason', dt: 'Condonation Reason' },
				{ name: 'Department',         dt: 'Department' },
				{ name: 'Faculty',            dt: 'Faculty' },
				{ name: 'Room',               dt: 'Room' },
			],
		},
		{
			num: 2,
			emoji: '📅',
			title: 'Academic Calendar',
			note: 'Needs: Department',
			color: '#0ea5e9',
			docs: [
				{ name: 'Academic Year',    dt: 'Academic Year' },
				{ name: 'Academic Term',    dt: 'Academic Term' },
				{ name: 'Academic Holiday', dt: 'Academic Holiday' },
			],
		},
		{
			num: 3,
			emoji: '🏫',
			title: 'Programme Structure',
			note: 'Needs: Stage 1 + 2',
			color: '#10b981',
			docs: [
				{ name: 'Course Master',    dt: 'Course Master' },
				{ name: 'Course',           dt: 'Course' },
				{ name: 'Program',          dt: 'Program' },
				{ name: 'Curriculum',       dt: 'Curriculum' },
				{ name: 'Cohort',           dt: 'Cohort' },
				{ name: 'Course Offering',  dt: 'Course Offering' },
				{ name: 'Class Configuration', dt: 'Class Configuration' },
				{ name: 'Class Schedule',   dt: 'Class Schedule' },
			],
		},
		{
			num: 4,
			emoji: '📊',
			title: 'Assessment Config',
			note: 'Needs: Stage 3',
			color: '#f59e0b',
			docs: [
				{ name: 'Grading Schema',          dt: 'Grading Schema' },
				{ name: 'Evaluation Schema',        dt: 'Evaluation Schema' },
				{ name: 'Exam Assessment Type',     dt: 'Exam Assessment Type' },
				{ name: 'Exam Component',           dt: 'Exam Component' },
				{ name: 'CGPA Percentage Scale',    dt: 'CGPA Percentage Scale' },
				{ name: 'Course Schema Assignment', dt: 'Course Schema Assignment' },
				{ name: 'Access Result Settings',   dt: 'Access Result Settings' },
				{ name: 'Publish Result Setting',   dt: 'Publish Result Setting' },
			],
		},
		{
			num: 5,
			emoji: '🎓',
			title: 'Students',
			note: 'Needs: Stage 1–3',
			color: '#8b5cf6',
			docs: [
				{ name: 'Student Master',       dt: 'Student Master' },
				{ name: 'Student Parent',       dt: 'Student Parent' },
				{ name: 'Student Group',        dt: 'Student Group' },
				{ name: 'Student Group Student', dt: 'Student Group Student' },
			],
		},
		{
			num: 6,
			emoji: '📋',
			title: 'Enrollment',
			note: 'Needs: Stage 5',
			color: '#06b6d4',
			docs: [
				{ name: 'Program Enrollment',          dt: 'Program Enrollment' },
				{ name: 'Student Enrollment',          dt: 'Student Enrollment' },
				{ name: 'Student Enrollment Course',   dt: 'Student Enrollment Course' },
			],
		},
		{
			num: 7,
			emoji: '✅',
			title: 'Attendance',
			note: 'Needs: Stage 6',
			color: '#14b8a6',
			docs: [
				{ name: 'Attendance Session',              dt: 'Attendance Session' },
				{ name: 'Attendance Session Student',      dt: 'Attendance Session Student' },
				{ name: 'Student Attendance',              dt: 'Student Attendance' },
				{ name: 'FA MFA Application',              dt: 'FA MFA Application' },
				{ name: 'Student Attendance Condonation',  dt: 'Student Attendance Condonation' },
			],
		},
		{
			num: 8,
			emoji: '📝',
			title: 'Examination & Marks',
			note: 'Needs: Stage 6 + 7',
			color: '#ef4444',
			docs: [
				{ name: 'Exam Plan',                      dt: 'Exam Plan' },
				{ name: 'Student Course Marks',            dt: 'Student Course Marks' },
				{ name: 'Student Marks Entry',             dt: 'Student Marks Entry' },
				{ name: 'Re Exam Registration',            dt: 'Re Exam Registration' },
				{ name: 'Improvement Exam Registration',   dt: 'Improvement Exam Registration' },
				{ name: 'Grade Appeal',                    dt: 'Grade Appeal' },
				{ name: 'Exam Barcode',                    dt: 'Exam Barcode' },
				{ name: 'Student Result Publish',          dt: 'Student Result Publish' },
				{ name: 'Student Transcript',              dt: 'Student Transcript' },
			],
		},
		{
			num: 9,
			emoji: '💰',
			title: 'Fees',
			note: 'Needs: Stage 5–6',
			color: '#f97316',
			docs: [
				{ name: 'Fee Structure',    dt: 'Fee Structure' },
				{ name: 'Fee Invoice',      dt: 'Fee Invoice' },
				{ name: 'Fee Payment',      dt: 'Fee Payment' },
			],
		},
		{
			num: 10,
			emoji: '📥',
			title: 'Admission',
			note: 'Parallel to Stage 5 — independent',
			color: '#ec4899',
			docs: [
				{ name: 'Admission Cycle',       dt: 'Admission Cycle' },
				{ name: 'Applicant',             dt: 'Applicant' },
				{ name: 'Admission Application', dt: 'Admission Application' },
				{ name: 'Offer Letter',          dt: 'Offer Letter' },
				{ name: 'Merit List',            dt: 'Merit List' },
			],
		},
		{
			num: 11,
			emoji: '🪪',
			title: 'ID Cards',
			note: 'Needs: Stage 5',
			color: '#6366f1',
			docs: [
				{ name: 'ID Card Template',   dt: 'ID Card Template' },
				{ name: 'ID Card Generation', dt: 'ID Card Generation' },
			],
		},
		{
			num: 12,
			emoji: '🏛️',
			title: 'Venue Booking',
			note: 'Needs: Room (Stage 1)',
			color: '#0ea5e9',
			docs: [
				{ name: 'Venue Booking', dt: 'Venue Booking' },
			],
		},
		{
			num: 13,
			emoji: '🏆',
			title: 'Promotion',
			note: 'Needs: Stage 6 + Exam results',
			color: '#10b981',
			docs: [
				{ name: 'Promotion Policy',  dt: 'Promotion Policy' },
				{ name: 'Student Promotion', dt: 'Student Promotion' },
			],
		},
		{
			num: 14,
			emoji: '🏠',
			title: 'Hostel',
			note: 'Needs: Stage 5',
			color: '#8b5cf6',
			docs: [
				{ name: 'Hostel',            dt: 'Hostel' },
				{ name: 'Hostel Block',      dt: 'Hostel Block' },
				{ name: 'Hostel Floor',      dt: 'Hostel Floor' },
				{ name: 'Hostel Room',       dt: 'Hostel Room' },
				{ name: 'Hostel Bed',        dt: 'Hostel Bed' },
				{ name: 'Hostel Allocation', dt: 'Hostel Allocation' },
			],
		},
		{
			num: 15,
			emoji: '💼',
			title: 'Placement',
			note: 'Needs: Stage 5',
			color: '#f59e0b',
			docs: [
				{ name: 'Placement Opportunity',  dt: 'Placement Opportunity' },
				{ name: 'Placement Application',  dt: 'Placement Application' },
				{ name: 'Placement Offer',        dt: 'Placement Offer' },
			],
		},
	];

	const QUICKSTART = [
		'Department', 'Academic Year', 'Academic Term',
		'Program', 'Course', 'Cohort', 'Course Offering',
		'Student Master', 'Student Enrollment', 'Student Enrollment Course',
		'Exam Plan', 'Student Course Marks', 'Student Result Publish',
	];

	// ── Render ────────────────────────────────────────────────────────────────
	function dt_url(dt) {
		return `/app/${frappe.router.slug(dt)}`;
	}

	function render_doc(doc, counts) {
		const cnt = (counts && counts[doc.dt] !== undefined) ? counts[doc.dt] : '…';
		const cls = cnt === '…' ? '' : (cnt > 0 ? 'has-data' : 'no-data');
		return `
		<a class="sdm-doc-item" href="${dt_url(doc.dt)}" target="_blank">
			<span class="sdm-doc-dot" style="background:${doc.color || '#888'}"></span>
			<span class="sdm-doc-name">${doc.name}</span>
			<span class="sdm-doc-count ${cls}">${cnt}</span>
			<span class="sdm-doc-arrow">↗</span>
		</a>`;
	}

	function render_card(stage, counts) {
		const docs_html = stage.docs.map(d => render_doc({ ...d, color: stage.color }, counts)).join('');
		const total = counts
			? stage.docs.reduce((s, d) => s + (counts[d.dt] || 0), 0)
			: null;
		const total_badge = total !== null
			? `<span class="sdm-doc-count ${total > 0 ? 'has-data' : 'no-data'}" style="margin-left:auto;margin-right:4px">${total}</span>`
			: '';
		return `
		<div class="sdm-card">
			<div class="sdm-card-header">
				<div class="sdm-stage-badge" style="background:${stage.color}">${stage.num}</div>
				<div class="sdm-card-title">${stage.title}</div>
				${total_badge}
				<span class="sdm-card-emoji">${stage.emoji}</span>
			</div>
			${stage.note ? `<div class="sdm-dep-note">↳ ${stage.note}</div>` : ''}
			<div class="sdm-divider"></div>
			<div class="sdm-doc-list">${docs_html}</div>
		</div>`;
	}

	function render_all(counts) {
		const qs_html = QUICKSTART.map((dt, i) => {
			const cnt = counts ? counts[dt] : null;
			const badge = cnt !== null
				? ` <span style="background:rgba(255,255,255,.25);border-radius:8px;padding:1px 6px;font-size:10px;margin-left:4px">${cnt}</span>`
				: '';
			const arrow = i < QUICKSTART.length - 1 ? `<span class="sdm-qs-arrow">→</span>` : '';
			return `<a class="sdm-qs-item" href="${dt_url(dt)}" target="_blank">${dt}${badge}</a>${arrow}`;
		}).join('');

		const cards_html = STAGES.map(s => render_card(s, counts)).join('');

		$(wrapper).find('.page-content').html(`
			<div class="sdm-wrap">
				<div class="sdm-header">
					<h1>📌 SLCM Data Entry Map</h1>
					<p>Follow the stages in order — each stage depends on the ones before it. Click any doctype to open its list.</p>
				</div>

				<div class="sdm-quickstart">
					<h3>⚡ Minimum Viable Path — Quick Start</h3>
					<div class="sdm-qs-flow">${qs_html}</div>
				</div>

				<div class="sdm-grid">${cards_html}</div>
			</div>
		`);
	}

	// Render immediately with loading placeholders, then fill counts
	render_all(null);

	frappe.call({
		method: 'slcm.slcm.page.slcm_data_map.slcm_data_map.get_doctype_counts',
		callback(r) {
			if (r.message) render_all(r.message);
		},
	});
};
