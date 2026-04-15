// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.pages["transcript-management-page"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Transcript Management"),
		single_column: true,
	});

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
		// Display labels for active filter tags (ID → human label)
		_prog_labels:   {},
		_dept_labels:   {},
	};

	// ── Build page ─────────────────────────────────────────────────────────────
	$(wrapper).find(".page-content").html(`
		<div class="transcript-mgmt-wrap" style="padding:16px">
			<!-- Toolbar -->
			<div class="tm-toolbar" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;">
				<div style="flex:1;min-width:260px;max-width:420px;position:relative;">
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="position:absolute;left:10px;top:50%;transform:translateY(-50%)">
						<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
					</svg>
					<input id="tm-search" type="text" placeholder="${__('Search by Student Name, Registration ID, Email')}"
						style="width:100%;padding:7px 10px 7px 32px;border:1px solid #d1d8dd;border-radius:5px;font-size:13px;outline:none;box-sizing:border-box;" />
				</div>
				<div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
					<button id="tm-filter-btn" class="btn btn-default btn-sm" style="border:1px solid #c84630;color:#c84630;background:white;display:flex;align-items:center;gap:4px;">
						<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
						${__("Filter")}
					</button>
					<!-- Generate split button -->
					<div class="btn-group">
						<button type="button" class="btn btn-default btn-sm dropdown-toggle"
							data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"
							style="border:1px solid #c84630;color:#c84630;background:white;">
							${__("Generate")} <span class="caret" style="margin-left:4px;"></span>
						</button>
						<ul class="dropdown-menu dropdown-menu-right">
							<li><a id="tm-gen-interim" href="#">${__("Generate Interim Transcript")}</a></li>
							<li><a id="tm-gen-final"   href="#">${__("Generate Final Transcript")}</a></li>
							<li role="separator" class="divider"></li>
							<li><a id="tm-gen-all-interim" href="#">${__("Generate Interim – All Filtered")}</a></li>
							<li><a id="tm-gen-all-final"   href="#">${__("Generate Final – All Filtered")}</a></li>
						</ul>
					</div>
					<!-- Download split button -->
					<div class="btn-group">
						<button type="button" class="btn btn-default btn-sm dropdown-toggle"
							data-toggle="dropdown" aria-haspopup="true" aria-expanded="false"
							style="border:1px solid #c84630;color:#c84630;background:white;">
							${__("Download")} <span class="caret" style="margin-left:4px;"></span>
						</button>
						<ul class="dropdown-menu dropdown-menu-right">
							<li><a id="tm-dl-interim" href="#">${__("Download Interim Transcript")}</a></li>
							<li><a id="tm-dl-final"   href="#">${__("Download Final Transcript")}</a></li>
						</ul>
					</div>
					<!-- Settings / Templates icon -->
					<button id="tm-settings-btn" title="${__('Transcript Templates')}"
						style="width:32px;height:32px;border:1px solid #d1d8dd;border-radius:5px;
						       background:white;cursor:pointer;display:inline-flex;align-items:center;
						       justify-content:center;padding:0;transition:border-color .15s,color .15s;"
						onmouseover="this.style.borderColor='#c84630';this.style.color='#c84630';"
						onmouseout="this.style.borderColor='#d1d8dd';this.style.color='inherit';">
						<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24"
							fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<circle cx="12" cy="12" r="3"/>
							<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06
							         a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09
							         A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83
							         l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09
							         A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83
							         l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09
							         a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83
							         l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09
							         a1.65 1.65 0 0 0-1.51 1z"/>
						</svg>
					</button>
				</div>
			</div>

			<!-- Filter Panel -->
			<div id="tm-filter-panel" style="display:none;background:#f9fafb;border:1px solid #e4e7ea;border-radius:6px;padding:14px 18px;margin-bottom:12px;">
				<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;">
					<div>
						<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px;">${__("Programme")}</label>
						<select id="tm-f-programme" class="tm-filter-select" style="width:100%;padding:6px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:13px;">
							<option value="">${__("All Programmes")}</option>
						</select>
					</div>
					<div>
						<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px;">${__("Department")}</label>
						<select id="tm-f-department" class="tm-filter-select" style="width:100%;padding:6px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:13px;">
							<option value="">${__("All Departments")}</option>
						</select>
					</div>
					<div>
						<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px;">${__("Course")}</label>
						<select id="tm-f-course" class="tm-filter-select" style="width:100%;padding:6px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:13px;">
							<option value="">${__("All Courses")}</option>
						</select>
					</div>
					<div>
						<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px;">${__("Academic Year")}</label>
						<select id="tm-f-academic-year" class="tm-filter-select" style="width:100%;padding:6px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:13px;">
							<option value="">${__("All Years")}</option>
						</select>
					</div>
					<div>
						<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px;">${__("Batch")}</label>
						<select id="tm-f-batch" class="tm-filter-select" style="width:100%;padding:6px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:13px;">
							<option value="">${__("All Batches")}</option>
						</select>
					</div>
					<div>
						<label style="font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:4px;">${__("Student Status")}</label>
						<select id="tm-f-status" class="tm-filter-select" style="width:100%;padding:6px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:13px;">
							<option value="">${__("All Statuses")}</option>
						</select>
					</div>
				</div>
				<div style="margin-top:12px;display:flex;gap:8px;">
					<button id="tm-apply-filter" class="btn btn-sm btn-primary">${__("Apply Filters")}</button>
					<button id="tm-clear-filter" class="btn btn-sm btn-default">${__("Clear All")}</button>
				</div>
			</div>

			<!-- Active Filter Tags -->
			<div id="tm-active-tags" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;"></div>

			<!-- Table -->
			<div id="tm-table-wrap" style="border:1px solid #e4e7ea;border-radius:6px;overflow:hidden;">
				<table class="table table-hover" style="margin-bottom:0;width:100%;">
					<thead>
						<tr style="background:#f9fafb;border-bottom:2px solid #e4e7ea;">
							<th style="width:36px;padding:10px 14px;">
								<input type="checkbox" id="tm-select-all" title="${__('Select All on this page')}"/>
							</th>
							<th class="tm-sortable" data-sort="student_name"
								style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;cursor:pointer;user-select:none;">
								${__("Student")} <span id="tm-count-badge" style="font-weight:400;color:#888;font-size:11px;"></span>
								<span class="sort-indicator" data-col="student_name">↕</span>
							</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;">${__("Learning Pathway(s)")}</th>
							<th class="tm-sortable" data-sort="registration_id"
								style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;cursor:pointer;user-select:none;white-space:nowrap;">
								${__("Reg. ID")} <span class="sort-indicator" data-col="registration_id">↓</span>
							</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;white-space:nowrap;">${__("Earned / Total Credits")}</th>
							<th class="tm-sortable" data-sort="cgpa"
								style="font-size:12px;font-weight:700;color:#c84630;padding:10px 14px;cursor:pointer;user-select:none;">
								${__("CGPA")} <span class="sort-indicator" data-col="cgpa">↕</span>
							</th>
							<th style="font-size:12px;font-weight:700;color:#c84630;padding:10px 14px;">${__("Interim Transcript")}</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;">${__("Final Transcript")}</th>
						</tr>
					</thead>
					<tbody id="tm-tbody">
						<tr id="tm-loading-row">
							<td colspan="8" style="text-align:center;padding:40px;color:#888;">
								<div class="spinner" style="margin:0 auto 8px;width:28px;height:28px;border:3px solid #e4e7ea;border-top-color:#c84630;border-radius:50%;animation:tm-spin .8s linear infinite;"></div>
								${__("Loading students...")}
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- Pagination -->
			<div id="tm-pagination" style="display:flex;align-items:center;justify-content:space-between;margin-top:12px;flex-wrap:wrap;gap:8px;">
				<span id="tm-page-info" style="font-size:12px;color:#777;"></span>
				<div style="display:flex;gap:6px;align-items:center;">
					<select id="tm-page-length" style="padding:4px 8px;border:1px solid #d1d8dd;border-radius:4px;font-size:12px;">
						<option value="25" ${state.page_length===25?'selected':''}>25 ${__("per page")}</option>
						<option value="50" ${state.page_length===50?'selected':''}>50 ${__("per page")}</option>
						<option value="100" ${state.page_length===100?'selected':''}>100 ${__("per page")}</option>
					</select>
					<button id="tm-prev" class="btn btn-xs btn-default">‹ ${__("Prev")}</button>
					<span id="tm-page-current" style="font-size:12px;padding:0 4px;"></span>
					<button id="tm-next" class="btn btn-xs btn-default">${__("Next")} ›</button>
				</div>
			</div>
		</div>
		<style>
		@keyframes tm-spin { to { transform: rotate(360deg); } }
		.tm-row-avatar { width:36px;height:36px;border-radius:50%;object-fit:cover; }
		.tm-avatar-initials { width:36px;height:36px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:#c84630;color:white;font-weight:700;font-size:14px;flex-shrink:0; }
		.tm-tag { display:inline-flex;align-items:center;gap:4px;padding:2px 8px 2px 10px;background:#f0f0f0;border-radius:12px;font-size:11px;color:#444; }
		.tm-tag button { background:none;border:none;padding:0;line-height:1;cursor:pointer;color:#888;margin-left:2px;font-size:13px; }
		.tm-tag button:hover { color:#c84630; }
		.tm-transcript-badge { font-size:11px;font-weight:600;padding:3px 10px;border-radius:10px;display:inline-block; }
		.tm-transcript-badge.generated { background:#e6f4ea;color:#1e7e34; }
		.tm-transcript-badge.revoked   { background:#fdecea;color:#c0392b; }
		.tm-transcript-badge.pending   { background:#fff3cd;color:#856404; }
		.tm-transcript-badge.na        { color:#bbb; }
		#tm-tbody tr:hover { background:#fdf5f5; }
		.tm-sortable:hover { background:#f0f0f0; }
		.sort-indicator { font-size:10px;color:#aaa;margin-left:2px; }
		.sort-indicator.active-asc  { color:#c84630; }
		.sort-indicator.active-desc { color:#c84630; }
		</style>
	`);

	// ── Event Bindings ─────────────────────────────────────────────────────────

	// Search with debounce
	let searchTimer;
	$(wrapper).on("input", "#tm-search", function () {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			state.search = $(this).val().trim();
			state.page   = 1;
			load_students();
		}, 350);
	});

	// Filter toggle
	$(wrapper).on("click", "#tm-filter-btn", function () {
		const panel = $(wrapper).find("#tm-filter-panel");
		panel.slideToggle(150);
		if (!state.filter_options) {
			load_filter_options();
		}
	});

	// Apply filters
	$(wrapper).on("click", "#tm-apply-filter", function () {
		state.programme      = $(wrapper).find("#tm-f-programme").val();
		state.department     = $(wrapper).find("#tm-f-department").val();
		state.course         = $(wrapper).find("#tm-f-course").val();
		state.academic_year  = $(wrapper).find("#tm-f-academic-year").val();
		state.batch          = $(wrapper).find("#tm-f-batch").val();
		state.student_status = $(wrapper).find("#tm-f-status").val();
		state.page           = 1;
		render_active_tags();
		load_students();
	});

	// Clear filters
	$(wrapper).on("click", "#tm-clear-filter", function () {
		$(wrapper).find(".tm-filter-select").val("");
		state.programme = state.department = state.course =
		state.academic_year = state.batch = state.student_status = "";
		state.page = 1;
		render_active_tags();
		load_students();
	});

	// Select all (current page)
	$(wrapper).on("change", "#tm-select-all", function () {
		const checked = $(this).is(":checked");
		$(wrapper).find(".tm-row-check").prop("checked", checked);
		$(wrapper).find(".tm-row-check").each(function () {
			const sid = $(this).data("student");
			if (checked) { state.selected.add(sid); }
			else         { state.selected.delete(sid); }
		});
	});

	// Row checkboxes
	$(wrapper).on("change", ".tm-row-check", function () {
		const sid = $(this).data("student");
		if ($(this).is(":checked")) { state.selected.add(sid); }
		else                         { state.selected.delete(sid); }
		const total = $(wrapper).find(".tm-row-check").length;
		const sel   = $(wrapper).find(".tm-row-check:checked").length;
		$(wrapper).find("#tm-select-all")
			.prop("indeterminate", sel > 0 && sel < total)
			.prop("checked", sel === total && total > 0);
	});

	// Generate – selected students
	$(wrapper).on("click", "#tm-gen-interim", function (e) {
		e.preventDefault();
		handle_generate("Interim", false);
	});
	$(wrapper).on("click", "#tm-gen-final", function (e) {
		e.preventDefault();
		handle_generate("Final", false);
	});

	// Generate – all filtered students
	$(wrapper).on("click", "#tm-gen-all-interim", function (e) {
		e.preventDefault();
		handle_generate("Interim", true);
	});
	$(wrapper).on("click", "#tm-gen-all-final", function (e) {
		e.preventDefault();
		handle_generate("Final", true);
	});

	// Download
	$(wrapper).on("click", "#tm-dl-interim", function (e) {
		e.preventDefault();
		handle_download("Interim");
	});
	$(wrapper).on("click", "#tm-dl-final", function (e) {
		e.preventDefault();
		handle_download("Final");
	});

	// Settings / Templates navigation
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

	// Pagination
	$(wrapper).on("click", "#tm-prev", function () {
		if (state.page > 1) { state.page--; load_students(); }
	});
	$(wrapper).on("click", "#tm-next", function () {
		const total_pages = Math.ceil(state.total / state.page_length);
		if (state.page < total_pages) { state.page++; load_students(); }
	});
	$(wrapper).on("change", "#tm-page-length", function () {
		state.page_length = parseInt($(this).val());
		state.page = 1;
		load_students();
	});

	// ── Functions ──────────────────────────────────────────────────────────────

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

				// Restore current selections
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

		const tbody = $(wrapper).find("#tm-tbody");
		tbody.html(`
			<tr id="tm-loading-row">
				<td colspan="8" style="text-align:center;padding:40px;color:#888;">
					<div class="spinner" style="margin:0 auto 8px;width:28px;height:28px;border:3px solid #e4e7ea;border-top-color:#c84630;border-radius:50%;animation:tm-spin .8s linear infinite;"></div>
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
			},
			error: function () {
				state.loading = false;
				tbody.html(`<tr><td colspan="8" style="text-align:center;padding:28px;color:#c84630;">${__("Error loading students. Please try again.")}</td></tr>`);
			}
		});
	}

	function render_table(students, total) {
		const tbody = $(wrapper).find("#tm-tbody");

		$(wrapper).find("#tm-count-badge").text(`(${total})`);

		if (!students || students.length === 0) {
			tbody.html(`<tr><td colspan="8" style="text-align:center;padding:48px;color:#888;">
				<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ddd" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block;margin:0 auto 10px"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
				${__("No students found matching the current filters.")}
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
				? `<img src="${s.photo}" class="tm-row-avatar" style="flex-shrink:0;" onerror="this.outerHTML='<div class=\'tm-avatar-initials\'>${initials}</div>'">`
				: `<div class="tm-avatar-initials">${initials}</div>`;

			// Learning pathways
			let pathwayHtml = `<span style="color:#bbb;">—</span>`;
			if (s.learning_pathways && s.learning_pathways.length) {
				pathwayHtml = s.learning_pathways.map(p => {
					const type  = frappe.utils.escape_html(p.type || "Major");
					const pname = frappe.utils.escape_html(p.program_name || p.program || "");
					return `<div style="font-size:12px;"><span style="color:#888;font-size:11px;">${type}</span> · <strong style="color:#333;">${pname}</strong></div>`;
				}).join("");
			}

			// Credits
			const earned = s.earned_credits || 0;
			const total_c = s.total_credits || 0;
			const credHtml = `<span style="font-weight:600;">${earned}</span><span style="color:#aaa;">/</span><span style="color:#777;">${total_c}</span>`;

			// CGPA
			let cgpaHtml = `<span style="color:#bbb;">—</span>`;
			if (s.cgpa !== null && s.cgpa !== undefined && s.cgpa !== "") {
				const cgpaVal = parseFloat(s.cgpa);
				const color = cgpaVal >= 7.0 ? "#198754" : cgpaVal >= 5.0 ? "#fd7e14" : "#dc3545";
				cgpaHtml = `<span style="font-weight:700;color:${color};">${cgpaVal.toFixed(2)}</span>`;
			}

			const interimHtml = badge_html(s.interim_transcript);
			const finalHtml   = badge_html(s.final_transcript);

			// Sub-info line under student name
			const subInfo = [prog, batch, acYear].filter(Boolean).join(" · ");

			return `
				<tr style="border-bottom:1px solid #f1f3f5;" data-student="${s.student}">
					<td style="padding:10px 14px;vertical-align:middle;">
						<input type="checkbox" class="tm-row-check" data-student="${s.student}" ${checked} />
					</td>
					<td style="padding:10px 14px;vertical-align:middle;">
						<div style="display:flex;align-items:flex-start;gap:10px;">
							${photoSrc}
							<div>
								<div><a href="/app/student-master/${s.student}" style="font-weight:600;color:#c84630;font-size:13px;">${name}</a></div>
								<div style="font-size:11px;color:#aaa;">${email}</div>
								${subInfo ? `<div style="font-size:11px;color:#555;margin-top:2px;">${subInfo}</div>` : ""}
							</div>
						</div>
					</td>
					<td style="padding:10px 14px;vertical-align:middle;">${pathwayHtml}</td>
					<td style="padding:10px 14px;vertical-align:middle;font-size:12px;color:#555;">${regId}</td>
					<td style="padding:10px 14px;vertical-align:middle;text-align:center;">${credHtml}</td>
					<td style="padding:10px 14px;vertical-align:middle;text-align:center;">${cgpaHtml}</td>
					<td style="padding:10px 14px;vertical-align:middle;text-align:center;">${interimHtml}</td>
					<td style="padding:10px 14px;vertical-align:middle;text-align:center;">${finalHtml}</td>
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

	function badge_html(status) {
		if (!status) return `<span class="tm-transcript-badge na">—</span>`;
		const s = status.toLowerCase();
		if (s === "generated") return `<span class="tm-transcript-badge generated">${__("Generated")}</span>`;
		if (s === "revoked")   return `<span class="tm-transcript-badge revoked">${__("Revoked")}</span>`;
		return `<span class="tm-transcript-badge pending">${frappe.utils.escape_html(status)}</span>`;
	}

	function render_pagination() {
		const total_pages = Math.ceil(state.total / state.page_length) || 1;
		const from = state.total ? (state.page - 1) * state.page_length + 1 : 0;
		const to   = Math.min(state.page * state.page_length, state.total);

		$(wrapper).find("#tm-page-info").text(
			state.total
				? `${__("Showing")} ${from}–${to} ${__("of")} ${state.total} ${__("students")}`
				: __("No students found")
		);
		$(wrapper).find("#tm-page-current").text(`${__("Page")} ${state.page} / ${total_pages}`);
		$(wrapper).find("#tm-prev").prop("disabled", state.page <= 1);
		$(wrapper).find("#tm-next").prop("disabled", state.page >= total_pages);
	}

	// Maps state key → filter select element ID (avoids the broken string-replace approach)
	const FILTER_KEY_TO_ID = {
		programme:      "tm-f-programme",
		department:     "tm-f-department",
		course:         "tm-f-course",
		academic_year:  "tm-f-academic-year",
		batch:          "tm-f-batch",
		student_status: "tm-f-status",   // ← was broken: replace("_","-") gave "tm-f-student-status"
	};

	// Maps state key → human-readable label for active filter tags
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

		// Use display name where available
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
					<button data-key="${key}" title="${__('Remove filter')}">✕</button>
				</span>
			`);
			tag.find("button").on("click", function () {
				const k = $(this).data("key");
				state[k] = "";
				const selectId = FILTER_KEY_TO_ID[k];
				if (selectId) $(wrapper).find(`#${selectId}`).val("");
				render_active_tags();
				state.page = 1;
				load_students();
			});
			container.append(tag);
		});
	}

	function update_sort_indicators() {
		$(wrapper).find(".sort-indicator").removeClass("active-asc active-desc").text("↕");
		const ind = $(wrapper).find(`.sort-indicator[data-col="${state.sort_by}"]`);
		if (state.sort_order === "asc") {
			ind.addClass("active-asc").text("↑");
		} else {
			ind.addClass("active-desc").text("↓");
		}
	}

	function get_selected_students() {
		return [...state.selected];
	}

	/**
	 * Generate transcripts.
	 * @param {string} type        - "Interim" or "Final"
	 * @param {boolean} all_filtered - true = generate for ALL filtered students (ignores selection)
	 */
	function handle_generate(type, all_filtered) {
		if (all_filtered) {
			// Generate for every student matching the current filters
			const filterDesc = build_filter_description();
			const msg = filterDesc
				? __("Generate {0} Transcript for ALL students matching: {1}?", [type, filterDesc])
				: __("Generate {0} Transcript for ALL {1} students?", [type, state.total]);

			frappe.confirm(msg, function () {
				// Fetch all student IDs matching current filters (no pagination)
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
						const all_ids = r.message.students.map(s => s.student);
						do_generate(all_ids, type);
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
					message: ok + " " + __("transcript(s) generated.") + (err ? " " + err + " " + __("failed.") : ""),
					indicator: err ? "orange" : "green",
				}, 5);
				state.selected.clear();
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

		frappe.call({
			method: "slcm.slcm.page.transcript_management_page.transcript_management_page.download_transcript",
			args: { student: students[0], transcript_type: type },
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
				// Server throws if transcript not yet generated
				frappe.msgprint({
					title:   __("Transcript Not Found"),
					message: __("No {0} transcript exists for this student. Please generate it first.", [type]),
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
	load_students();
};
