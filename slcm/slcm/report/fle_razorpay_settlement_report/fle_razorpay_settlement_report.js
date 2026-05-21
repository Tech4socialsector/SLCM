frappe.query_reports["FLE Razorpay Settlement Report"] = {
	onload: function (report) {
		// ── Export buttons ────────────────────────────────────────────────────
		report.page.add_inner_button(__("Download Excel"), function () {
			frappe.query_report.export_report("Excel");
		}, __("Export"));

		report.page.add_inner_button(__("Download CSV"), function () {
			frappe.query_report.export_report("CSV");
		}, __("Export"));

		// ── Diagnose Missing Matches button ──────────────────────────────────
		report.page.add_inner_button(__("Diagnose Missing Names"), function () {
			frappe.call({
				method: "slcm.api.sync_settlements.diagnose_missing_matches",
				freeze: true,
				freeze_message: __("Analysing settlement vs FLE Payment Log..."),
				callback: function (r) {
					if (!r.message) return;
					var d = r.message;
					var recon_status = d.recon_api_available
						? '<span style="color:green">✔ Available</span>'
						: '<span style="color:red">✘ Not enabled on this Razorpay account (404)</span>';
					var html = `
						<table class="table table-bordered table-sm" style="font-size:13px">
							<tr><td><b>Recon/Combined API</b></td><td>${recon_status}</td></tr>
							<tr><td><b>Total settlements</b></td><td>${d.total_settlements}</td></tr>
							<tr><td><b>Razorpay payment IDs (pay_xxx) in settlements</b></td><td>${d.total_razorpay_payment_ids}</td></tr>
							<tr><td><b>FLE Payment Log total records</b></td><td>${d.total_fle_payment_log_records}</td></tr>
							<tr><td><b>FLE Payment Log rows with NULL transaction_id</b></td><td>${d.fle_rows_with_null_tid}</td></tr>
							<tr style="background:#d4edda"><td><b>Matched (settlement ID found in FLE log)</b></td><td>${d.matched_with_fle_log}</td></tr>
							<tr style="background:#f8d7da"><td><b>Unmatched (no FLE log entry at all)</b></td><td>${d.unmatched_no_fle_log}</td></tr>
							<tr style="background:#fff3cd"><td><b>Matched but contact name is blank</b></td><td>${d.matched_but_blank_name}</td></tr>
						</table>
						${d.sample_unmatched_ids && d.sample_unmatched_ids.length ? "<b>Sample unmatched pay_xxx IDs (no FLE log):</b><br>" + d.sample_unmatched_ids.join("<br>") : ""}
						${d.sample_blank_name_ids && d.sample_blank_name_ids.length ? "<br><b>Sample IDs matched but name blank:</b><br>" + d.sample_blank_name_ids.join("<br>") : ""}
					`;
					frappe.msgprint({ title: __("Diagnosis Result"), message: html, indicator: "blue", wide: true });
				},
			});
		}, __("Actions"));

		// ── Backfill Contact Names button ─────────────────────────────────────
		// Fixes existing FLE Payment Log rows where full_name is blank
		report.page.add_inner_button(__("Fix Contact Names"), function () {
			frappe.call({
				method: "slcm.api.sync_settlements.backfill_contact_names",
				freeze: true,
				freeze_message: __("Backfilling contact names from FLE records..."),
				callback: function (r) {
					if (r.message) {
						frappe.msgprint({ title: __("Done"), message: r.message, indicator: "green" });
						frappe.query_report.refresh();
					}
				},
			});
		}, __("Actions"));

		// ── Sync Settlements button ───────────────────────────────────────────
		// Triggers a full re-sync of past Razorpay settlements into FLE Payment Log
		report.page.add_inner_button(__("Sync Settlements"), function () {
			frappe.confirm(
				__("This will sync all past Razorpay settlements into the FLE Payment Log. This may take a minute. Continue?"),
				function () {
					frappe.show_progress(__("Syncing Settlements"), 0, 100, __("Calling Razorpay API..."));
					frappe.call({
						method: "slcm.api.sync_settlements.run_sync",
						freeze: true,
						freeze_message: __("Syncing settlements from Razorpay..."),
						callback: function (r) {
							frappe.hide_progress();
							if (r.message) {
								frappe.msgprint({
									title: __("Sync Complete"),
									message: r.message,
									indicator: "green",
								});
								frappe.query_report.refresh();
							}
						},
						error: function (r) {
							frappe.hide_progress();
							frappe.msgprint({
								title: __("Sync Failed"),
								message: __("Could not sync settlements. Check the error log for details."),
								indicator: "red",
							});
						},
					});
				}
			);
		}, __("Actions"));
	},

	before_submit: function (filters) {
		// Guard: from_date must not be after to_date
		var from = filters.from_date;
		var to   = filters.to_date;
		if (from && to && frappe.datetime.str_to_obj(from) > frappe.datetime.str_to_obj(to)) {
			frappe.msgprint({
				title: __("Invalid Date Range"),
				message: __("From Date cannot be after To Date. Please correct your filters."),
				indicator: "red",
			});
			return false;
		}
	},

	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 0,
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
			reqd: 0,
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
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			// Values sent to Python — normalised to lowercase in Python for comparison
			options: "\nSettled\nPending",
			reqd: 0,
		},
	],
};
