/*****************************************************
 * LIST VIEW CONFIGURATION
 *****************************************************/
frappe.listview_settings["Student Enrollment"] = {
	onload(listview) {
		$("span.sidebar-toggle-btn").hide();
		$(".col-lg-2.layout-side-section").hide();
		inject_enrollment_status_css();
		add_listview_status_actions(listview);
		add_promotion_buttons(listview);
	},

	get_indicator(doc) {
		if (doc.status === "Enrolled") {
			return [__("Enrolled"), "green", "status,=,Enrolled"];
		}

		if (doc.status === "Dropped") {
			return [__("Dropped"), "red", "status,=,Dropped"];
		}

		if (doc.status === "Completed") {
			return [__("Completed"), "blue", "status,=,Completed"];
		}

		if (doc.status === "Pending") {
			return [__("Pending"), "yellow", "status,=,Pending"];
		}

		return [__(doc.status), "gray"];
	},
};

/* --------------------------------------------------
   List View → Actions → Status (Bulk Update)
-------------------------------------------------- */
function add_listview_status_actions(listview) {
	const statuses = [
		{ label: __("Enrolled"), value: "Enrolled" },
		{ label: __("Dropped"), value: "Dropped" },
		{ label: __("Completed"), value: "Completed" },
		{ label: __("Pending"), value: "Pending" },
	];

	statuses.forEach((status) => {
		listview.page.add_action_item(status.label, () => {
			update_listview_status(listview, status.value);
		});
	});
}

/* --------------------------------------------------
   Bulk status update logic
-------------------------------------------------- */
function update_listview_status(listview, status) {
	const selected = listview.get_checked_items();

	if (!selected.length) {
		frappe.msgprint({
			title: __("No Records Selected"),
			message: __("Please select at least one Student Enrollment."),
			indicator: "orange",
		});
		return;
	}

	frappe.confirm(
		__("Are you sure you want to change status to <b>{0}</b> for {1} record(s)?", [
			status,
			selected.length,
		]),
		() => {
			frappe.call({
				method: "slcm.slcm.doctype.student_enrollment.student_enrollment.bulk_update_enrollment_status",
				args: {
					names: selected.map((doc) => doc.name),
					status: status,
				},
				freeze: true,
				callback: (r) => {
					const { updated = [], failed = [] } = r.message || {};

					if (updated.length) {
						frappe.show_alert(
							{
								message: __("Status updated to {0} for {1} record(s)", [status, updated.length]),
								indicator: "green",
							},
							5
						);
					}

					if (failed.length) {
						frappe.msgprint({
							title: __("Some records could not be updated"),
							indicator: "red",
							message: failed
								.map((f) => `${f.name}: ${f.error}`)
								.join("<br>"),
						});
					}

					listview.refresh();
				},
			});
		}
	);
}

/*****************************************************
 * BULK PROMOTION
 *****************************************************/
function add_promotion_buttons(listview) {
	const allowed_roles = ["System Manager", "slcm_Academic Incharge"];
	if (!frappe.user_roles.some((r) => allowed_roles.includes(r))) return;

	inject_promotion_button_css();

	const $promote_btn = listview.page.add_inner_button(__("Promote Students"), () =>
		open_promote_students_dialog(listview)
	);
	const $log_btn = listview.page.add_inner_button(__("View Promotion Log"), () => {
		frappe.set_route("List", "Promotion Run");
	});

	$promote_btn.addClass("promotion-btn promotion-btn-primary").prepend('<span class="promotion-btn-icon">&#8613;</span> ');
	$log_btn.addClass("promotion-btn promotion-btn-secondary").prepend('<span class="promotion-btn-icon">&#128203;</span> ');
}

function inject_promotion_button_css() {
	if (document.getElementById("promotion-btn-css")) return;

	const style = document.createElement("style");
	style.id = "promotion-btn-css";
	style.innerHTML = `
		.promotion-btn {
			font-weight: 600;
			border: none !important;
			box-shadow: none !important;
			transition: filter 0.15s ease, transform 0.05s ease;
		}
		.promotion-btn:active {
			transform: translateY(1px);
		}
		.promotion-btn-icon {
			display: inline-block;
			transform: translateY(-1px);
		}
		.promotion-btn-primary {
			background-color: #1e293b !important;
			color: #ffffff !important;
		}
		.promotion-btn-primary:hover {
			background-color: #0f172a !important;
			color: #ffffff !important;
		}
		.promotion-btn-secondary {
			background-color: #334155 !important;
			color: #e2e8f0 !important;
		}
		.promotion-btn-secondary:hover {
			background-color: #1e293b !important;
			color: #ffffff !important;
		}

		.promote-dialog .modal-dialog {
			max-width: 1100px !important;
			width: 92vw !important;
		}
		.promote-dialog .modal-header {
			background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
			border-radius: 6px 6px 0 0;
			padding: 18px 28px;
		}
		.promote-dialog .modal-header .modal-title {
			color: #ffffff;
			font-size: 17px;
			font-weight: 700;
			display: flex;
			align-items: center;
			gap: 10px;
		}
		.promote-dialog .modal-header .btn-modal-close svg {
			stroke: #ffffff;
		}
		.promote-dialog .modal-body {
			padding: 0;
			max-height: 72vh;
			overflow-y: auto;
		}
		.promote-dialog-intro {
			padding: 14px 28px;
			background: #f1f5f9;
			border-bottom: 1px solid #e2e8f0;
			font-size: 13px;
			line-height: 1.5;
			color: #475569;
			display: flex;
			align-items: flex-start;
			gap: 10px;
		}
		.promote-dialog-intro .info-icon {
			flex-shrink: 0;
			width: 20px;
			height: 20px;
			border-radius: 50%;
			background: #cbd5e1;
			color: #1e293b;
			font-weight: 700;
			font-size: 12px;
			display: flex;
			align-items: center;
			justify-content: center;
			margin-top: 1px;
		}
		.promote-dialog .modal-body form {
			padding: 20px 28px 6px 28px;
		}
		.promote-dialog .frappe-control {
			margin-bottom: 16px;
		}
		.promote-dialog .form-column {
			padding-left: 12px;
			padding-right: 12px;
		}
		.promote-dialog .form-section.promote-section-card {
			background: #f8fafc;
			border: 1px solid #e2e8f0;
			border-radius: 8px;
			padding: 16px 16px 4px 16px;
			margin-bottom: 20px;
		}
		.promote-dialog .form-section.promote-section-card.target {
			background: #f0fdf4;
			border-color: #bbf7d0;
		}
		.promote-dialog .form-section.promote-section-card .section-head {
			font-size: 11.5px;
			font-weight: 700;
			letter-spacing: 0.06em;
			text-transform: uppercase;
			color: #475569;
			border: none;
			padding: 0 0 14px 0;
			margin: 0;
		}
		.promote-dialog .form-section.promote-section-card.target .section-head {
			color: #166534;
		}
		.promote-dialog .form-section:not(.promote-section-card) .section-head {
			display: none;
		}
		.promote-dialog .modal-footer {
			background: #f8fafc;
			border-top: 1px solid #e2e8f0;
			padding: 14px 28px;
		}
		.promote-dialog .modal-footer .btn-primary {
			background-color: #1e293b;
			border: none;
			font-weight: 600;
			padding: 8px 22px;
		}
		.promote-dialog .modal-footer .btn-primary:hover {
			background-color: #0f172a;
		}

		.promote-review-dialog .modal-dialog {
			max-width: 1240px !important;
			width: 92vw !important;
		}
		.promote-review-count {
			font-weight: 400;
			opacity: 0.8;
			font-size: 14px;
		}
		.promote-review-toolbar {
			padding: 14px 32px;
			background: #f8fafc;
			border-bottom: 1px solid #e2e8f0;
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 16px;
			flex-wrap: wrap;
		}
		.promote-review-summary {
			font-size: 12.5px;
			color: #64748b;
			flex: 1;
		}
		.promote-review-summary b {
			color: #1e293b;
		}
		.promote-review-selected-count {
			font-size: 12.5px;
			font-weight: 700;
			color: #1e293b;
			background: #e2e8f0;
			padding: 4px 12px;
			border-radius: 20px;
			white-space: nowrap;
		}
		.promote-review-datatable {
			padding: 16px 32px 8px 32px;
		}
		.promote-review-datatable .dt-scrollable {
			max-height: 55vh;
		}
		.promote-review-datatable .dt-row-highlight,
		.promote-review-datatable .dt-cell:hover {
			background-color: #f8fafc;
		}
		.promote-review-datatable .dt-cell__content {
			padding: 6px 12px;
			display: flex;
			flex-direction: column;
			justify-content: center;
		}
		.promote-row-name {
			font-weight: 600;
			color: #1e293b;
			font-size: 13.5px;
			line-height: 1.3;
			white-space: normal;
		}
		.promote-row-id {
			font-size: 11px;
			line-height: 1.3;
			color: #94a3b8;
			margin-top: 2px;
		}
		.promote-row-tag {
			display: inline-flex;
			align-items: center;
			gap: 5px;
			font-size: 11.5px;
			font-weight: 600;
			padding: 4px 11px;
			border-radius: 20px;
			white-space: nowrap;
			max-width: 280px;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.promote-row-tag.ok {
			background: #dcfce7;
			color: #166534;
		}
		.promote-row-tag.warn {
			background: #fef3c7;
			color: #92400e;
		}
		.promote-review-dialog .modal-body {
			padding-top: 0;
			padding-bottom: 4px;
		}
		.promote-review-dialog .modal-footer .btn-secondary {
			font-weight: 600;
		}
		.promote-review-dialog .modal-footer {
			background: #f8fafc;
			border-top: 1px solid #e2e8f0;
			padding: 14px 32px;
		}
	`;
	document.head.appendChild(style);
}

function open_promote_students_dialog(listview, defaults) {
	const dialog = new frappe.ui.Dialog({
		title: `<span>&#8613;</span> ${__("Promote Students")}`,
		fields: [
			{
				fieldname: "intro_html",
				fieldtype: "HTML",
				options: `<div class="promote-dialog-intro">
					<span class="info-icon">i</span>
					<span>${__(
						"Set the criteria below, then review and pick exactly which students to promote on the next screen."
					)}</span>
				</div>`,
			},

			{ fieldname: "sb_source", fieldtype: "Section Break",
				label: `&#128269; ${__("Who to promote")}`, css_class: "promote-section-card" },
			{ fieldname: "program", label: __("Programme"), fieldtype: "Link", options: "Programme", reqd: 1 },
			{ fieldname: "source_academic_year", label: __("Source Academic Year"), fieldtype: "Link", options: "Academic Year", reqd: 1 },
			{ fieldname: "col_break_1", fieldtype: "Column Break" },
			{ fieldname: "source_term", label: __("Source Term"), fieldtype: "Link", options: "Academic Term" },
			{ fieldname: "batch", label: __("Batch"), fieldtype: "Link", options: "Batch" },
			{ fieldname: "section", label: __("Section"), fieldtype: "Link", options: "Section" },

			{ fieldname: "sb_target", fieldtype: "Section Break",
				label: `&#127919; ${__("Promote to")}`, css_class: "promote-section-card target" },
			{ fieldname: "target_academic_year", label: __("Target Academic Year"), fieldtype: "Link", options: "Academic Year", reqd: 1 },
			{ fieldname: "target_term", label: __("Target Term"), fieldtype: "Link", options: "Academic Term" },
			{ fieldname: "col_break_2", fieldtype: "Column Break" },
			{ fieldname: "promotion_policy", label: __("Promotion Policy"), fieldtype: "Link", options: "Promotion Policy",
				description: __("Optional — evaluates attendance, backlog, CGPA and fee-due rules, shown as a hint per student on the next screen.") },
		],
		size: "extra-large",
		primary_action_label: __("Next: Review Students"),
		primary_action(values) {
			frappe.call({
				method: "slcm.slcm.doctype.promotion_run.promotion_run.preview_students",
				args: {
					program: values.program,
					source_academic_year: values.source_academic_year,
					batch: values.batch,
					section: values.section,
					promotion_policy: values.promotion_policy,
				},
				freeze: true,
				freeze_message: __("Fetching matching students..."),
				callback: (r) => {
					const students = (r.message && r.message.students) || [];
					if (!students.length) {
						const available = (r.message && r.message.available_academic_years) || [];
						let message = __("No Enrolled students match this Programme / Academic Year / Batch / Section combination.");
						if (available.length) {
							const list_html = available
								.map((a) => `<li><b>${frappe.utils.escape_html(a.academic_year)}</b> — ${a.student_count} ${__("student(s)")}</li>`)
								.join("");
							message += `<br><br>${__("This Programme has Enrolled students under these Academic Year(s) instead — check for a near-duplicate name:")}<ul style="margin-top:6px;">${list_html}</ul>`;
						}
						frappe.msgprint({
							title: __("No Students Found"),
							indicator: "orange",
							message,
						});
						return;
					}
					dialog.hide();
					open_student_review_dialog(listview, values, students);
				},
			});
		},
	});

	dialog.$wrapper.find(".modal-dialog").addClass("promote-dialog");
	if (defaults) dialog.set_values(defaults);
	dialog.show();
}

function open_student_review_dialog(listview, criteria, students) {
	const eligible_count = students.filter((s) => s.likely_eligible).length;

	const dialog = new frappe.ui.Dialog({
		title: `<span>&#128203;</span> ${__("Review Students")} <span class="promote-review-count">(${students.length})</span>`,
		fields: [
			{
				fieldname: "review_html",
				fieldtype: "HTML",
				options: `
					<div class="promote-review-toolbar">
						<span class="promote-review-summary">
							${__("{0} of {1} likely eligible (pre-selected)", [`<b>${eligible_count}</b>`, `<b>${students.length}</b>`])}
							— ${__("deselect or select any student before promoting. Click a column header to sort, or type in the filter row to search.")}
						</span>
						<span class="promote-review-selected-count" id="promote-selected-count"></span>
					</div>
					<div class="promote-review-datatable" id="promote-review-datatable"></div>
				`,
			},
		],
		size: "extra-large",
		primary_action_label: __("Promote Selected"),
		primary_action() {
			if (!review_datatable) return;
			const checked_indexes = review_datatable.rowmanager.getCheckedRows();
			const selected = checked_indexes
				.map((idx) => students[idx])
				.filter(Boolean)
				.map((s) => s.enrollment);

			if (!selected.length) {
				frappe.msgprint(__("Select at least one student to promote."));
				return;
			}

			frappe.confirm(
				__("Start a promotion run for {0} selected student(s)?", [selected.length]),
				() => {
					dialog.hide();
					frappe.call({
						method: "slcm.slcm.doctype.promotion_run.promotion_run.create_and_queue",
						args: { ...criteria, student_list: selected },
						freeze: true,
						freeze_message: __("Queuing promotion run..."),
						callback: (r) => {
							if (!r.message) return;
							const run_name = r.message;
							frappe.show_alert({ message: __("Promotion Run {0} started", [run_name]), indicator: "blue" }, 6);
							watch_promotion_run(run_name, listview);
						},
					});
				}
			);
		},
		secondary_action_label: __("Back"),
		secondary_action() {
			dialog.hide();
			open_promote_students_dialog(listview, criteria);
		},
	});

	dialog.$wrapper.find(".modal-dialog").addClass("promote-dialog promote-review-dialog");
	dialog.show();

	const $wrapper = dialog.$wrapper;
	let review_datatable = null;

	function update_selected_count() {
		if (!review_datatable) return;
		const count = review_datatable.rowmanager.getCheckedRows().length;
		$wrapper.find("#promote-selected-count").text(__("Selected: {0}", [count]));
	}

	const columns = [
		{ name: __("Student"), id: "student_name", width: 240 },
		{ name: __("Batch"), id: "batch", width: 240 },
		{ name: __("Eligibility"), id: "eligibility", width: 300 },
	];

	// Cell content is rendered as raw HTML by frappe.DataTable (no formatter needed),
	// and inline-filter/sort operate on the stripped text of this HTML, so building the
	// markup up front here — rather than via a per-cell `format` callback — sidesteps
	// datatable's lack of a reliable rowIndex in that callback.
	const rows = students.map((s) => {
		const student_cell = `<div class="promote-row-name">${frappe.utils.escape_html(s.student_name || s.student)}</div>
			<div class="promote-row-id">${frappe.utils.escape_html(s.student)}</div>`;
		const eligibility_cell = s.likely_eligible
			? `<span class="promote-row-tag ok">&#10003; ${__("Likely Eligible")}</span>`
			: `<span class="promote-row-tag warn">&#9888; ${frappe.utils.escape_html(s.hint || __("Not Eligible"))}</span>`;
		return [student_cell, frappe.utils.escape_html(s.batch || "—"), eligibility_cell];
	});

	// Build the DataTable after the modal's open animation/layout has settled — constructing
	// it immediately on a still-animating/zero-size container throws inside the library's
	// internal stylesheet setup (insertRule on a null sheet). Same workaround already used
	// for the child DataTable in frappe's own multi_select_dialog.js.
	setTimeout(() => {
		review_datatable = new frappe.DataTable(
			$wrapper.find("#promote-review-datatable").get(0),
			{
				columns,
				data: rows,
				layout: "fluid",
				inlineFilters: true,
				serialNoColumn: false,
				checkboxColumn: true,
				checkedRowStatus: false,
				cellHeight: 54,
				noDataMessage: __("No students to review."),
				disableReorderColumn: true,
				events: {
					onCheckRow: update_selected_count,
				},
			}
		);

		// pre-check likely-eligible rows (row index here matches students[] order — see sort-stability note above)
		students.forEach((s, idx) => {
			if (s.likely_eligible) review_datatable.rowmanager.checkRow(idx, true);
		});

		update_selected_count();
	}, 300);
}

function watch_promotion_run(run_name, listview) {
	frappe.realtime.on("promotion_run_complete", (data) => {
		if (data.promotion_run !== run_name) return;
		const indicator = data.status === "Completed" ? "green" :
			data.status === "Error" ? "red" : "orange";
		frappe.show_alert({
			message: __("Promotion Run {0}: {1} — {2} promoted, {3} skipped", [
				run_name, data.status, data.promoted || 0, data.skipped || 0,
			]),
			indicator,
		}, 8);
		if (listview) listview.refresh();
		frappe.realtime.off("promotion_run_complete");
	});
}

/*****************************************************
 * STATUS INDICATOR STYLING (LIST VIEW ONLY)
 *****************************************************/
function inject_enrollment_status_css() {
	if (document.getElementById("enrollment-status-css")) return;

	const style = document.createElement("style");
	style.id = "enrollment-status-css";
	style.innerHTML = `
		.indicator.green {
			background-color: #e6f4ea !important;
			color: #1e7e34 !important;
			font-weight: 600;
		}
		.indicator.red {
			background-color: #fdecea !important;
			color: #b02a37 !important;
			font-weight: 600;
		}
		.indicator.blue {
			background-color: #e7f1ff !important;
			color: #0d6efd !important;
			font-weight: 600;
		}
	`;
	document.head.appendChild(style);
}

/*****************************************************
 * FORM VIEW CONFIGURATION (SINGLE RECORD)
 *****************************************************/
frappe.ui.form.on("Student Enrollment", {
	refresh(frm) {
		// Do not show action buttons for unsaved records
		if (frm.is_new()) return;

		add_form_status_action_buttons(frm);
	},
});

/* --------------------------------------------------
   Form View → Actions → Status
-------------------------------------------------- */
function add_form_status_action_buttons(frm) {
	// Prevent duplicate buttons
	frm.clear_custom_buttons();

	const statuses = [
		{ label: __("Enrolled"), value: "Enrolled" },
		{ label: __("Dropped"), value: "Dropped" },
		{ label: __("Completed"), value: "Completed" },
		{ label: __("Pending"), value: "Pending" },
	];

	statuses.forEach((status) => {
		frm.add_custom_button(
			status.label,
			() => update_form_status(frm, status.value),
			__("Actions")
		);
	});
}

/* --------------------------------------------------
   Single record status update logic
-------------------------------------------------- */
function update_form_status(frm, status) {
	if (frm.doc.status === status) {
		frappe.msgprint({
			title: __("No Change"),
			message: __("Status is already <b>{0}</b>.", [status]),
			indicator: "blue",
		});
		return;
	}

	frappe.confirm(__("Are you sure you want to change status to <b>{0}</b>?", [status]), () => {
		frm.set_value("status", status);

		frm.save().then(() => {
			frappe.show_alert(
				{
					message: __("Status updated to {0}", [status]),
					indicator: "green",
				},
				5
			);
		});
	});
}
