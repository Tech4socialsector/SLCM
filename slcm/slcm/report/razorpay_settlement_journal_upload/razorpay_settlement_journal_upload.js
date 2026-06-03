// Copyright (c) 2026, Azim Premji Foundation and contributors
// For license information, please see license.txt

frappe.query_reports["Razorpay Settlement Journal Upload"] = {
	ignore_prepared_report: true,

	// ── Filters ───────────────────────────────────────────────────────────────
	filters: [
		// ── Row 1: Date range ─────────────────────────────────────────────────
		{
			fieldname: "from_date",
			label:     __("From Date"),
			fieldtype: "Date",
			reqd:      1,
			on_change: function () { _rsjur_validate_and_refresh(); },
		},
		{
			fieldname: "to_date",
			label:     __("To Date"),
			fieldtype: "Date",
			reqd:      1,
			on_change: function () { _rsjur_validate_and_refresh(); },
		},
		// ── Row 2: Account config (dynamic — loaded from Razorpay Settings) ───
		{
			fieldname:   "bank_account",
			label:       __("Bank Account (Debit)"),
			fieldtype:   "Data",
			description: __("Populated from Razorpay Settings on load. Must match Zoho Books chart of accounts."),
		},
		{
			fieldname:   "credit_account",
			label:       __("Credit Account"),
			fieldtype:   "Data",
			description: __("Income account as it appears in Zoho Books."),
		},
		// ── Row 3: Journal config (dynamic defaults) ──────────────────────────
		{
			fieldname:   "journal_prefix",
			label:       __("Journal Prefix"),
			fieldtype:   "Data",
			description: __("Prefix for Journal Number (e.g. JN-FP-)."),
		},
		{
			fieldname: "department",
			label:     __("Department"),
			fieldtype: "Data",
		},
		{
			fieldname: "course",
			label:     __("Course"),
			fieldtype: "Data",
		},
		// ── Row 4: Settlement filters ──────────────────────────────────────────
		{
			fieldname: "settlement_status",
			label:     __("Settlement Status"),
			fieldtype: "Select",
			options:   "\nAll\nprocessed\ncreated\nsettled",
		},
		{
			fieldname:   "settlement_id",
			label:       __("Settlement ID"),
			fieldtype:   "Data",
			placeholder: "setl_xxx — partial match",
		},
		// ── Row 5: Amount range ────────────────────────────────────────────────
		{
			fieldname: "min_amount",
			label:     __("Min Amount (₹)"),
			fieldtype: "Currency",
		},
		{
			fieldname: "max_amount",
			label:     __("Max Amount (₹)"),
			fieldtype: "Currency",
		},
		// ── Row 6: View filters ────────────────────────────────────────────────
		{
			fieldname:   "row_type",
			label:       __("Row Type"),
			fieldtype:   "Select",
			options:     "\nAll\nDebit\nCredit",
			description: __("Show All rows, Debit only, or Credit only."),
		},
		{
			fieldname:   "fle_only",
			label:       __("FLE Payments Only"),
			fieldtype:   "Check",
			description: __("Show only settlements matched in FLE Payment Log."),
			on_change:   function () { _rsjur_safe_refresh(frappe.query_report); },
		},
	],

	// ── Row formatter ─────────────────────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (column.fieldname === "row_type") {
			if (data.row_type === "Credit") {
				return `<span style="background:#e8f5e9;color:#2e7d32;padding:2px 10px;
					border-radius:12px;font-weight:700;font-size:11px;letter-spacing:.3px;
					border:1px solid #a5d6a7;">&#8593; Credit</span>`;
			}
			if (data.row_type === "Debit") {
				return `<span style="background:#e3f2fd;color:#1565c0;padding:2px 10px;
					border-radius:12px;font-weight:700;font-size:11px;letter-spacing:.3px;
					border:1px solid #90caf9;">&#8595; Debit</span>`;
			}
		}

		if (column.fieldname === "settlement_status") {
			var icons = { processed: ["#2e7d32","&#10003;"], created: ["#e65100","&#9679;"], settled: ["#1565c0","&#10003;"] };
			var st = (data.settlement_status || "").toLowerCase();
			if (icons[st]) {
				return `<span style="color:${icons[st][0]};font-weight:600;">${icons[st][1]} ${st}</span>`;
			}
		}

		if (column.fieldname === "account") {
			var colour = data.row_type === "Credit" ? "#6a1b9a" : "#1565c0";
			return `<span style="color:${colour};font-weight:500;">${value}</span>`;
		}

		if (column.fieldname === "debit" && _rsjur_flt(data.debit) > 0) {
			return `<b style="color:#1565c0;">${value}</b>`;
		}
		if (column.fieldname === "credit" && _rsjur_flt(data.credit) > 0) {
			return `<b style="color:#2e7d32;">${value}</b>`;
		}

		if (column.fieldname === "fle_match") {
			return data.fle_match === "Yes"
				? `<span style="background:#e8f5e9;color:#2e7d32;padding:1px 8px;
					border-radius:10px;font-size:11px;font-weight:600;
					border:1px solid #a5d6a7;">&#10003; Yes</span>`
				: `<span style="background:#fafafa;color:#9e9e9e;padding:1px 8px;
					border-radius:10px;font-size:11px;border:1px solid #e0e0e0;">No</span>`;
		}

		if (column.fieldname === "utr" && value) {
			return `<span style="font-family:monospace;font-size:11px;color:#37474f;">${value}</span>`;
		}

		return value;
	},

	// ── On load ───────────────────────────────────────────────────────────────
	onload: function (report) {
		// ── Kill prepared_report mode completely ──────────────────────────────
		// Set on the live instance immediately — this is what query_report.js reads
		report.ignore_prepared_report  = true;
		report.prepared_report         = false;
		report.prepared_report_document = null;

		// Persist to DB so it survives page reloads (use frappe.call — it's
		// synchronous in the request queue, unlike frappe.db.set_value)
		frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype:   "Report",
				name:      "Razorpay Settlement Journal Upload",
				fieldname: { prepared_report: 0 },
			},
			async: false,
		}).catch(function () {});

		// ── Export to Zoho Books dropdown ─────────────────────────────────────
		report.page.add_inner_button(__("Download CSV"), function () {
			_rsjur_download(report, "csv");
		}, __("Export to Zoho Books"));

		report.page.add_inner_button(__("Download Excel (.xlsx)"), function () {
			_rsjur_download(report, "xlsx");
		}, __("Export to Zoho Books"));

		// ── Actions dropdown ──────────────────────────────────────────────────
		report.page.add_inner_button(__("Sync Settlements"), function () {
			_rsjur_sync_settlements(report);
		}, __("Actions"));

		// ── Style buttons ─────────────────────────────────────────────────────
		setTimeout(function () {
			document.querySelectorAll(".inner-group-button").forEach(function (btn) {
				var text = (btn.textContent || "").trim();
				if (text === __("Export to Zoho Books")) {
					Object.assign(btn.style, {
						background:  "#5e64ff",
						color:       "#fff",
						borderColor: "#5e64ff",
						fontWeight:  "600",
					});
					btn.addEventListener("mouseenter", function () { this.style.opacity = ".85"; });
					btn.addEventListener("mouseleave", function () { this.style.opacity = "1"; });
				}
				if (text === __("Actions")) {
					Object.assign(btn.style, {
						background:  "#2e7d32",
						color:       "#fff",
						borderColor: "#2e7d32",
						fontWeight:  "600",
					});
					btn.addEventListener("mouseenter", function () { this.style.opacity = ".85"; });
					btn.addEventListener("mouseleave", function () { this.style.opacity = "1"; });
				}
			});
		}, 500);

		report.chart_options = { height: 260 };
	},
};


// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Safe refresh — always clears prepared_report state before calling refresh().
 * Prevents: "Cannot read properties of null (reading 'report_end_time')"
 * which occurs when Frappe's add_prepared_report_buttons() receives a doc
 * whose report_end_time is null.
 */
function _rsjur_safe_refresh(report) {
	var r = report || frappe.query_report;
	if (!r) return;
	r.ignore_prepared_report   = true;
	r.prepared_report          = false;
	r.prepared_report_document = null;
	r.prepared_report_name     = null;
	r.refresh();
}

function _rsjur_validate_and_refresh() {
	var from = frappe.query_report.get_filter_value("from_date");
	var to   = frappe.query_report.get_filter_value("to_date");
	if (from && to) {
		if (frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
			frappe.show_alert({ message: __("From Date cannot be after To Date."), indicator: "red" }, 4);
			return;
		}
		_rsjur_safe_refresh(frappe.query_report);
	}
}

function _rsjur_flt(v) { return parseFloat(v) || 0; }


// ── Download handler ──────────────────────────────────────────────────────────

function _rsjur_download(report, format) {
	var filters = report.get_filter_values();

	if (!filters.from_date || !filters.to_date) {
		frappe.msgprint({
			title:     __("Missing Filters"),
			message:   __("Please set both <b>From Date</b> and <b>To Date</b> before exporting."),
			indicator: "orange",
		});
		return;
	}

	var label = format === "xlsx" ? "Excel (.xlsx)" : "CSV";
	var icon  = format === "xlsx" ? "📊" : "📄";

	_rsjur_show_loading(
		icon,
		__("Generating {0}", [label]),
		__(
			"Fetching live settlement data from Razorpay<br>"
			+ "and building Zoho Books journal entries…<br><br>"
			+ "<small style='color:#94a3b8'>Validating Debit = Credit before export.</small>"
		)
	);

	frappe.call({
		method: "slcm.slcm.report.razorpay_settlement_journal_upload.razorpay_settlement_journal_upload.download_zoho_upload_file",
		args:   { filters: filters, file_format: format },
		callback: function (r) {
			_rsjur_hide_loading();
			if (!r || !r.message || !r.message.content) {
				frappe.msgprint({
					title:     __("Export Failed"),
					message:   __("No data returned. Check date filters and Razorpay credentials in Razorpay Settings."),
					indicator: "red",
				});
				return;
			}

			var msg = r.message;
			_rsjur_trigger_download(msg.content, msg.filename, msg.mime);

			// Show balance confirmation after download
			var bal_html = msg.balanced
				? `<span style="color:#2e7d32;font-weight:700;">&#10003; Balanced</span>`
				: `<span style="color:#c62828;font-weight:700;">&#10007; UNBALANCED</span>`;

			frappe.show_alert({
				message: __(
					"&#10003; Downloaded <b>{0}</b> &mdash; {1} rows | {2}",
					[msg.filename, msg.row_count || 0, bal_html]
				),
				indicator: "green",
			}, 10);
		},
		error: function (err) {
			_rsjur_hide_loading();
			// Show the server-side validation error prominently
			frappe.msgprint({
				title:     __("Export Error"),
				message:   err.message || (err.exc_type ? err.exc_type + ": " + err.exception : JSON.stringify(err)),
				indicator: "red",
			});
		},
	});
}

function _rsjur_trigger_download(b64, filename, mime) {
	try {
		var binary = atob(b64);
		var bytes  = new Uint8Array(binary.length);
		for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
		var blob = new Blob([bytes], { type: mime });
		var url  = URL.createObjectURL(blob);
		var a    = document.createElement("a");
		a.href = url; a.download = filename;
		document.body.appendChild(a); a.click();
		document.body.removeChild(a); URL.revokeObjectURL(url);
	} catch (e) {
		frappe.msgprint({ title: __("Download Error"), message: e.message, indicator: "red" });
	}
}


// ── Settlement sync (background job — avoids 504 timeout) ────────────────────

function _rsjur_sync_settlements(report) {
	_rsjur_show_loading(
		"🔒",
		__("Syncing with Razorpay"),
		__(
			"Securely connecting to Razorpay and fetching "
			+ "your latest settlement records.<br><br>"
			+ "Your data is safe — this is a read-only operation.<br>"
			+ "<small style='color:#94a3b8'>Please keep this tab open.</small>"
		)
	);

	// Step 1: enqueue the sync as a background job (returns instantly, no timeout)
	frappe.call({
		method:  "slcm.api.sync_settlements.run_sync_background",
		callback: function (r) {
			if (!r || !r.message) {
				_rsjur_hide_loading();
				frappe.show_alert({ message: __("Failed to start sync. Check Error Log."), indicator: "red" }, 8);
				return;
			}
			var job_id = r.message.job_id || "";
			// Step 2: poll for completion
			_rsjur_poll_sync(report, job_id, 0);
		},
		error: function () {
			_rsjur_hide_loading();
			frappe.show_alert({ message: __("Failed to start sync. Check Error Log."), indicator: "red" }, 8);
		},
	});
}

function _rsjur_poll_sync(report, job_id, attempts) {
	// Poll every 4 seconds, give up after 150 attempts (10 minutes)
	if (attempts > 150) {
		_rsjur_hide_loading();
		frappe.show_alert({
			message:   __("Sync is taking longer than expected. It may still be running — refresh the report in a few minutes."),
			indicator: "orange",
		}, 15);
		return;
	}

	setTimeout(function () {
		frappe.call({
			method: "slcm.api.sync_settlements.get_sync_status",
			args:   { job_id: job_id },
			callback: function (r) {
				var status = (r && r.message && r.message.status) ? r.message.status : "unknown";
				var result = (r && r.message && r.message.result) ? r.message.result : "";

				if (status === "finished") {
					_rsjur_hide_loading();
					var match = result.match(/Total updated:\s*(\d+)/);
					var count = match ? parseInt(match[1]) : null;
					if (count !== null && count === 0) {
						frappe.show_alert({
							message:   __("Sync complete — <b>0 records updated</b>. FLE Payment Log may not have matching payment IDs yet."),
							indicator: "orange",
						}, 12);
					} else {
						frappe.show_alert({
							message:   __("&#10003; {0}", [result || "Sync complete."]),
							indicator: "green",
						}, 12);
					}
					_rsjur_safe_refresh(report);

				} else if (status === "failed") {
					_rsjur_hide_loading();
					frappe.show_alert({
						message:   __("Sync failed. Check the Error Log for details."),
						indicator: "red",
					}, 10);

				} else {
					// still queued or started — keep polling
					_rsjur_poll_sync(report, job_id, attempts + 1);
				}
			},
			error: function () {
				// network blip — keep polling
				_rsjur_poll_sync(report, job_id, attempts + 1);
			},
		});
	}, 4000);
}


// ── Loading overlay ───────────────────────────────────────────────────────────

function _rsjur_show_loading(icon, title, message) {
	var old = document.getElementById("rsjur-overlay");
	if (old) old.remove();

	if (!document.getElementById("rsjur-style")) {
		var s = document.createElement("style");
		s.id = "rsjur-style";
		s.textContent = `
			@keyframes rsjur-spin    { to { transform: rotate(360deg); } }
			@keyframes rsjur-pulse   { 0%,100%{transform:scale(.85);opacity:.55} 50%{transform:scale(1.1);opacity:.12} }
			@keyframes rsjur-fadein  { from{opacity:0;transform:translateY(18px) scale(.96)} to{opacity:1;transform:translateY(0) scale(1)} }
			@keyframes rsjur-shimmer { from{background-position:-500px 0} to{background-position:500px 0} }
		`;
		document.head.appendChild(s);
	}

	var el = document.createElement("div");
	el.id = "rsjur-overlay";
	el.innerHTML = `
		<div style="position:fixed;inset:0;background:rgba(8,14,36,.78);
			backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);
			z-index:99999;display:flex;align-items:center;justify-content:center;">
			<div style="background:#fff;border-radius:20px;padding:44px 52px 40px;
				max-width:430px;width:90%;text-align:center;
				box-shadow:0 28px 72px rgba(0,0,0,.30),0 0 0 1px rgba(94,100,255,.12);
				animation:rsjur-fadein .26s cubic-bezier(.22,1,.36,1) both;
				position:relative;overflow:hidden;">
				<div style="position:absolute;top:0;left:0;right:0;height:3px;
					background:linear-gradient(90deg,#5e64ff,#a78bfa,#5e64ff);
					background-size:500px 3px;
					animation:rsjur-shimmer 1.5s linear infinite;
					border-radius:20px 20px 0 0;"></div>
				<div style="position:relative;display:inline-block;margin-bottom:18px;margin-top:6px;">
					<div style="position:absolute;inset:-12px;border-radius:50%;
						background:radial-gradient(circle,rgba(94,100,255,.16) 0%,transparent 70%);
						animation:rsjur-pulse 2s ease-in-out infinite;"></div>
					<div style="width:68px;height:68px;border-radius:50%;
						background:linear-gradient(135deg,#eef0ff 0%,#dde1ff 100%);
						display:flex;align-items:center;justify-content:center;
						font-size:30px;box-shadow:0 4px 14px rgba(94,100,255,.22);">
						${icon}
					</div>
				</div>
				<div style="margin:0 auto 18px;position:relative;width:34px;height:34px;">
					<div style="position:absolute;inset:0;border:3px solid #ede9fe;border-radius:50%;"></div>
					<div style="position:absolute;inset:0;border:3px solid transparent;
						border-top-color:#5e64ff;border-radius:50%;
						animation:rsjur-spin .85s linear infinite;"></div>
				</div>
				<div style="font-size:17px;font-weight:700;color:#0f172a;margin-bottom:10px;letter-spacing:-.2px;">
					${title}
				</div>
				<div style="font-size:13px;color:#64748b;line-height:1.75;max-width:300px;margin:0 auto;">
					${message}
				</div>
			</div>
		</div>`;
	document.body.appendChild(el);
}

function _rsjur_hide_loading() {
	var el = document.getElementById("rsjur-overlay");
	if (el) el.remove();
}
