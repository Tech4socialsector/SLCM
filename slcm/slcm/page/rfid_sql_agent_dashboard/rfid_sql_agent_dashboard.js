// Copyright (c) 2026, Nishanth and contributors
// RFID SQL Agent Dashboard — monitoring for the SQL Server puller

frappe.pages["rfid-sql-agent-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "RFID SQL Agent Dashboard",
		single_column: true,
	});

	page.set_primary_action("Run Now", () => run_now(wrapper), "fa fa-refresh");
	page.add_menu_item("Open Settings", () => frappe.set_route("Form", "RFID SQL Agent Settings"));

	$(build_html()).appendTo($(wrapper).find(".page-content, .layout-main-section").first());
	load(wrapper);

	wrapper._rfid_sql_agent_interval = setInterval(() => load(wrapper), 30000);
};

frappe.pages["rfid-sql-agent-dashboard"].on_page_hide = function (wrapper) {
	if (wrapper._rfid_sql_agent_interval) {
		clearInterval(wrapper._rfid_sql_agent_interval);
		wrapper._rfid_sql_agent_interval = null;
	}
};

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
			</div>
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>Emp Code</th><th>Student</th><th>Punch Time</th>
						<th>Terminal</th><th>Location</th><th>Status</th>
					</tr>
				</thead>
				<tbody id="cp-feed-body"><tr><td colspan="6" class="text-muted">Loading...</td></tr></tbody>
			</table>
		</div>
		<style>
			.stat-card { background: var(--card-bg, #fff); border: 1px solid var(--border-color, #d1d8dd); border-radius: 8px; padding: 16px; text-align: center; }
			.stat-value { font-size: 1.8rem; font-weight: 700; }
			.stat-label { font-size: .8rem; color: var(--text-muted, #8d99a6); text-transform: uppercase; }
		</style>
	`;
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
	$w.find("#cp-status-text").text(
		d.enabled
			? `Enabled — polling every 5 minutes. Last swipe: ${frappe.datetime.str_to_user(d.stats.last_punch) || "none yet"}`
			: "Disabled — turn on 'Enable RFID SQL Agent' in RFID SQL Agent Settings."
	);

	const rows = (d.recent || [])
		.map(
			(row) => `
			<tr>
				<td>${frappe.utils.escape_html(row.emp_code || "")}</td>
				<td>${row.student ? frappe.utils.escape_html(row.student_name || row.student) : '<span class="text-muted">Unmapped</span>'}</td>
				<td>${frappe.datetime.str_to_user(row.punch_time) || ""}</td>
				<td>${frappe.utils.escape_html(row.terminal_id || "")}</td>
				<td>${frappe.utils.escape_html(row.terminal_alias || "")}</td>
				<td><span class="indicator ${row.sync_status === "Matched" ? "green" : "orange"}">${row.sync_status}</span></td>
			</tr>`
		)
		.join("");

	$w.find("#cp-feed-body").html(rows || '<tr><td colspan="6" class="text-muted">No punches yet.</td></tr>');
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
