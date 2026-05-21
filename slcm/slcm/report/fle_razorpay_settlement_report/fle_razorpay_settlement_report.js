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
			frappe.call({
				method: "slcm.api.sync_settlements.diagnose_missing_matches",
				freeze: true,
				freeze_message: __("🔍  Analysing Razorpay settlements vs FLE Payment Log… This may take a moment."),
				callback: function (r) {
					if (!r.message) return;
					var d = r.message;
					var recon_status = d.recon_api_available
						? '<span style="color:green">✔ Available</span>'
						: '<span style="color:red">✘ Not enabled (404)</span>';
					var html = `
						<table class="table table-bordered table-sm" style="font-size:13px">
							<tr><td><b>Recon/Combined API</b></td><td>${recon_status}</td></tr>
							<tr><td><b>Total settlements</b></td><td>${d.total_settlements}</td></tr>
							<tr><td><b>Razorpay pay_xxx IDs in settlements</b></td><td>${d.total_razorpay_payment_ids}</td></tr>
							<tr><td><b>FLE Payment Log total records</b></td><td>${d.total_fle_payment_log_records}</td></tr>
							<tr><td><b>FLE rows with NULL transaction_id</b></td><td>${d.fle_rows_with_null_tid}</td></tr>
							<tr style="background:#d4edda"><td><b>Matched (found in FLE log)</b></td><td>${d.matched_with_fle_log}</td></tr>
							<tr style="background:#f8d7da"><td><b>Unmatched (no FLE log entry)</b></td><td>${d.unmatched_no_fle_log}</td></tr>
							<tr style="background:#fff3cd"><td><b>Matched but name blank</b></td><td>${d.matched_but_blank_name}</td></tr>
						</table>
						${d.sample_unmatched_ids && d.sample_unmatched_ids.length
							? "<b>Sample unmatched pay_xxx IDs:</b><br>" + d.sample_unmatched_ids.join("<br>")
							: ""}
						${d.sample_blank_name_ids && d.sample_blank_name_ids.length
							? "<br><b>Sample matched but blank name:</b><br>" + d.sample_blank_name_ids.join("<br>")
							: ""}
					`;
					frappe.msgprint({ title: __("Diagnosis Result"), message: html, indicator: "blue", wide: true });
				},
			});
		}, __("Actions"));

		// ── Fix Contact Names ─────────────────────────────────────────────
		report.page.add_inner_button(__("Fix Contact Names"), function () {
			frappe.call({
				method: "slcm.api.sync_settlements.backfill_contact_names",
				freeze: true,
				freeze_message: __("✏️  Backfilling student names and emails into FLE Payment Log… Please wait."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint({ title: __("Done"), message: r.message, indicator: "green" });
						frappe.query_report.refresh();
					}
				},
			});
		}, __("Actions"));

		// ── Sync Settlements ──────────────────────────────────────────────
		report.page.add_inner_button(__("Sync Settlements"), function () {
			frappe.confirm(
				__("We will securely fetch your latest settlement data directly from Razorpay and update the FLE Payment Log with accurate UTR numbers, gateway fees, and net amounts. No payment data will be modified — this is a read and sync operation only. Ready to proceed?"),
				function () {
					frappe.call({
						method: "slcm.api.sync_settlements.run_sync",
						freeze: true,
						freeze_message: __("⚡  Securely connecting to Razorpay and syncing your settlement records… Your data is safe. This will only take a moment — please keep this tab open."),
						callback: function (r) {
							if (r.message) {
								frappe.msgprint({ title: __("Sync Complete"), message: r.message, indicator: "green" });
								frappe.query_report.refresh();
							}
						},
					});
				}
			);
		}, __("Actions"));
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
				if (from && to && frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
					frappe.msgprint({
						title: __("Invalid Date Range"),
						message: __("From Date cannot be after To Date."),
						indicator: "orange",
					});
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
				if (from && to && frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
					frappe.msgprint({
						title: __("Invalid Date Range"),
						message: __("To Date cannot be before From Date."),
						indicator: "orange",
					});
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
		// ── Row 5: Missing data filters ───────────────────────────────────
		{
			fieldname: "missing_data",
			label: __("Show Records Where"),
			fieldtype: "Select",
			options: "\nContact Name is Blank\nContact Name is Filled\nStudent ID is Blank\nStudent ID is Filled\nPayment Method is Blank\nPayment Method is Filled",
			reqd: 0,
		},
	],
};
