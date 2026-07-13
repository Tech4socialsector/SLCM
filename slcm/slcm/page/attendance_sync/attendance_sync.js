// Copyright (c) 2026, Nishanth and contributors
// Attendance Sync — reconciliation queue for RFID taps that could not be
// auto-matched to a Student Attendance record (missing device/room mapping,
// faculty never activated RFID, unregistered card, etc.)

const AUTO_REFRESH_MS = 30000;
const AUTO_REFRESH_STORAGE_KEY = "attendance_sync_auto_refresh";

const STATUS_LABELS = {
	"Unmatched - No Session": "No Session Found",
	"Unmatched - No Device Mapping": "Device/Venue Not Mapped",
	"Unmatched - Unknown Card": "Unregistered Card",
	"Pending": "Pending",
	"Matched": "Matched",
	"Manually Synced": "Manually Synced",
};

const STATUS_COLORS = {
	"Unmatched - No Session": "orange",
	"Unmatched - No Device Mapping": "red",
	"Unmatched - Unknown Card": "red",
	"Pending": "grey",
	"Matched": "green",
	"Manually Synced": "blue",
};

frappe.pages["attendance-sync"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Attendance Sync",
		single_column: true,
	});

	page.set_primary_action("Refresh", () => load(wrapper), "fa fa-refresh");

	page.add_field({
		fieldtype: "Select",
		fieldname: "status_filter",
		label: "Reason",
		options: [
			"",
			"Unmatched - No Session",
			"Unmatched - No Device Mapping",
			"Unmatched - Unknown Card",
		].join("\n"),
		change() {
			load(wrapper);
		},
	});

	const stored = localStorage.getItem(AUTO_REFRESH_STORAGE_KEY);
	wrapper._auto_refresh_on = stored === null ? true : stored === "1";

	wrapper._auto_refresh_btn = page.add_inner_button(
		auto_refresh_label(wrapper._auto_refresh_on),
		() => toggle_auto_refresh(wrapper)
	);

	$(build_html()).appendTo($(wrapper).find(".page-content, .layout-main-section").first());
	wrapper._page = page;
	load(wrapper);

	if (wrapper._auto_refresh_on) {
		start_auto_refresh(wrapper);
	}
};

frappe.pages["attendance-sync"].on_page_hide = function (wrapper) {
	stop_auto_refresh(wrapper);
};

function auto_refresh_label(on) {
	return on ? "Auto Refresh: On (30s)" : "Auto Refresh: Off";
}

function start_auto_refresh(wrapper) {
	stop_auto_refresh(wrapper);
	wrapper._sync_interval = setInterval(() => load(wrapper), AUTO_REFRESH_MS);
}

function stop_auto_refresh(wrapper) {
	if (wrapper._sync_interval) {
		clearInterval(wrapper._sync_interval);
		wrapper._sync_interval = null;
	}
}

function toggle_auto_refresh(wrapper) {
	wrapper._auto_refresh_on = !wrapper._auto_refresh_on;
	localStorage.setItem(AUTO_REFRESH_STORAGE_KEY, wrapper._auto_refresh_on ? "1" : "0");

	if (wrapper._auto_refresh_btn) {
		wrapper._auto_refresh_btn.text(auto_refresh_label(wrapper._auto_refresh_on));
	}

	if (wrapper._auto_refresh_on) {
		load(wrapper);
		start_auto_refresh(wrapper);
	} else {
		stop_auto_refresh(wrapper);
	}
}

function build_html() {
	return `
		<div class="attendance-sync-page">
			<div class="row" style="margin: 0 0 20px;">
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="as-total">-</div><div class="stat-label">Needs Review</div></div></div>
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="as-no-session">-</div><div class="stat-label">No Session Found</div></div></div>
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="as-no-device">-</div><div class="stat-label">Device Not Mapped</div></div></div>
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="as-unknown">-</div><div class="stat-label">Unregistered Card</div></div></div>
			</div>
			<div style="margin-bottom: 10px;">
				<span class="text-muted" id="as-shown-count"></span>
			</div>
			<div id="as-table"></div>
		</div>
		<style>
			.stat-card { background: var(--card-bg, #fff); border: 1px solid var(--border-color, #d1d8dd); border-radius: 8px; padding: 16px; text-align: center; }
			.stat-value { font-size: 1.8rem; font-weight: 700; }
			.stat-label { font-size: .8rem; color: var(--text-muted, #8d99a6); text-transform: uppercase; }
			.as-badge { padding: 2px 8px; border-radius: 10px; font-size: .75rem; color: #fff; }
		</style>
	`;
}

function load(wrapper) {
	const status_filter = wrapper._page.fields_dict.status_filter.get_value();
	frappe.call({
		method: "slcm.slcm.doctype.attendance_log.process_attendance_logs.get_unmatched_logs",
		args: { match_status: status_filter || null },
		callback(r) {
			if (!r.message) return;
			render(wrapper, r.message);
		},
	});
}

function render(wrapper, logs) {
	const $w = $(wrapper);

	const counts = { "Unmatched - No Session": 0, "Unmatched - No Device Mapping": 0, "Unmatched - Unknown Card": 0 };
	logs.forEach((l) => {
		if (counts[l.match_status] !== undefined) counts[l.match_status] += 1;
	});

	$w.find("#as-total").text(logs.length);
	$w.find("#as-no-session").text(counts["Unmatched - No Session"]);
	$w.find("#as-no-device").text(counts["Unmatched - No Device Mapping"]);
	$w.find("#as-unknown").text(counts["Unmatched - Unknown Card"]);
	$w.find("#as-shown-count").text(logs.length ? `Showing ${logs.length} unresolved tap(s)` : "");

	wrapper._logs = logs;
	build_table(wrapper, logs);
}

function build_table(wrapper, logs) {
	const $container = $(wrapper).find("#as-table");
	$container.empty();

	if (!logs.length) {
		$container.html(
			'<div class="text-muted text-center" style="padding:40px;">' +
				'<i class="fa fa-check-circle" style="font-size:28px;color:#28a745;"></i>' +
				"<p style='margin-top:10px;'>No unresolved taps. Everything is reconciled.</p></div>"
		);
		return;
	}

	const $table = $(
		'<table class="table table-bordered" style="background:#fff;">' +
			"<thead><tr>" +
			"<th>Student</th><th>Card/RFID UID</th><th>Punch Time</th>" +
			"<th>Device / Reader</th><th>Class / Course</th><th>Lesson Time</th>" +
			"<th>RFID Activated By</th><th>Activation Time</th>" +
			"<th>Reason</th><th>Action</th>" +
			"</tr></thead><tbody></tbody></table>"
	);
	const $tbody = $table.find("tbody");

	logs.forEach((log) => {
		const student_label = log.student ? `${log.student_name || ""} (${log.student})` : "Unknown Card";
		const lesson_candidates = log.candidate_sessions || [];
		const first_session = lesson_candidates[0];

		const class_label = first_session
			? first_session.course_offering || "-"
			: log.resolved_rooms && log.resolved_rooms.length
			? `Room mapped (${log.resolved_rooms.join(", ")}) — no session that day`
			: "-";

		const lesson_time = first_session
			? `${frappe.datetime.str_to_user(first_session.session_start_time) || first_session.session_start_time || ""} - ${first_session.session_end_time || ""}`
			: "-";

		const activated_by = first_session && first_session.rfid_activated_by ? first_session.rfid_activated_by : "-";
		const activation_time = first_session && first_session.rfid_activation_time
			? frappe.datetime.str_to_user(first_session.rfid_activation_time)
			: "-";

		const color = STATUS_COLORS[log.match_status] || "grey";
		const label = STATUS_LABELS[log.match_status] || log.match_status;

		const $row = $('<tr style="cursor:pointer;"></tr>');
		$row.on("click", () => open_log_detail_dialog(log));
		$row.append(`<td>${frappe.utils.escape_html(student_label)}</td>`);
		$row.append(`<td>${frappe.utils.escape_html(log.rfid_uid || "-")}</td>`);
		$row.append(`<td>${frappe.datetime.str_to_user(log.swipe_time) || ""}</td>`);
		$row.append(`<td>${frappe.utils.escape_html(log.device_id || "-")}${log.terminal_alias ? " / " + frappe.utils.escape_html(log.terminal_alias) : ""}</td>`);
		$row.append(`<td>${frappe.utils.escape_html(class_label)}</td>`);
		$row.append(`<td>${lesson_time}</td>`);
		$row.append(`<td>${frappe.utils.escape_html(activated_by)}</td>`);
		$row.append(`<td>${activation_time}</td>`);
		$row.append(`<td><span class="as-badge" style="background:${color};">${label}</span></td>`);

		const $actionTd = $('<td></td>').on("click", (e) => e.stopPropagation());
		const $viewBtn = $('<button class="btn btn-xs btn-default" style="margin-right:4px;">View</button>');
		$viewBtn.on("click", () => open_log_detail_dialog(log));
		const $syncBtn = $('<button class="btn btn-xs btn-primary">Sync</button>');
		$syncBtn.on("click", () => open_sync_dialog(wrapper, log));
		$actionTd.append($viewBtn).append($syncBtn);
		$row.append($actionTd);

		$tbody.append($row);
	});

	$container.append($table);
}

function _kv_row(label, value) {
	return `<div class="row" style="margin:0 0 8px;">` +
		`<div class="col-sm-5 text-muted">${frappe.utils.escape_html(label)}</div>` +
		`<div class="col-sm-7" style="font-weight:500;">${value}</div></div>`;
}

function open_log_detail_dialog(log) {
	const first_session = (log.candidate_sessions || [])[0];
	const color = STATUS_COLORS[log.match_status] || "grey";
	const label = STATUS_LABELS[log.match_status] || log.match_status;
	const student_display = log.student ? `${log.student_name || ""} (${log.student})` : "Unregistered Card";

	const class_name_display = first_session
		? `${frappe.utils.escape_html(first_session.course_offering || "-")}` +
		  (first_session.course_code ? ` [${frappe.utils.escape_html(first_session.course_code)}]` : "")
		: "-";

	let body = "";
	body += `<div style="padding:4px 0 12px;border-bottom:1px solid var(--border-color,#d1d8dd);margin-bottom:14px;">`;
	body += _kv_row("Name", frappe.utils.escape_html(student_display));
	body += _kv_row("Email", frappe.utils.escape_html(log.student_email || "-"));
	body += _kv_row("Punch Id", frappe.utils.escape_html(log.name));
	body += _kv_row("Punch Timestamp", frappe.datetime.str_to_user(log.swipe_time) || "-");
	body += _kv_row("Processing Status", `<span class="as-badge" style="background:${color};">${label}</span>`);
	body += `</div>`;

	body += `<div style="font-weight:600;margin-bottom:8px;">Entity Details</div>`;
	body += _kv_row("Device / Reader", frappe.utils.escape_html(log.device_id || "-") +
		(log.terminal_alias ? " / " + frappe.utils.escape_html(log.terminal_alias) : ""));
	body += _kv_row("Lesson Id", first_session ? frappe.utils.escape_html(first_session.name) : "-");
	body += _kv_row("Lesson Start", first_session
		? (frappe.datetime.str_to_user(first_session.session_start_time) || first_session.session_start_time)
		: "-");
	body += _kv_row("Lesson End", first_session
		? (frappe.datetime.str_to_user(first_session.session_end_time) || first_session.session_end_time)
		: "-");
	body += _kv_row("Lesson Activation Time", first_session && first_session.rfid_activation_time
		? frappe.datetime.str_to_user(first_session.rfid_activation_time)
		: "-");
	body += _kv_row("System Activated", first_session && first_session.rfid_activation_time ? "True" : "False");
	body += _kv_row("RFID Activated By", first_session && first_session.rfid_activated_by
		? frappe.utils.escape_html(first_session.rfid_activated_by)
		: "-");
	body += _kv_row("Class Name [Course Code]", class_name_display);

	if (!first_session && log.resolved_rooms && log.resolved_rooms.length) {
		body += _kv_row("Resolved Room(s)", frappe.utils.escape_html(log.resolved_rooms.join(", ")) +
			" — no Attendance Session found for this date");
	}

	body += `<div style="font-weight:600;margin:16px 0 8px;">Processing History</div>`;
	const history = [];
	history.push({ ts: log.creation, status: "Log received" });
	if (log.synced_on) {
		history.push({ ts: log.synced_on, status: `Manually synced by ${log.synced_by || "-"}` });
	} else if (log.processed) {
		history.push({ ts: log.modified, status: "Matched to Student Attendance" });
	} else {
		history.push({ ts: log.modified, status: label });
	}

	let history_html = '<table class="table table-bordered" style="background:#fff;">' +
		"<thead><tr><th>Timestamp</th><th>Status</th></tr></thead><tbody>";
	history.forEach((h) => {
		history_html += `<tr><td>${frappe.datetime.str_to_user(h.ts) || "-"}</td><td>${frappe.utils.escape_html(h.status)}</td></tr>`;
	});
	history_html += "</tbody></table>";
	body += history_html;

	const d = new frappe.ui.Dialog({
		title: `Log Details — ${log.name}`,
		fields: [{ fieldtype: "HTML", fieldname: "detail_html", options: body }],
	});
	d.show();
}

function open_sync_dialog(wrapper, log) {
	const candidate_sessions = log.candidate_sessions || [];

	const fields = [
		{
			fieldtype: "Data",
			fieldname: "rfid_uid",
			label: "RFID UID",
			default: log.rfid_uid,
			read_only: 1,
		},
	];

	if (!log.student) {
		fields.push({
			fieldtype: "Link",
			fieldname: "student",
			label: "Student (identify the card owner)",
			options: "Student Master",
			reqd: 1,
		});
	}

	fields.push({
		fieldtype: "Link",
		fieldname: "session",
		label: "Attendance Session",
		options: "Attendance Session",
		reqd: 1,
		default: candidate_sessions.length ? candidate_sessions[0].name : "",
		description: candidate_sessions.length
			? `${candidate_sessions.length} candidate session(s) resolved from the device's room mapping for this date. Override if incorrect.`
			: "No session could be auto-resolved — pick the correct one manually.",
	});

	const d = new frappe.ui.Dialog({
		title: `Sync Attendance Log — ${log.name}`,
		fields,
		primary_action_label: "Sync",
		primary_action(values) {
			frappe.call({
				method: "slcm.slcm.doctype.attendance_log.process_attendance_logs.sync_attendance_log",
				args: {
					log_name: log.name,
					session_name: values.session,
					student: values.student || null,
				},
				freeze: true,
				freeze_message: __("Syncing..."),
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({ message: __("Attendance synced successfully"), indicator: "green" });
					d.hide();
					load(wrapper);
				},
			});
		},
	});

	d.show();
}
