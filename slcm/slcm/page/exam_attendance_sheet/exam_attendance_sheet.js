frappe.pages['exam-attendance-sheet'].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Exam Attendance Sheet',
		single_column: true
	});
	new ExamAttendanceSheet(wrapper);
};

class ExamAttendanceSheet {
	constructor(wrapper) {
		this.$body = $(wrapper).find('.page-content').css({ padding: '16px 20px' });
		this.exam_plan = null;
		this.courses = [];
		this.$toolbar = null;
		this._build_ui();
	}

	// ── UI skeleton ───────────────────────────────────────────────────────────
	_build_ui() {
		/* Filter card */
		this.$filter = $(`
			<div style="background:#fff;border:1px solid #e2e6ea;border-radius:8px;
				padding:20px 24px;margin-bottom:18px;display:flex;
				align-items:flex-end;gap:16px;flex-wrap:wrap;">
				<div style="display:flex;flex-direction:column;gap:4px;min-width:320px;">
					<label style="font-size:12px;font-weight:600;color:#495057;margin:0;">
						Exam Plan <span style="color:#e03e3e">*</span>
					</label>
					<div class="eas-plan-wrap"></div>
				</div>
				<button class="btn btn-primary btn-sm eas-load-btn"
					style="height:32px;min-width:130px;" disabled>
					<i class="fa fa-search"></i>&nbsp; Load Courses
				</button>
			</div>
		`).appendTo(this.$body);

		/* Results container — never destroyed, only emptied */
		this.$results = $('<div class="eas-results"></div>').appendTo(this.$body);

		this._build_plan_field();
	}

	// ── Exam Plan link field ──────────────────────────────────────────────────
	_build_plan_field() {
		this._plan_ctrl = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Link',
				fieldname: 'exam_plan',
				options: 'Exam Plan',
				placeholder: 'Select Exam Plan…',
			},
			parent: this.$filter.find('.eas-plan-wrap')[0],
			render_input: true,
		});
		this._plan_ctrl.refresh();

		const $btn = this.$filter.find('.eas-load-btn');

		/* Enable/disable button whenever the field value changes.
		   Use both native input events AND set_value override so we catch
		   keyboard entry, mouse-select from dropdown, and programmatic sets. */
		const _sync_btn = () => {
			const v = this._plan_value();
			$btn.prop('disabled', !v);
			if (!v) {
				this.exam_plan = null;
				this._clear();
			}
		};

		this._plan_ctrl.$input.on('input change awesomplete-selectcomplete', _sync_btn);

		const _orig_set = this._plan_ctrl.set_value.bind(this._plan_ctrl);
		this._plan_ctrl.set_value = (v) => { _orig_set(v); _sync_btn(); };

		$btn.on('click', () => {
			const v = this._plan_value();
			if (!v) {
				frappe.show_alert({ message: 'Please select an Exam Plan.', indicator: 'orange' });
				return;
			}
			this.exam_plan = v;
			this._load_courses();
		});
	}

	_plan_value() {
		return (this._plan_ctrl.get_value() || this._plan_ctrl.$input.val() || '').trim();
	}

	// ── Helpers ───────────────────────────────────────────────────────────────
	_clear() {
		/* Only empties the DOM results area; does NOT touch this.courses
		   (callers that need to reset courses do so explicitly). */
		this.$results.empty();
		this.$toolbar = null;
	}

	_fmt_time(t) {
		if (!t) return '<span class="text-muted">—</span>';
		try { return moment(t, 'HH:mm:ss').format('hh:mm A'); }
		catch (e) { return t; }
	}

	// ── Load courses ──────────────────────────────────────────────────────────
	_load_courses() {
		this.courses = [];          // reset data
		this._clear();              // reset DOM

		this.$results.html(`
			<div class="text-center text-muted" style="padding:40px;">
				<i class="fa fa-spinner fa-spin fa-2x"></i>
				<p style="margin-top:12px;">Loading courses…</p>
			</div>`);

		frappe.call({
			method: 'slcm.slcm.page.exam_attendance_sheet.exam_attendance_sheet.get_exam_courses',
			args: { exam_plan: this.exam_plan },
			callback: (r) => {
				if (r.exc) { this._clear(); return; }

				const data = r.message || [];
				this._clear();   // remove spinner before rendering

				if (!data.length) {
					this.$results.html(`
						<div class="alert alert-warning" style="margin:0;">
							<b>No courses scheduled</b> in <i>"${this.exam_plan}"</i>.
							Open the Exam Plan and add course schedules first.
						</div>`);
					return;
				}

				/* Store THEN render — order matters */
				this.courses = data;
				this._render_courses();
			}
		});
	}

	// ── Render course table ───────────────────────────────────────────────────
	_render_courses() {
		/* NOTE: do NOT call _clear() here — this.courses must remain intact */

		/* Toolbar */
		this.$toolbar = $(`
			<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;
				margin-bottom:14px;background:#fff;border:1px solid #e2e6ea;
				border-radius:8px;padding:14px 18px;">
				<button class="btn btn-success btn-sm eas-gen-all">
					<i class="fa fa-qrcode"></i>&nbsp; Generate All Barcodes
				</button>
				<button class="btn btn-primary btn-sm eas-export" disabled>
					<i class="fa fa-download"></i>&nbsp; Download Attendance Excel
				</button>
				<span class="eas-msg text-muted" style="font-size:12px;margin-left:4px;"></span>
			</div>
		`).appendTo(this.$results);

		this.$toolbar.find('.eas-gen-all').on('click', () =>
			this._generate_barcodes(this.courses.map(c => c.course)));

		this.$toolbar.find('.eas-export').on('click', () => this._export_excel());

		/* Group by date */
		const date_groups = {};
		this.courses.forEach(c => {
			const key = c.exam_date || '__nodate__';
			if (!date_groups[key]) date_groups[key] = [];
			date_groups[key].push(c);
		});

		const sorted_dates = Object.keys(date_groups).sort((a, b) => {
			if (a === '__nodate__') return 1;
			if (b === '__nodate__') return -1;
			return a < b ? -1 : 1;
		});

		sorted_dates.forEach(date => {
			const label = (date === '__nodate__')
				? '(No Date Scheduled)'
				: frappe.datetime.str_to_user(date);

			/* Date header */
			$(`<div style="background:#f0f4ff;border-left:4px solid #2490ef;
					padding:9px 16px;margin-bottom:6px;border-radius:4px;
					font-weight:600;font-size:13px;color:#1a5276;
					display:flex;align-items:center;gap:8px;">
				<i class="fa fa-calendar-o"></i> Exam Date: ${label}
			</div>`).appendTo(this.$results);

			/* Course table */
			const $card = $(`
				<div style="background:#fff;border:1px solid #e2e6ea;
					border-radius:8px;margin-bottom:16px;overflow:hidden;">
					<table class="table table-bordered" style="margin:0;font-size:13px;">
						<thead style="background:#f8f9fa;">
							<tr>
								<th style="width:36px;text-align:center;">#</th>
								<th>Course</th>
								<th style="width:100px;">Code</th>
								<th style="width:105px;">Start</th>
								<th style="width:105px;">End</th>
								<th style="width:150px;">Venue / Block</th>
								<th style="width:120px;">Hall / Room</th>
								<th style="width:110px;text-align:center;">Barcodes</th>
								<th style="width:110px;text-align:center;">Action</th>
							</tr>
						</thead>
						<tbody></tbody>
					</table>
				</div>
			`).appendTo(this.$results);

			date_groups[date].forEach((c, i) =>
				this._append_course_row(c, i + 1, $card.find('tbody')));
		});

		this._sync_export_btn();
	}

	// ── Single course row + detail row ────────────────────────────────────────
	_append_course_row(c, idx, $tbody) {
		const has = c.barcode_count > 0;

		const $tr = $(`
			<tr data-course="${c.course}">
				<td style="text-align:center;color:#6c757d;">${idx}</td>
				<td>
					<a class="eas-course-link" href="#"
						style="font-weight:600;color:#2490ef;text-decoration:none;"
						title="Click to view enrolled students">
						${c.course_name || c.course}
					</a>
					<i class="fa fa-chevron-right eas-chevron"
						style="font-size:10px;color:#adb5bd;margin-left:6px;
						transition:transform .2s;"></i>
				</td>
				<td><span class="text-muted" style="font-size:12px;">${c.course_code || c.course}</span></td>
				<td>${this._fmt_time(c.start_time)}</td>
				<td>${this._fmt_time(c.end_time)}</td>
				<td>${c.venue || '<span class="text-muted">—</span>'}</td>
				<td>${c.hall  || '<span class="text-muted">—</span>'}</td>
				<td style="text-align:center;">
					<span class="badge eas-bc-badge badge-${has ? 'success' : 'secondary'}"
						style="font-size:12px;padding:4px 8px;">
						${c.barcode_count}
					</span>
				</td>
				<td style="text-align:center;">
					<button class="btn btn-xs btn-default eas-gen-one"
						style="font-size:11px;">
						<i class="fa fa-refresh"></i> Generate
					</button>
				</td>
			</tr>
		`).appendTo($tbody);

		/* Detail/student row (hidden) */
		const $detail = $(`
			<tr class="eas-detail" data-course="${c.course}"
				style="display:none;background:#f9fbff;">
				<td colspan="9" style="padding:0;">
					<div class="eas-student-panel" style="padding:12px 20px;"></div>
				</td>
			</tr>
		`).appendTo($tbody);

		/* Toggle student list on course-name click */
		$tr.find('.eas-course-link').on('click', (e) => {
			e.preventDefault();
			const open = $detail.is(':visible');
			$detail.toggle(!open);
			$tr.find('.eas-chevron').css('transform', open ? '' : 'rotate(90deg)');
			if (!open) this._load_students(c, $detail.find('.eas-student-panel'));
		});

		/* Per-course generate */
		$tr.find('.eas-gen-one').on('click', () => this._generate_barcodes([c.course]));
	}

	// ── Student list panel ────────────────────────────────────────────────────
	_load_students(c, $panel) {
		/* If already loaded, keep existing content */
		if ($panel.children().length) return;

		$panel.html('<i class="fa fa-spinner fa-spin"></i> Loading students…');

		frappe.call({
			method: 'slcm.slcm.page.exam_attendance_sheet.exam_attendance_sheet.get_course_students',
			args: { exam_plan: this.exam_plan, course: c.course },
			callback: (r) => {
				if (r.exc) {
					$panel.html('<span class="text-danger">Failed to load students.</span>');
					return;
				}
				this._render_student_panel($panel, r.message || [], c);
			}
		});
	}

	_render_student_panel($panel, students, c) {
		if (!students.length) {
			$panel.html(`
				<div class="text-muted" style="padding:10px 0;font-size:13px;">
					<i class="fa fa-info-circle"></i>
					No students found in Student Groups for <b>${c.course_name || c.course}</b>.
					Check that students are added to a Student Group with this course.
				</div>`);
			return;
		}

		const total = students.length;
		const done  = students.filter(s => s.has_barcode).length;

		const rows = students.map((s, i) => `
			<tr>
				<td style="text-align:center;color:#6c757d;width:40px;">${i + 1}</td>
				<td style="font-weight:500;">${s.student_name}</td>
				<td style="width:130px;">${s.registration_id || '<span class="text-muted">—</span>'}</td>
				<td style="width:80px;text-align:center;">${s.section || '<span class="text-muted">—</span>'}</td>
				<td style="width:130px;text-align:center;">
					${s.barcode
						? `<span class="badge badge-success"
								style="font-size:12px;letter-spacing:1px;">${s.barcode}</span>`
						: `<span class="badge badge-secondary"
								style="font-size:11px;">Not generated</span>`}
				</td>
			</tr>`).join('');

		$panel.html(`
			<div style="display:flex;align-items:center;justify-content:space-between;
				margin-bottom:10px;flex-wrap:wrap;gap:8px;">
				<span style="font-weight:600;font-size:13px;color:#333;">
					<i class="fa fa-users"></i>&nbsp;
					${c.course_name || c.course} —
					<span class="text-muted" style="font-weight:400;">
						${total} student(s) &nbsp;|&nbsp;
						${done} barcoded &nbsp;|&nbsp;
						${total - done} pending
					</span>
				</span>
				<button class="btn btn-xs btn-success eas-gen-panel">
					<i class="fa fa-qrcode"></i> Generate Barcodes
				</button>
			</div>
			<div style="max-height:340px;overflow-y:auto;border:1px solid #e2e6ea;border-radius:6px;">
				<table class="table table-bordered table-hover"
					style="margin:0;font-size:12px;">
					<thead style="background:#f0f4ff;position:sticky;top:0;">
						<tr>
							<th style="text-align:center;">#</th>
							<th>Name</th>
							<th>ID No.</th>
							<th style="text-align:center;">Sec</th>
							<th style="text-align:center;">Barcode</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`);

		$panel.find('.eas-gen-panel').on('click', () =>
			this._generate_barcodes([c.course]));
	}

	// ── Generate barcodes ─────────────────────────────────────────────────────
	_generate_barcodes(courses) {
		frappe.call({
			method: 'slcm.slcm.page.exam_attendance_sheet.exam_attendance_sheet.generate_barcodes',
			args: {
				exam_plan: this.exam_plan,
				courses: JSON.stringify(courses),
			},
			freeze: true,
			freeze_message: 'Generating barcodes…',
			callback: (r) => {
				if (r.exc) {
					frappe.show_alert({ message: 'Error generating barcodes.', indicator: 'red' });
					return;
				}
				const res = r.message || {};
				frappe.show_alert({ message: res.message || 'Done.', indicator: 'green' });
				/* Reload to refresh badge counts and clear cached student panels */
				this._load_courses();
			}
		});
	}

	// ── Export Excel ──────────────────────────────────────────────────────────
	_export_excel() {
		frappe.show_alert({ message: 'Preparing Excel…', indicator: 'blue' });
		frappe.call({
			method: 'slcm.slcm.page.exam_attendance_sheet.exam_attendance_sheet.export_attendance_excel',
			args: { exam_plan: this.exam_plan },
			freeze: true,
			freeze_message: 'Building Excel file…',
			callback: (r) => {
				if (r.exc) {
					frappe.show_alert({ message: 'Error generating Excel.', indicator: 'red' });
					return;
				}
				const { file_content, filename } = r.message;
				const bytes = Uint8Array.from(atob(file_content), c => c.charCodeAt(0));
				const blob  = new Blob([bytes], {
					type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
				});
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url; a.download = filename;
				document.body.appendChild(a); a.click();
				setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
				frappe.show_alert({ message: 'Excel downloaded!', indicator: 'green' });
			}
		});
	}

	// ── Sync export button state ──────────────────────────────────────────────
	_sync_export_btn() {
		if (!this.$toolbar) return;
		const total = this.courses.reduce((s, c) => s + (c.barcode_count || 0), 0);
		this.$toolbar.find('.eas-export').prop('disabled', total === 0);
	}
}
