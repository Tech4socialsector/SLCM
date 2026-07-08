// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

/* ── Shared helper: build a MultiSelectList get_data function ────────────────
   Calls the whitelisted Python API get_filter_options(filter_name, txt)
   and returns a Promise that resolves to [{label, value, description}].
──────────────────────────────────────────────────────────────────────────── */
function rfid_multiselect_get_data(filter_name) {
	return function (txt) {
		return frappe.call({
			method: "slcm.slcm.report.rfid_attendance_report.rfid_attendance_report.get_filter_options",
			args: { filter_name: filter_name, txt: txt || "" }
		}).then(function (r) {
			return r && r.message ? r.message : [];
		});
	};
}

/* ── Inject NLSIU selection highlight styles once ────────────────────────── */
(function inject_rfid_styles() {
	if (document.getElementById("rfid-report-styles")) return;
	const style = document.createElement("style");
	style.id = "rfid-report-styles";
	style.textContent = `
		/* Summary rows (bold=1) — light navy background, stronger bottom border */
		.dt-row.dt-row--bold .dt-cell {
			background: #eef0f8 !important;
			border-bottom: 2px solid #b8bcd8 !important;
		}
		/* Indent detail rows visually */
		.dt-row:not(.dt-row--bold) .dt-cell--col-0 {
			padding-left: 28px !important;
		}
		/* Horizontal scroll — force the datatable wrapper to scroll */
		.report-wrapper .dt-scrollable {
			overflow-x: auto !important;
		}
		/* Selected item in MultiSelectList dropdown — navy highlight */
		.rfid-filter .selectable-item.selected,
		.rfid-filter .selectable-item.selected:hover {
			background: #2b2e4a !important;
			color: #fff !important;
		}
		/* Tick icon inside selected item */
		.rfid-filter .selectable-item.selected .multiselect-check {
			color: #fff !important;
		}
		/* Hover on unselected items — light navy tint */
		.rfid-filter .selectable-item:hover {
			background: #e8e9f0 !important;
			color: #2b2e4a !important;
		}
		/* Clear All button — maroon */
		.rfid-filter .clear-selections {
			background: #8b1a1a !important;
			border-color: #8b1a1a !important;
			color: #fff !important;
		}
		/* Select All button — navy */
		.rfid-filter .select-all-options {
			background: #2b2e4a !important;
			border-color: #2b2e4a !important;
			color: #fff !important;
		}
		/* Status text when values selected — navy bold */
		.rfid-filter .multiselect-list .status-text {
			color: #2b2e4a;
			font-weight: 600;
		}
	`;
	document.head.appendChild(style);
})();

frappe.query_reports["RFID Attendance Report"] = {

	onload: function (report) {
		// ── Reset Filters button ─────────────────────────────────────────────
		report.page.add_inner_button(__("Reset Filters"), function () {
			const today   = frappe.datetime.get_today();
			const week_ago = frappe.datetime.add_days(today, -6);

			// Clear every MultiSelectList to an empty array
			["academic_year", "programme", "terminal_alias", "area_alias", "student"].forEach(function (fn) {
				const f = report.get_filter(fn);
				if (f && f.set_value) f.set_value([]);
			});

			// Reset scalar filters to defaults
			report.get_filter("view_by").set_input("Daily");
			report.get_filter("from_date").set_input(week_ago);
			report.get_filter("to_date").set_input(today);
			report.get_filter("known_only").set_input(0);

			// Clear the URL params so stale values don't re-apply on refresh
			frappe.route_options = {};

			report.refresh();
		}).css({
			"color":        "#8b1a1a",
			"font-weight":  "600",
			"border-color": "#8b1a1a"
		});

		// ── Apply .rfid-filter CSS class to MultiSelectList controls ─────────
		setTimeout(function () {
			report.page.page_form.find(".frappe-control").each(function () {
				const fn = $(this).attr("data-fieldname");
				if (["academic_year", "programme", "terminal_alias", "area_alias", "student"].includes(fn)) {
					$(this).addClass("rfid-filter");
				}
			});
		}, 600);
	},

	filters: [
		{
			fieldname: "view_by",
			label: __("View By"),
			fieldtype: "Select",
			options: "Daily\nWeekly\nMonthly",
			default: "Daily",
			reqd: 1,
			on_change: function () { frappe.query_report.refresh(); }
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -6),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "academic_year",
			label: __("Academic Year"),
			fieldtype: "MultiSelectList",
			get_data: rfid_multiselect_get_data("academic_year")
		},
		{
			fieldname: "programme",
			label: __("Programme(s)"),
			fieldtype: "MultiSelectList",
			get_data: rfid_multiselect_get_data("programme")
		},
		{
			fieldname: "terminal_alias",
			label: __("Terminal / Room"),
			fieldtype: "MultiSelectList",
			get_data: rfid_multiselect_get_data("terminal_alias")
		},
		{
			fieldname: "area_alias",
			label: __("Area"),
			fieldtype: "MultiSelectList",
			get_data: rfid_multiselect_get_data("area_alias")
		},
		{
			fieldname: "student",
			label: __("Student"),
			fieldtype: "MultiSelectList",
			get_data: rfid_multiselect_get_data("student")
		},
		{
			fieldname: "known_only",
			label: __("Known Students Only"),
			fieldtype: "Check",
			default: 0
		}
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		const is_summary = data && data.bold == 1;

		// ── Summary row styling ────────────────────────────────────────────
		if (is_summary) {
			if (column.fieldname === "period_label") {
				// Date (Tuesday) — style date part bold navy, weekday part lighter
				const raw = data.period_label || "";
				const m = raw.match(/^(.+?)\s+\((.+?)\)$/);
				const formatted = m
					? `<span style="color:#2b2e4a;font-weight:700">${m[1]}</span><span style="color:#6b7280;font-weight:400;font-size:.85em;margin-left:6px">(${m[2]})</span>`
					: `<span style="color:#2b2e4a;font-weight:700;font-size:.95em">${raw}</span>`;
				value = formatted;
			}
			if (column.fieldname === "terminal_alias") {
				value = `<span style="color:#2b2e4a;font-style:italic;font-size:.82em">${data.terminal_alias || ""}</span>`;
			}
			if (column.fieldname === "total_swipes") {
				value = `<b style="color:#2b2e4a">${data.total_swipes || 0}</b>`;
			}
			if (column.fieldname === "unique_students") {
				value = `<b style="color:#2b2e4a">${data.unique_students || 0}</b>`;
			}
			if (column.fieldname === "known_students") {
				value = `<b style="color:#2b2e4a">${data.known_students || 0}</b>`;
			}
			if (column.fieldname === "unknown_swipes" && data.unknown_swipes > 0) {
				value = `<b style="color:#8b1a1a">${data.unknown_swipes}</b>`;
			}
			return value;
		}

		// ── Detail row styling ─────────────────────────────────────────────
		if (column.fieldname === "terminal_alias" && data && data.terminal_alias) {
			value = `<code style="background:#dde0f0;color:#2b2e4a;padding:2px 8px;border-radius:4px;font-size:.82em;font-weight:600">${data.terminal_alias}</code>`;
		}
		if (column.fieldname === "area_alias" && data && data.area_alias) {
			value = `<span style="color:#555;font-style:italic">${data.area_alias}</span>`;
		}
		if (column.fieldname === "unique_students" && data && data.unique_students > 0) {
			value = `<span style="color:#2b2e4a">${data.unique_students}</span>`;
		}
		if (column.fieldname === "known_students" && data && data.known_students > 0) {
			value = `<span style="color:#2b2e4a">${data.known_students}</span>`;
		}
		if (column.fieldname === "unknown_swipes" && data && data.unknown_swipes > 0) {
			value = `<span style="color:#8b1a1a;font-weight:600">${data.unknown_swipes}</span>`;
		}
		if (column.fieldname === "student_name" && data && data.student) {
			value = `<a href="/app/student-master/${data.student}" style="color:#2b2e4a;font-weight:600">${data.student_name || ""}</a>`;
		}

		return value;
	},

	get_datatable_options: function (options) {
		return Object.assign(options, {
			checkboxColumn:    false,
			cellHeight:        40,
			/* treeView adds "Set Level / Collapse All" controls — keep off.
			   We use indent purely for visual indentation via the formatter. */
			treeView:          false,
			/* "fixed" keeps column widths as defined and enables the
			   horizontal scrollbar properly. "fluid" stretches columns
			   and breaks overflow scroll. */
			layout:            "fixed",
			/* Freeze the first column (Date) so it stays visible while
			   scrolling horizontally across the wide table. */
			freezeColumns:     1,
		});
	}
};
