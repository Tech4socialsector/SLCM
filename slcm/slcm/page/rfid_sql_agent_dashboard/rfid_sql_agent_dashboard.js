// Copyright (c) 2026, Nishanth and contributors
// RFID SQL Agent Dashboard — monitoring for the SQL Server puller

const AUTO_REFRESH_MS = 30000;
const AUTO_REFRESH_STORAGE_KEY = "rfid_sql_agent_dashboard_auto_refresh";

frappe.pages["rfid-sql-agent-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "RFID SQL Agent Dashboard",
		single_column: true,
	});

	page.set_primary_action("Run Now", () => run_now(wrapper), "fa fa-refresh");
	page.add_menu_item("Open Settings", () => frappe.set_route("Form", "RFID SQL Agent Settings"));

	const stored = localStorage.getItem(AUTO_REFRESH_STORAGE_KEY);
	wrapper._auto_refresh_on = stored === null ? true : stored === "1";

	wrapper._auto_refresh_btn = page.add_inner_button(
		auto_refresh_label(wrapper._auto_refresh_on),
		() => toggle_auto_refresh(wrapper)
	);

	$(build_html()).appendTo($(wrapper).find(".page-content, .layout-main-section").first());
	load(wrapper);

	if (wrapper._auto_refresh_on) {
		start_auto_refresh(wrapper);
	}
};

frappe.pages["rfid-sql-agent-dashboard"].on_page_hide = function (wrapper) {
	stop_auto_refresh(wrapper);
};

function auto_refresh_label(on) {
	return on ? "Auto Refresh: On (30s)" : "Auto Refresh: Off";
}

function start_auto_refresh(wrapper) {
	stop_auto_refresh(wrapper);
	wrapper._rfid_sql_agent_interval = setInterval(() => load(wrapper), AUTO_REFRESH_MS);
}

function stop_auto_refresh(wrapper) {
	if (wrapper._rfid_sql_agent_interval) {
		clearInterval(wrapper._rfid_sql_agent_interval);
		wrapper._rfid_sql_agent_interval = null;
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
		<div class="rfid-sql-agent-dashboard">
			<div class="row" style="margin: 0 0 20px;">
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="cp-total">-</div><div class="stat-label">Total Punches</div></div></div>
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="cp-matched">-</div><div class="stat-label">Matched to Student</div></div></div>
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="cp-unmatched">-</div><div class="stat-label">Unmatched</div></div></div>
				<div class="col-sm-3"><div class="stat-card"><div class="stat-value" id="cp-watermark">-</div><div class="stat-label">Last Log ID</div></div></div>
			</div>
			<div style="margin-bottom: 10px;">
				<span id="cp-status-dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#ccc;margin-right:6px;"></span>
				<span id="cp-status-text">Loading...</span>
				<span class="text-muted" id="cp-shown-count" style="float:right;"></span>
			</div>
			<div id="cp-datatable"></div>
		</div>
		<style>
			.stat-card { background: var(--card-bg, #fff); border: 1px solid var(--border-color, #d1d8dd); border-radius: 8px; padding: 16px; text-align: center; }
			.stat-value { font-size: 1.8rem; font-weight: 700; }
			.stat-label { font-size: .8rem; color: var(--text-muted, #8d99a6); text-transform: uppercase; }
		</style>
	`;
}

const DT_COLUMNS = [
	{ name: "Emp Code", id: "emp_code", width: 140 },
	{ name: "Student", id: "student", width: 160 },
	{ name: "Punch Time", id: "punch_time", width: 170 },
	{ name: "Terminal", id: "terminal_id", width: 100 },
	{ name: "Location", id: "terminal_alias", width: 140 },
	{ name: "Status", id: "sync_status", width: 110 },
];

function rows_to_datatable_data(recent) {
	return (recent || []).map((row) => [
		row.emp_code || "",
		row.student ? row.student_name || row.student : "Unmapped",
		frappe.datetime.str_to_user(row.punch_time) || "",
		row.terminal_id || "",
		row.terminal_alias || "",
		row.sync_status || "",
	]);
}

function format_interval(seconds) {
	seconds = seconds || 300;
	if (seconds % 60 === 0) {
		const mins = seconds / 60;
		return mins === 1 ? "1 minute" : `${mins} minutes`;
	}
	return seconds === 1 ? "1 second" : `${seconds} seconds`;
}

function load(wrapper) {
	frappe.call({
		method: "slcm.slcm.rfid_sql_agent.poller.get_dashboard_summary",
		callback(r) {
			if (!r.message) return;
			render(wrapper, r.message);
		},
	});
}

function render(wrapper, d) {
	const $w = $(wrapper);
	$w.find("#cp-total").text(d.stats.total_punches || 0);
	$w.find("#cp-matched").text(d.stats.matched || 0);
	$w.find("#cp-unmatched").text(d.stats.unmatched || 0);
	$w.find("#cp-watermark").text(d.last_log_id || 0);

	$w.find("#cp-status-dot").css("background", d.enabled ? "#28a745" : "#dc3545");
	const refreshed_at = new Date().toLocaleTimeString();
	$w.find("#cp-status-text").text(
		(d.enabled
			? `Enabled — polling every ${format_interval(d.poll_interval_seconds)}. Last swipe: ${frappe.datetime.str_to_user(d.stats.last_punch) || "none yet"}`
			: "Disabled — turn on 'Enable RFID SQL Agent' in RFID SQL Agent Settings.") +
			`  ·  Dashboard refreshed at ${refreshed_at}`
	);

	const data = rows_to_datatable_data(d.recent);
	$w.find("#cp-shown-count").text(
		d.recent && d.recent.length ? `Showing ${d.recent.length} most recent (searchable/sortable below)` : ""
	);

	if (!wrapper._rfid_dt) {
		wrapper._rfid_dt = new frappe.DataTable(wrapper.querySelector("#cp-datatable"), {
			columns: DT_COLUMNS,
			data,
			layout: "fluid",
			serialNoColumn: true,
			inlineFilters: true,
			clusterize: true,
			noDataMessage: "No punches yet.",
		});
	} else {
		wrapper._rfid_dt.refresh(data, DT_COLUMNS);
	}
}

function run_now(wrapper) {
	frappe.call({
		method: "slcm.slcm.rfid_sql_agent.poller.poll_now",
		freeze: true,
		freeze_message: __("Polling SQL Server..."),
		callback(r) {
			if (!r.message) return;
			frappe.show_alert({
				message: r.message.message,
				indicator: r.message.success ? "green" : "red",
			});
			load(wrapper);
		},
	});
}
