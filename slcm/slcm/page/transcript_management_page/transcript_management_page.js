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
					<div class="btn-group">
						<button id="tm-generate-btn" class="btn btn-default btn-sm" style="border:1px solid #c84630;color:#c84630;background:white;">
							${__("Generate")} <span class="caret" style="margin-left:2px;"></span>
						</button>
						<button type="button" class="btn btn-default btn-sm dropdown-toggle" data-toggle="dropdown" style="border:1px solid #c84630;color:#c84630;background:white;padding:5px 8px;">
							<span class="caret"></span>
						</button>
						<ul class="dropdown-menu dropdown-menu-right">
							<li><a id="tm-gen-interim" href="#">${__("Generate Interim Transcript")}</a></li>
							<li><a id="tm-gen-final"   href="#">${__("Generate Final Transcript")}</a></li>
						</ul>
					</div>
					<div class="btn-group">
						<button id="tm-download-btn" class="btn btn-default btn-sm" style="border:1px solid #c84630;color:#c84630;background:white;">
							${__("Download")} <span class="caret" style="margin-left:2px;"></span>
						</button>
						<button type="button" class="btn btn-default btn-sm dropdown-toggle" data-toggle="dropdown" style="border:1px solid #c84630;color:#c84630;background:white;padding:5px 8px;">
							<span class="caret"></span>
						</button>
						<ul class="dropdown-menu dropdown-menu-right">
							<li><a id="tm-dl-interim" href="#">${__("Download Interim Transcripts")}</a></li>
							<li><a id="tm-dl-final"   href="#">${__("Download Final Transcripts")}</a></li>
						</ul>
					</div>
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
								<input type="checkbox" id="tm-select-all" title="${__('Select All')}"/>
							</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;">
								${__("Student")} <span id="tm-count-badge" style="font-weight:400;color:#888;font-size:11px;"></span>
							</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;">${__("Learning Pathway(s)")}</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;white-space:nowrap;">${__("Earned / Total Credits")}</th>
							<th style="font-size:12px;font-weight:700;color:#c84630;padding:10px 14px;cursor:pointer;" id="th-cgpa" data-sort="cgpa">${__("CGPA")} <span class="sort-indicator">↕</span></th>
							<th style="font-size:12px;font-weight:700;color:#c84630;padding:10px 14px;">${__("Interim Transcript")}</th>
							<th style="font-size:12px;font-weight:700;color:#444;padding:10px 14px;">${__("Final Transcript")}</th>
						</tr>
					</thead>
					<tbody id="tm-tbody">
						<tr id="tm-loading-row">
							<td colspan="7" style="text-align:center;padding:40px;color:#888;">
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
		.tm-row-avatar { width:36px;height:36px;border-radius:50%;object-fit:cover;background:#e4e7ea; }
		.tm-tag { display:inline-flex;align-items:center;gap:4px;padding:2px 8px 2px 10px;background:#f0f0f0;border-radius:12px;font-size:11px;color:#444; }
		.tm-tag button { background:none;border:none;padding:0;line-height:1;cursor:pointer;color:#888;margin-left:2px; }
		.tm-transcript-badge { font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px; }
		.tm-transcript-badge.generated { background:#e6f4ea;color:#1e7e34; }
		.tm-transcript-badge.pending   { background:#fff3cd;color:#856404; }
		.tm-transcript-badge.na        { background:none;color:#bbb; }
		#tm-tbody tr:hover { background:#fdf5f5; }
		.sort-indicator { font-size:10px;color:#aaa; }
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

	// Select all
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
		$(wrapper).find("#tm-select-all").prop("indeterminate", sel > 0 && sel < total)
			.prop("checked", sel === total && total > 0);
	});

	// Generate Interim
	$(wrapper).on("click", "#tm-gen-interim", function (e) {
		e.preventDefault();
		handle_generate("Interim");
	});
	// Generate Final
	$(wrapper).on("click", "#tm-gen-final", function (e) {
		e.preventDefault();
		handle_generate("Final");
	});

	// Download Interim
	$(wrapper).on("click", "#tm-dl-interim", function (e) {
		e.preventDefault();
		handle_download("Interim");
	});
	// Download Final
	$(wrapper).on("click", "#tm-dl-final", function (e) {
		e.preventDefault();
		handle_download("Final");
	});

	// Primary Generate / Download buttons (default to Interim)
	$(wrapper).on("click", "#tm-generate-btn", function () {
		handle_generate("Interim");
	});
	$(wrapper).on("click", "#tm-download-btn", function () {
		handle_download("Final");
	});

	// Sort
	$(wrapper).on("click", "[data-sort]", function () {
		const col = $(this).data("sort");
		if (state.sort_by === col) {
			state.sort_order = state.sort_order === "asc" ? "desc" : "asc";
		} else {
			state.sort_by    = col;
			state.sort_order = "asc";
		}
		state.page = 1;
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
				const prog_sel  = $(wrapper).find("#tm-f-programme");
				const dept_sel  = $(wrapper).find("#tm-f-department");
				const course_sel= $(wrapper).find("#tm-f-course");
				const yr_sel    = $(wrapper).find("#tm-f-academic-year");
				const bat_sel   = $(wrapper).find("#tm-f-batch");
				const stat_sel  = $(wrapper).find("#tm-f-status");

				(r.message.programmes || []).forEach(p => {
					prog_sel.append(`<option value="${p.name}">${frappe.utils.escape_html(p.cohort_name || p.name)}</option>`);
				});
				(r.message.departments || []).forEach(d => {
					dept_sel.append(`<option value="${d.name}">${frappe.utils.escape_html(d.department_name || d.name)}</option>`);
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
				<td colspan="7" style="text-align:center;padding:40px;color:#888;">
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
				tbody.html(`<tr><td colspan="7" style="text-align:center;padding:28px;color:#c84630;">${__("Error loading students. Please try again.")}</td></tr>`);
			}
		});
	}

	function render_table(students, total) {
		const tbody  = $(wrapper).find("#tm-tbody");
		const startN = (state.page - 1) * state.page_length + 1;

		$(wrapper).find("#tm-count-badge").text(`(${total})`);

		if (!students || students.length === 0) {
			tbody.html(`<tr><td colspan="7" style="text-align:center;padding:40px;color:#888;"><div style="font-size:32px;margin-bottom:8px;">🎓</div>${__("No students found.")}</td></tr>`);
			return;
		}

		const rows = students.map((s, idx) => {
			const rowNum  = startN + idx;
			const name    = frappe.utils.escape_html(s.student_name || "");
			const regId   = frappe.utils.escape_html(s.registration_id || "");
			const email   = frappe.utils.escape_html(s.email || "");
			const prog    = frappe.utils.escape_html(s.programme_name || s.programme || "");
			const batch   = frappe.utils.escape_html(s.batch_year || "");
			const acYear  = frappe.utils.escape_html(s.academic_year || "");
			const checked = state.selected.has(s.student) ? "checked" : "";

			const photoSrc = s.photo ? `<img src="${s.photo}" class="tm-row-avatar" onerror="this.style.display='none'"/>` :
				`<div class="tm-row-avatar" style="display:inline-flex;align-items:center;justify-content:center;background:#c84630;color:white;font-weight:700;font-size:14px;">${(name[0] || "?").toUpperCase()}</div>`;

			// Learning pathways
			let pathwayHtml = "—";
			if (s.learning_pathways && s.learning_pathways.length) {
				pathwayHtml = s.learning_pathways.map(p => {
					const type = frappe.utils.escape_html(p.type || "Major");
					const pname = frappe.utils.escape_html(p.program_name || p.program || "");
					return `<div style="font-size:12px;"><span style="color:#888;">${type}</span> · <span style="color:#333;font-weight:500;">${pname}</span></div>`;
				}).join("");
			}

			// Credits
			const cred = `<span style="font-weight:600;">${s.earned_credits || 0}</span>/<span style="color:#777;">${s.total_credits || 0}</span>`;

			// CGPA
			let cgpaHtml = "—";
			if (s.cgpa !== null && s.cgpa !== undefined && s.cgpa !== "") {
				const cgpaVal = parseFloat(s.cgpa);
				const color = cgpaVal >= 3.5 ? "#198754" : cgpaVal >= 2.0 ? "#fd7e14" : "#dc3545";
				cgpaHtml = `<span style="font-weight:700;color:${color};">${cgpaVal.toFixed(2)}</span>`;
			}

			// Transcript badges
			const interimHtml = badge_html(s.interim_transcript);
			const finalHtml   = badge_html(s.final_transcript);

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
								<div style="font-size:11px;color:#777;">${regId}</div>
								<div style="font-size:11px;color:#aaa;">${email}</div>
								<div style="font-size:11px;color:#555;margin-top:2px;">${prog}${batch ? ' · '+batch : ''}${acYear ? ' · '+acYear : ''}</div>
							</div>
						</div>
					</td>
					<td style="padding:10px 14px;vertical-align:middle;">${pathwayHtml}</td>
					<td style="padding:10px 14px;vertical-align:middle;text-align:center;">${cred}</td>
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
		if (status.toLowerCase() === "generated") {
			return `<span class="tm-transcript-badge generated">${__("Generated")}</span>`;
		}
		return `<span class="tm-transcript-badge pending">${frappe.utils.escape_html(status)}</span>`;
	}

	function render_pagination() {
		const total_pages = Math.ceil(state.total / state.page_length);
		const from = Math.min((state.page - 1) * state.page_length + 1, state.total);
		const to   = Math.min(state.page * state.page_length, state.total);

		$(wrapper).find("#tm-page-info").text(
			state.total
				? `${__("Showing")} ${from}–${to} ${__("of")} ${state.total} ${__("students")}`
				: `${__("No students found")}`
		);
		$(wrapper).find("#tm-page-current").text(`${__("Page")} ${state.page} / ${total_pages || 1}`);
		$(wrapper).find("#tm-prev").prop("disabled", state.page <= 1);
		$(wrapper).find("#tm-next").prop("disabled", state.page >= total_pages);
	}

	function render_active_tags() {
		const container = $(wrapper).find("#tm-active-tags");
		container.empty();

		const labels = {
			programme:      state.programme      ? `${__("Programme")}: ${state.programme}` : null,
			department:     state.department     ? `${__("Department")}: ${state.department}` : null,
			course:         state.course         ? `${__("Course")}: ${state.course}` : null,
			academic_year:  state.academic_year  ? `${__("Year")}: ${state.academic_year}` : null,
			batch:          state.batch          ? `${__("Batch")}: ${state.batch}` : null,
			student_status: state.student_status ? `${__("Status")}: ${state.student_status}` : null,
		};

		Object.entries(labels).forEach(([key, label]) => {
			if (!label) return;
			const tag = $(`
				<span class="tm-tag">
					${frappe.utils.escape_html(label)}
					<button data-key="${key}" title="${__('Remove filter')}">✕</button>
				</span>
			`);
			tag.find("button").on("click", function () {
				state[$(this).data("key")] = "";
				$(wrapper).find(`#tm-f-${$(this).data("key").replace("_", "-")}`).val("");
				render_active_tags();
				state.page = 1;
				load_students();
			});
			container.append(tag);
		});
	}

	function get_selected_students() {
		return [...state.selected];
	}

	function handle_generate(type) {
		const students = get_selected_students();
		if (!students.length) {
			frappe.msgprint(__("Please select at least one student to generate a transcript."));
			return;
		}

		frappe.confirm(
			__("Generate {0} Transcript for {1} selected student(s)?", [type, students.length]),
			function () {
				frappe.call({
					method: "slcm.slcm.page.transcript_management_page.transcript_management_page.generate_transcript",
					args: {
						students:        JSON.stringify(students),
						transcript_type: type,
					},
					callback: function (r) {
						if (!r.message) return;
						const ok  = r.message.filter(x => x.success).length;
						const err = r.message.filter(x => !x.success).length;
						frappe.show_alert({
							message: __("{0} transcript(s) generated successfully." + (err ? ` {1} failed.` : ""), [ok, err]),
							indicator: err ? "orange" : "green",
						});
						state.selected.clear();
						load_students();
					}
				});
			}
		);
	}

	function handle_download(type) {
		const students = get_selected_students();
		if (!students.length) {
			frappe.msgprint(__("Please select at least one student to download a transcript."));
			return;
		}
		if (students.length === 1) {
			window.open(
				`/api/method/slcm.slcm.page.transcript_management_page.transcript_management_page.download_transcript?student=${students[0]}&transcript_type=${type}`,
				"_blank"
			);
		} else {
			frappe.msgprint(__("Bulk download is not yet supported. Please select one student at a time."));
		}
	}

	// ── Initial Load ───────────────────────────────────────────────────────────
	load_students();

};
