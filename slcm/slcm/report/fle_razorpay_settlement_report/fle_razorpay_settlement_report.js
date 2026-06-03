// ── Custom loading overlay ────────────────────────────────────────────────────
function _fle_show_loading(icon, title, message) {
	var existing = document.getElementById("fle-loading-overlay");
	if (existing) existing.remove();

	if (!document.getElementById("fle-loading-style")) {
		var style = document.createElement("style");
		style.id = "fle-loading-style";
		style.textContent = `
			@keyframes fle-spin {
				0%   { transform: rotate(0deg); }
				100% { transform: rotate(360deg); }
			}
			@keyframes fle-pulse-ring {
				0%   { transform: scale(0.85); opacity: 0.6; }
				50%  { transform: scale(1.1);  opacity: 0.15; }
				100% { transform: scale(0.85); opacity: 0.6; }
			}
			@keyframes fle-fadein {
				from { opacity: 0; transform: translateY(16px) scale(0.97); }
				to   { opacity: 1; transform: translateY(0)    scale(1);    }
			}
			@keyframes fle-shimmer {
				0%   { background-position: -400px 0; }
				100% { background-position:  400px 0; }
			}
		`;
		document.head.appendChild(style);
	}

	var el = document.createElement("div");
	el.id = "fle-loading-overlay";
	el.innerHTML = `
		<div style="
			position:fixed;inset:0;
			background:rgba(10,18,40,0.75);
			backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
			z-index:99999;
			display:flex;align-items:center;justify-content:center;
		">
			<div style="
				background:#fff;
				border-radius:24px;
				padding:48px 52px 44px;
				max-width:440px;width:88%;
				text-align:center;
				box-shadow:0 32px 80px rgba(0,0,0,0.32), 0 0 0 1px rgba(255,255,255,0.08);
				animation:fle-fadein 0.28s cubic-bezier(.22,1,.36,1) both;
				position:relative;overflow:hidden;
			">
				<!-- shimmer bar at top -->
				<div style="
					position:absolute;top:0;left:0;right:0;height:4px;
					background:linear-gradient(90deg,#2490ef 0%,#5bc0eb 40%,#2490ef 100%);
					background-size:400px 4px;
					animation:fle-shimmer 1.6s linear infinite;
					border-radius:24px 24px 0 0;
				"></div>

				<!-- icon with pulsing ring -->
				<div style="position:relative;display:inline-block;margin-bottom:20px;margin-top:8px">
					<div style="
						position:absolute;inset:-10px;
						border-radius:50%;
						background:radial-gradient(circle,rgba(36,144,239,0.18) 0%,transparent 70%);
						animation:fle-pulse-ring 1.8s ease-in-out infinite;
					"></div>
					<div style="
						width:72px;height:72px;border-radius:50%;
						background:linear-gradient(135deg,#eef6ff 0%,#dbeeff 100%);
						display:flex;align-items:center;justify-content:center;
						font-size:34px;line-height:1;
						box-shadow:0 4px 16px rgba(36,144,239,0.2);
					">${icon}</div>
				</div>

				<!-- spinner -->
				<div style="margin:0 auto 20px;position:relative;width:36px;height:36px">
					<div style="
						position:absolute;inset:0;
						border:3px solid #e2eaf4;
						border-radius:50%;
					"></div>
					<div style="
						position:absolute;inset:0;
						border:3px solid transparent;
						border-top-color:#2490ef;
						border-radius:50%;
						animation:fle-spin 0.9s linear infinite;
					"></div>
				</div>

				<!-- title -->
				<div style="
					font-size:18px;font-weight:700;
					color:#0f172a;
					margin-bottom:10px;
					letter-spacing:-0.2px;
				">${title}</div>

				<!-- message -->
				<div style="
					font-size:13.5px;color:#64748b;
					line-height:1.7;
					max-width:320px;margin:0 auto;
				">${message}</div>
			</div>
		</div>
	`;
	document.body.appendChild(el);
}

function _fle_hide_loading() {
	var el = document.getElementById("fle-loading-overlay");
	if (el) el.remove();
}

frappe.query_reports["FLE Razorpay Settlement Report"] = {
	// Force live execution — never use background Prepared Report mode.
	// This report calls the Razorpay API directly; prepared_report=1 in the
	// DB causes the report_end_time JS crash. Setting this flag tells
	// Frappe's query_report.js to always pass ignore_prepared_report=true.
	ignore_prepared_report: true,

	onload: function (report) {
		// Permanently disable prepared-report mode on the server side too.
		// Runs silently each time the report is opened so the DB flag can
		// never drift back to 1 (e.g. after a bench migrate reset).
		frappe.db.set_value("Report", "FLE Razorpay Settlement Report", {
			prepared_report: 0,
			timeout: 300,
		}).catch(function () {
			// Non-fatal — report still works even if this silent patch fails
		});

		// ── Export buttons ────────────────────────────────────────────────
		report.page.add_inner_button(__("Download Excel"), function () {
			frappe.query_report.export_report("Excel");
		}, __("Export"));

		report.page.add_inner_button(__("Download CSV"), function () {
			frappe.query_report.export_report("CSV");
		}, __("Export"));

		// ── Diagnose Missing Names ────────────────────────────────────────
		report.page.add_inner_button(__("Diagnose Missing Names"), function () {
			_fle_show_loading(
				"🔍",
				__("Running Diagnosis"),
				__("Checking FLE Payment Log records for missing data…")
			);
			frappe.call({
				method: "slcm.api.sync_settlements.diagnose_quick",
				callback: function (r) {
					_fle_hide_loading();
					if (!r.message) {
						frappe.msgprint({ title: __("Error"), message: __("No response from server. Check Error Log."), indicator: "red" });
						return;
					}
					var d = r.message;
					var t = d.total_fle_records;

					// Empty DB — local or cloud with no data yet
					if (t === 0) {
						frappe.msgprint({
							title: __("Diagnosis Result"),
							message: `
								<div style="text-align:center;padding:20px">
									<div style="font-size:48px">📭</div>
									<h4 style="color:#d44">FLE Payment Log is empty on this site</h4>
									<p style="color:#666;font-size:13px">
										This is expected on a <b>local/development</b> site.<br>
										On the <b>cloud site (fle.nls.ac.in)</b>, this will show real data.<br><br>
										The settlement report data comes <b>directly from Razorpay API</b><br>
										and does not depend on local FLE Payment Log records<br>
										for the amounts — only for student name enrichment.
									</p>
								</div>`,
							indicator: "orange",
							wide: true,
						});
						return;
					}

					var fmt = function(n, total) {
						var pct = total ? Math.round((n / total) * 100) : 0;
						var color = pct === 100 ? "#28a745" : pct === 0 ? "#dc3545" : "#fd7e14";
						return n + ' <span style="color:' + color + ';font-weight:bold;font-size:12px"> ' + pct + '%</span>';
					};

					var html = `
						<table class="table table-bordered" style="font-size:13px;margin-bottom:0">
							<thead>
								<tr style="background:#f0f4f8;font-weight:bold">
									<th style="width:70%">Check</th>
									<th style="width:30%;text-align:right">Count</th>
								</tr>
							</thead>
							<tbody>
								<tr style="background:#e9ecef">
									<td><b>Total FLE Payment Log records</b></td>
									<td style="text-align:right"><b>${t}</b></td>
								</tr>
								<tr style="background:#d4edda">
									<td>✔&nbsp; Has Razorpay Payment ID (pay_xxx)</td>
									<td style="text-align:right">${fmt(d.with_razorpay_payment_id, t)}</td>
								</tr>
								<tr style="background:#f8d7da">
									<td>✘&nbsp; Missing Razorpay Payment ID</td>
									<td style="text-align:right">${fmt(d.missing_razorpay_payment_id, t)}</td>
								</tr>
								<tr style="background:#d4edda">
									<td>✔&nbsp; Has Contact Name</td>
									<td style="text-align:right">${fmt(d.with_contact_name, t)}</td>
								</tr>
								<tr style="background:#f8d7da">
									<td>✘&nbsp; Missing Contact Name</td>
									<td style="text-align:right">${fmt(d.missing_contact_name, t)}</td>
								</tr>
								<tr style="background:#d4edda">
									<td>✔&nbsp; Synced with Settlement (has Settlement ID)</td>
									<td style="text-align:right">${fmt(d.synced_with_settlement, t)}</td>
								</tr>
								<tr style="background:#fff3cd">
									<td>⏳&nbsp; Settlement not yet synced</td>
									<td style="text-align:right">${fmt(d.not_yet_synced, t)}</td>
								</tr>
							</tbody>
						</table>
						<p style="margin-top:10px;font-size:12px;color:#555;background:#f8f9fa;padding:8px;border-radius:4px">
							💡 If <b>Settlement not yet synced</b> is high → run <b>Actions → Sync Settlements</b><br>
							💡 If <b>Missing Contact Name</b> is high → run <b>Actions → Fix Contact Names</b>
						</p>
					`;
					frappe.msgprint({
						title: __("FLE Payment Log — Diagnosis Result"),
						message: html,
						indicator: "blue",
						wide: true,
					});
				},
			});
		}, __("Actions"));

		// ── Fix Contact Names ─────────────────────────────────────────────
		report.page.add_inner_button(__("Fix Contact Names"), function () {
			_fle_show_loading(
				"✏️",
				__("Fixing Contact Names"),
				__("Copying student names and emails into FLE Payment Log.<br>This will only take a moment…")
			);
			frappe.call({
				method: "slcm.api.sync_settlements.backfill_contact_names",
				callback: function (r) {
					_fle_hide_loading();
					if (r.message) {
						frappe.msgprint({ title: __("Done"), message: r.message, indicator: "green" });
						frappe.query_report.refresh();
					}
				},
			});
		}, __("Actions"));

		// ── Sync Settlements (background job — avoids 504 timeout) ──────────
		report.page.add_inner_button(__("Sync Settlements"), function () {
			frappe.confirm(
				__("We will securely fetch your latest settlement data directly from Razorpay and update the FLE Payment Log with accurate UTR numbers, gateway fees, and net amounts. No payment data will be modified — this is a read-only sync. Ready to proceed?"),
				function () {
					_fle_show_loading(
						"🔐",
						__("Syncing with Razorpay"),
						__("Securely connecting to Razorpay and fetching your latest settlement records.<br><br>Your data is safe — this is a read-only operation.<br>Please keep this tab open.")
					);

					// Enqueue as background job — avoids 504 gateway timeout
					frappe.call({
						method: "slcm.api.sync_settlements.run_sync_background",
						callback: function (r) {
							if (!r || !r.message) {
								_fle_hide_loading();
								frappe.show_alert({ message: __("Failed to start sync. Check Error Log."), indicator: "red" }, 8);
								return;
							}
							_fle_poll_sync(r.message.job_id || "", 0);
						},
						error: function () {
							_fle_hide_loading();
							frappe.show_alert({ message: __("Failed to start sync. Check Error Log."), indicator: "red" }, 8);
						},
					});

					function _fle_poll_sync(job_id, attempts) {
						if (attempts > 150) {
							_fle_hide_loading();
							frappe.show_alert({ message: __("Sync is taking longer than expected — refresh in a few minutes."), indicator: "orange" }, 15);
							return;
						}
						setTimeout(function () {
							frappe.call({
								method: "slcm.api.sync_settlements.get_sync_status",
								args:   { job_id: job_id },
								callback: function (r) {
									var status = r && r.message ? r.message.status : "unknown";
									var result = r && r.message ? (r.message.result || "") : "";
									if (status === "finished") {
										_fle_hide_loading();
										frappe.msgprint({ title: __("Sync Complete"), message: result || __("Done."), indicator: "green" });
										frappe.query_report.refresh();
									} else if (status === "failed") {
										_fle_hide_loading();
										frappe.show_alert({ message: __("Sync failed. Check the Error Log."), indicator: "red" }, 10);
									} else {
										_fle_poll_sync(job_id, attempts + 1);
									}
								},
								error: function () { _fle_poll_sync(job_id, attempts + 1); },
							});
						}, 4000);
					}
				}
			);
		}, __("Actions"));

		// ── Color the three action buttons in the dropdown ────────────────
		var _fle_action_styles = {
			"Diagnose Missing Names": "#1d4ed8",   // blue
			"Fix Contact Names":      "#b45309",   // amber
			"Sync Settlements":       "#15803d",   // green
		};

		function _fle_style_actions() {
			document.querySelectorAll(".dropdown-menu .dropdown-item, .dropdown-menu li a").forEach(function (el) {
				var text = (el.textContent || "").trim();
				var color = _fle_action_styles[text];
				if (color && !el.dataset.fleStyled) {
					el.dataset.fleStyled = "1";
					el.style.color      = color;
					el.style.fontWeight = "600";
					el.addEventListener("mouseenter", function () { this.style.background = color + "15"; });
					el.addEventListener("mouseleave", function () { this.style.background = ""; });
				}
			});
		}

		// Run once after render, then re-run each time any dropdown opens
		setTimeout(_fle_style_actions, 500);
		document.addEventListener("click", function () {
			setTimeout(_fle_style_actions, 80);
		});
	},

	before_submit: function (filters) {
		var from = filters.from_date;
		var to   = filters.to_date;
		if (from && to && frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
			frappe.msgprint({
				title: __("Invalid Date Range"),
				message: __("From Date cannot be after To Date."),
				indicator: "red",
			});
			return false;
		}
	},

	filters: [
		// ── Row 1: Date range ─────────────────────────────────────────────
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
			on_change: function () {
				var from = frappe.query_report.get_filter_value("from_date");
				var to   = frappe.query_report.get_filter_value("to_date");
				if (from && to) {
					if (frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
						frappe.msgprint({
							title: __("Invalid Date Range"),
							message: __("From Date cannot be after To Date."),
							indicator: "orange",
						});
						return;
					}
					frappe.query_report.refresh();
				}
			},
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
			on_change: function () {
				var from = frappe.query_report.get_filter_value("from_date");
				var to   = frappe.query_report.get_filter_value("to_date");
				if (from && to) {
					if (frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
						frappe.msgprint({
							title: __("Invalid Date Range"),
							message: __("To Date cannot be before From Date."),
							indicator: "orange",
						});
						return;
					}
					frappe.query_report.refresh();
				}
			},
		},
		// ── Row 2: Status & Payment Method ───────────────────────────────
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nSettled\nPending",
			reqd: 0,
		},
		{
			fieldname: "payment_method",
			label: __("Payment Method"),
			fieldtype: "Select",
			options: "\nUpi\nCard\nNetbanking\nWallet",
			reqd: 0,
		},
		// ── Row 3: Amount range ───────────────────────────────────────────
		{
			fieldname: "min_amount",
			label: __("Min Amount (₹)"),
			fieldtype: "Currency",
			reqd: 0,
		},
		{
			fieldname: "max_amount",
			label: __("Max Amount (₹)"),
			fieldtype: "Currency",
			reqd: 0,
		},
		// ── Row 4: Settlement ID & Search ─────────────────────────────────
		{
			fieldname: "settlement_id",
			label: __("Settlement ID"),
			fieldtype: "Data",
			reqd: 0,
			placeholder: "setl_xxx — partial match allowed",
		},
		{
			fieldname: "search",
			label: __("Search"),
			fieldtype: "Data",
			reqd: 0,
			placeholder: "Name / Student ID / pay_xxx / UTR",
		},
		// ── Row 5: FLE Only + Missing data filters ────────────────────────────
		{
			fieldname: "show_fle_only",
			label: __("FLE Payments Only"),
			fieldtype: "Check",
			default: 0,
			reqd: 0,
			on_change: function () {
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "missing_data",
			label: __("Show Records Where"),
			fieldtype: "Select",
			options: "\nContact Name is Blank\nContact Name is Filled\nStudent ID is Blank\nStudent ID is Filled\nPayment Method is Blank\nPayment Method is Filled",
			reqd: 0,
		},
	],
};
