// Copyright (c) 2026, Azim Premji Foundation and contributors
// For license information, please see license.txt

frappe.query_reports["Fee Payment Zoho Journal Upload"] = {
	ignore_prepared_report: true,

	// ── Filters ───────────────────────────────────────────────────────────────
	filters: [
		{
			fieldname: "from_date",
			label:     __("From Date"),
			fieldtype: "Date",
			reqd:      1,
			default:   frappe.datetime.month_start(),
			on_change: function () { _fpzju_validate_and_refresh(); },
		},
		{
			fieldname: "to_date",
			label:     __("To Date"),
			fieldtype: "Date",
			reqd:      1,
			default:   frappe.datetime.month_end(),
			on_change: function () { _fpzju_validate_and_refresh(); },
		},
		{
			fieldname: "payment_mode",
			label:     __("Payment Mode"),
			fieldtype: "Select",
			options:   ["", "Cash", "Bank Transfer", "Cheque", "Credit Card", "Debit Card", "Online Payment", "Other"],
		},
		{
			fieldname: "program",
			label:     __("Programme"),
			fieldtype: "Link",
			options:   "Programme",
		},
		{
			fieldname: "bank_account",
			label:     __("Default Bank Account"),
			fieldtype: "Data",
			description: __("Used when a payment has no bank account of its own"),
		},
		{
			fieldname: "cash_account",
			label:     __("Default Cash Account"),
			fieldtype: "Data",
		},
		{
			fieldname: "journal_prefix",
			label:     __("Journal Number Prefix"),
			fieldtype: "Data",
		},
		{
			fieldname: "department",
			label:     __("Department (fallback)"),
			fieldtype: "Data",
		},
		{
			fieldname: "course",
			label:     __("Course (fallback)"),
			fieldtype: "Data",
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

		if (column.fieldname === "account") {
			var colour = data.row_type === "Credit" ? "#6a1b9a" : "#1565c0";
			return `<span style="color:${colour};font-weight:500;">${value}</span>`;
		}

		if (column.fieldname === "debit" && _fpzju_flt(data.debit) > 0) {
			return `<b style="color:#1565c0;">${value}</b>`;
		}
		if (column.fieldname === "credit" && _fpzju_flt(data.credit) > 0) {
			return `<b style="color:#2e7d32;">${value}</b>`;
		}

		return value;
	},

	// ── On load ───────────────────────────────────────────────────────────────
	onload: function (report) {
		report.ignore_prepared_report   = true;
		report.prepared_report          = false;
		report.prepared_report_document = null;

		report.page.add_inner_button(__("Download CSV"), function () {
			_fpzju_download(report, "csv");
		}, __("Export to Zoho Books"));

		report.page.add_inner_button(__("Download Excel (.xlsx)"), function () {
			_fpzju_download(report, "xlsx");
		}, __("Export to Zoho Books"));

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
			});
		}, 500);

		report.chart_options = { height: 260 };
	},
};


// ── Helpers ───────────────────────────────────────────────────────────────────

function _fpzju_safe_refresh(report) {
	var r = report || frappe.query_report;
	if (!r) return;
	r.ignore_prepared_report   = true;
	r.prepared_report          = false;
	r.prepared_report_document = null;
	r.prepared_report_name     = null;
	r.refresh();
}

function _fpzju_validate_and_refresh() {
	var from = frappe.query_report.get_filter_value("from_date");
	var to   = frappe.query_report.get_filter_value("to_date");
	if (from && to) {
		if (frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
			frappe.show_alert({ message: __("From Date cannot be after To Date."), indicator: "red" }, 4);
			return;
		}
		_fpzju_safe_refresh(frappe.query_report);
	}
}

function _fpzju_flt(v) { return parseFloat(v) || 0; }


// ── Download handler ──────────────────────────────────────────────────────────

function _fpzju_download(report, format) {
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

	_fpzju_show_loading(
		icon,
		__("Generating {0}", [label]),
		__(
			"Building Zoho Books journal entries from fee payments…<br><br>"
			+ "<small style='color:#94a3b8'>Validating Debit = Credit before export.</small>"
		)
	);

	frappe.call({
		method: "slcm.slcm.report.fee_payment_zoho_journal_upload.fee_payment_zoho_journal_upload.download_zoho_upload_file",
		args:   { filters: filters, file_format: format },
		callback: function (r) {
			_fpzju_hide_loading();
			if (!r || !r.message || !r.message.content) {
				frappe.msgprint({
					title:     __("Export Failed"),
					message:   __("No data returned. Check date filters."),
					indicator: "red",
				});
				return;
			}

			var msg = r.message;
			_fpzju_trigger_download(msg.content, msg.filename, msg.mime);

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
			_fpzju_hide_loading();
			frappe.msgprint({
				title:     __("Export Error"),
				message:   err.message || (err.exc_type ? err.exc_type + ": " + err.exception : JSON.stringify(err)),
				indicator: "red",
			});
		},
	});
}

function _fpzju_trigger_download(b64, filename, mime) {
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


// ── Loading overlay ───────────────────────────────────────────────────────────

function _fpzju_show_loading(icon, title, message) {
	var old = document.getElementById("fpzju-overlay");
	if (old) old.remove();

	if (!document.getElementById("fpzju-style")) {
		var s = document.createElement("style");
		s.id = "fpzju-style";
		s.textContent = `
			@keyframes fpzju-spin    { to { transform: rotate(360deg); } }
			@keyframes fpzju-pulse   { 0%,100%{transform:scale(.85);opacity:.55} 50%{transform:scale(1.1);opacity:.12} }
			@keyframes fpzju-fadein  { from{opacity:0;transform:translateY(18px) scale(.96)} to{opacity:1;transform:translateY(0) scale(1)} }
			@keyframes fpzju-shimmer { from{background-position:-500px 0} to{background-position:500px 0} }
		`;
		document.head.appendChild(s);
	}

	var el = document.createElement("div");
	el.id = "fpzju-overlay";
	el.innerHTML = `
		<div style="position:fixed;inset:0;background:rgba(8,14,36,.78);
			backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);
			z-index:99999;display:flex;align-items:center;justify-content:center;">
			<div style="background:#fff;border-radius:20px;padding:44px 52px 40px;
				max-width:430px;width:90%;text-align:center;
				box-shadow:0 28px 72px rgba(0,0,0,.30),0 0 0 1px rgba(94,100,255,.12);
				animation:fpzju-fadein .26s cubic-bezier(.22,1,.36,1) both;
				position:relative;overflow:hidden;">
				<div style="position:absolute;top:0;left:0;right:0;height:3px;
					background:linear-gradient(90deg,#5e64ff,#a78bfa,#5e64ff);
					background-size:500px 3px;
					animation:fpzju-shimmer 1.5s linear infinite;
					border-radius:20px 20px 0 0;"></div>
				<div style="position:relative;display:inline-block;margin-bottom:18px;margin-top:6px;">
					<div style="position:absolute;inset:-12px;border-radius:50%;
						background:radial-gradient(circle,rgba(94,100,255,.16) 0%,transparent 70%);
						animation:fpzju-pulse 2s ease-in-out infinite;"></div>
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
						animation:fpzju-spin .85s linear infinite;"></div>
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

function _fpzju_hide_loading() {
	var el = document.getElementById("fpzju-overlay");
	if (el) el.remove();
}
