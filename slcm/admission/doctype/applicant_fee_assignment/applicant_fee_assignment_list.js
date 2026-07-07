// Copyright (c) 2026, TFSS and contributors
// List view: "Bulk Convert to Student" opens MultiSelectDialog to find and select assignments (like Seat Allocation → Generate Offer Letters).

frappe.listview_settings['Applicant Fee Assignment'] = {
	onload: function (listview) {
		frappe.realtime.on("bulk_convert_to_student_progress", function (data) {
			if (frappe.get_route_str() === "List/Applicant Fee Assignment") {
				frappe.show_progress(__("Converting to Student"), data.progress, data.total, data.message || "");
			}
		});
		frappe.realtime.on("bulk_convert_to_student_done", function (data) {
			if (frappe.get_route_str() === "List/Applicant Fee Assignment") {
				frappe.hide_progress();
				const s = data.success != null ? data.success : 0;
				const e = data.errors != null ? data.errors : 0;
				frappe.show_alert({
					message: __("Student conversion finished: {0} succeeded, {1} failed.", [s, e]),
					indicator: e ? "orange" : "green",
				});
				listview.refresh();
			}
		});

		listview.page.add_inner_button(__("Convert to Student"), function () {
			new frappe.ui.form.MultiSelectDialog({
				doctype: "Applicant Fee Assignment",
				target: listview,
				title: __("Select Assignments to Convert to Student"),
				primary_action_label: __("Convert to Student"),
				add_filters_group: 1,
				// Eligible: submitted Admission Fee with Partially Paid or Paid only
				get_query: function () {
					return {
						filters: {
							docstatus: 1,
							fee_type: "Admission Fee",
							status: ["in", ["Partially Paid", "Paid"]],
						},
					};
				},
				columns: ["name", "applicant", "applicant_name", "program", "status"],
				setters: {
					applicant: "",
					program: "",
				},
				action: function (selections) {
					if (!selections || selections.length === 0) {
						frappe.msgprint(__("Please select at least one assignment to convert."));
						return;
					}
					this.dialog.hide();

					frappe.dom.freeze(__("Processing..."));

					frappe.call({
						method: "slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment.bulk_convert_to_student",
						args: { assignments: selections },
						callback: function (r) {
							frappe.dom.unfreeze();
							if (r.exc) {
								frappe.msgprint({ title: __("Error"), indicator: "red", message: r.exc });
								return;
							}
							const msg = r.message;
							if (msg.queued) {
								frappe.msgprint({
									title: __("Queued"),
									message: msg.message,
									indicator: "blue",
								});
								listview.refresh();
								return;
							}
							if (msg.message && !msg.success && !msg.errors) {
								frappe.msgprint({
									title: __("Cannot convert"),
									message: msg.message,
									indicator: "orange",
								});
								listview.refresh();
								return;
							}
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
													<th style="width: 35%;">${__('Assignment')}</th>
													<th>${__('Reason')}</th>
												</tr>
											</thead>
											<tbody>
												${(msg.skipped || []).map(row => `
													<tr>
														<td style="font-weight: 600;">${frappe.utils.escape_html(row.assignment || row.applicant || "")}</td>
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
													<th style="width: 35%;">${__('Assignment')}</th>
													<th>${__('Reason for Failure')}</th>
												</tr>
											</thead>
											<tbody>
												${(msg.errors || []).map(err => `
													<tr>
														<td style="font-weight: 600;">${frappe.utils.escape_html(err.assignment || err.applicant || "")}</td>
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
	},
};
