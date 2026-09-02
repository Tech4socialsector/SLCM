frappe.listview_settings['PACE Applicant Fee Assignment'] = {
	refresh: function(listview) {
		listview.page.add_inner_button(__("Convert to Student"), function () {
			frappe.model.with_doctype('PACE Applicant Fee Assignment', function() {
				new frappe.ui.form.MultiSelectDialog({
					doctype: "PACE Applicant Fee Assignment",
					target: listview,
					title: __("Select Fee Assignments (Paid only)"),
					primary_action_label: __("Convert to Student"),
					add_filters_group: 1,
					get_query: function () {
						return {
							filters: {
								status: "Paid",
								fee_type: "Course Fee"
							},
						};
					},
					columns: ["name", "applicant_name", "program", "status", "academic_year"],
					setters: {
						applicant_name: "",
						program: "",
					},
					action: function (selections) {
						if (!selections || selections.length === 0) {
							frappe.msgprint(__("Please select at least one assignment."));
							return;
						}
						this.dialog.hide();
						frappe.dom.freeze(__("Processing..."));
						frappe.call({
							method: "slcm.pace.api.service.pace_to_student.bulk_convert_pace_fee_assignments_to_student",
							args: { assignments: selections },
							callback: function (r) {
								frappe.dom.unfreeze();
								if (r.exc) {
									frappe.msgprint({ title: __("Error"), indicator: "red", message: r.exc });
									listview.refresh();
									return;
								}
								const msg = r.message;
								
								const success_count = (msg.success || []).length;
								const error_count = (msg.errors || []).length;
								const skipped_count = (msg.skipped || []).length;
								
								let message = `
									<div style="padding: 10px;">
										<div style="display: flex; gap: 15px; margin-bottom: 20px;">
											<div style="flex: 1; padding: 12px; background: #f0fff4; border: 1px solid #c6f6d5; border-radius: 8px; text-align: center;">
												<h3 style="margin: 0; color: #2f855a;">${success_count}</h3>
												<div style="font-size: 11px; color: #38a169; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Successful')}</div>
											</div>
											<div style="flex: 1; padding: 12px; background: #fef9c3; border: 1px solid #fef08a; border-radius: 8px; text-align: center;">
												<h3 style="margin: 0; color: #a16207;">${skipped_count}</h3>
												<div style="font-size: 11px; color: #ca8a04; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Skipped')}</div>
											</div>
											<div style="flex: 1; padding: 12px; background: ${error_count > 0 ? '#fff5f5' : '#f7fafc'}; border: 1px solid ${error_count > 0 ? '#fed7d7' : '#edf2f7'}; border-radius: 8px; text-align: center;">
												<h3 style="margin: 0; color: ${error_count > 0 ? '#c53030' : '#718096'};">${error_count}</h3>
												<div style="font-size: 11px; color: ${error_count > 0 ? '#e53e3e' : '#a0aec0'}; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Failed')}</div>
											</div>
										</div>
								`;

								if (skipped_count > 0) {
									message += `
										<div style="margin-bottom: 8px; font-weight: 600; color: #4a5568;">${__('Skipped Candidates (Already converted or missing requirements):')}</div>
										<div style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 15px;">
											<table class="table table-bordered table-condensed" style="margin:0; font-size: 12px; background: #fff;">
												<thead style="background: #f8fafc;">
													<tr>
														<th style="width: 35%;">${__('Applicant')}</th>
														<th>${__('Reason')}</th>
													</tr>
												</thead>
												<tbody>
													${(msg.skipped || []).map(row => `
														<tr>
															<td style="font-weight: 600;">${frappe.utils.escape_html(row.applicant || row.assignment || "")}</td>
															<td style="color: #ca8a04; word-break: break-word;">${frappe.utils.escape_html(row.reason || row.error || "")}</td>
														</tr>
													`).join('')}
												</tbody>
											</table>
										</div>
									`;
								}
								
								if (error_count > 0) {
									message += `
										<div style="margin-bottom: 8px; font-weight: 600; color: #4a5568;">${__('Generation Failures:')}</div>
										<div style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px;">
											<table class="table table-bordered table-condensed" style="margin:0; font-size: 12px; background: #fff;">
												<thead style="background: #f8fafc;">
													<tr>
														<th style="width: 35%;">${__('Applicant')}</th>
														<th>${__('Reason for Failure')}</th>
													</tr>
												</thead>
												<tbody>
													${(msg.errors || []).map(err => `
														<tr>
															<td style="font-weight: 600;">${frappe.utils.escape_html(err.applicant || err.assignment || "")}</td>
															<td style="color: #e53e3e; word-break: break-word;">${frappe.utils.escape_html(err.error || "")}</td>
														</tr>
													`).join('')}
												</tbody>
											</table>
										</div>
									`;
								}
								message += `</div>`;

								frappe.msgprint({
									title: __("Convert to Student Report"),
									message: message,
									wide: true,
									indicator: error_count === 0 && skipped_count === 0 ? "green" : (error_count > 0 ? "red" : "orange"),
									primary_action: {
										label: __("Open Student Master"),
										action() {
											frappe.hide_msgprint();
											frappe.set_route("List", "Student Master");
										},
									},
								});
								listview.refresh();
							},
							error: function () {
								frappe.dom.unfreeze();
								listview.refresh();
							},
						});
					},
				});
			});
		});

		listview.page.add_inner_button(__("Bulk Sync Razorpay Amount"), function() {
			frappe.confirm(
				__("This will sync the Razorpay captured amount for all Paid assignments with a pending sync. Continue?"),
				function() {
					run_bulk_sync(listview);
				}
			);
		});
	}
};

function run_bulk_sync(listview) {
	let progress_dialog = new frappe.ui.Dialog({
		title: __("Bulk Sync Razorpay Amount"),
		fields: [{ fieldtype: "HTML", fieldname: "progress_area" }]
	});

	progress_dialog.fields_dict.progress_area.$wrapper.html(`
		<div class="bulk-sync-progress">
			<div class="progress">
				<div class="progress-bar" role="progressbar" style="width:0%">0%</div>
			</div>
			<p class="text-muted small" style="margin-top:8px;">${__("Starting sync...")}</p>
		</div>
	`);
	progress_dialog.show();

	let realtime_handler = function(data) {
		let pct = data.total ? Math.round((data.processed / data.total) * 100) : 0;
		progress_dialog.$wrapper.find(".progress-bar")
			.css("width", pct + "%")
			.text(pct + "%");
		progress_dialog.$wrapper.find(".text-muted").text(
			__("Processing {0} of {1} — Success: {2}, Failed: {3}",
				[data.processed, data.total, data.success_count, data.failed_count])
		);
	};

	frappe.realtime.on("pace_bulk_sync_progress", realtime_handler);

	frappe.call({
		method: "slcm.pace.doctype.pace_applicant_fee_assignment.pace_applicant_fee_assignment.bulk_sync_razorpay_amount",
		callback: function(r) {
			frappe.realtime.off("pace_bulk_sync_progress", realtime_handler);
			
			// Ensure progress bar shows 100% completion before hiding
			progress_dialog.$wrapper.find(".progress-bar").css("width", "100%").text("100%");
			progress_dialog.$wrapper.find(".text-muted").text(__("Sync complete."));

			setTimeout(() => {
				progress_dialog.hide();
				
				if (!r.message) return;
				let { total, success_count, failed_count, error_log_title } = r.message;

				let summary_html = `
					<p><b>${__("Total processed")}:</b> ${total}</p>
					<p style="color:green;"><b>${__("Successful")}:</b> ${success_count}</p>
					<p style="color:red;"><b>${__("Failed")}:</b> ${failed_count}</p>
				`;

				// Wait for progress_dialog's fade-out animation before showing the summary dialog
				// to prevent Frappe backdrop stacking issues
				setTimeout(() => {
					let summary_dialog = new frappe.ui.Dialog({
						title: __("Bulk Sync Complete"),
						fields: [{ fieldtype: "HTML", fieldname: "summary", options: summary_html }],
						primary_action_label: failed_count ? __("View Errors") : __("Close"),
						primary_action: function() {
							if (failed_count && error_log_title) {
								frappe.set_route("List", "Error Log", { title: error_log_title });
							}
							summary_dialog.hide();
						}
					});
					summary_dialog.show();
					listview.refresh();
				}, 500);
			}, 600);
		},
		error: function() {
			frappe.realtime.off("pace_bulk_sync_progress", realtime_handler);
			progress_dialog.hide();
			setTimeout(() => {
				frappe.msgprint({
					title: __("Bulk Sync Failed"),
					indicator: "red",
					message: __("The bulk sync process failed unexpectedly. Please check the Error Log.")
				});
			}, 500);
		}
	});
}
