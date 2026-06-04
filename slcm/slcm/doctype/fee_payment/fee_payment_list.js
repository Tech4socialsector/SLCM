frappe.listview_settings["Fee Payment"] = {
	onload(listview) {
		const btn = listview.page.add_inner_button(__("View Fee Demands"), () => {
			const selected = listview.get_checked_items();
			if (!selected.length) {
				frappe.msgprint(__("Please select at least one Fee Payment record."));
				return;
			}

			const student_ids = [...new Set(selected.map((r) => r.student).filter(Boolean))];

			if (!student_ids.length) {
				frappe.msgprint(__("No student linked to the selected records."));
				return;
			}

			if (student_ids.length === 1) {
				// Single student — open filtered list directly
				frappe.set_route("List", "Fee Demand", { student: student_ids[0] });
				return;
			}

			// Multiple students — fetch all demands and show a combined dialog
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Fee Demand",
					filters: [["student", "in", student_ids]],
					fields: [
						"name", "student", "student_name", "description",
						"fee_component", "demand_type", "academic_year",
						"due_date", "status", "original_amount", "paid_amount", "outstanding_amount",
					],
					order_by: "student asc, due_date asc",
					limit: 500,
				},
				callback(r) {
					if (!r.message || !r.message.length) {
						frappe.msgprint({
							title: __("Fee Demands"),
							message: __("No fee demands found for the selected students."),
							indicator: "orange",
						});
						return;
					}

					const rows = r.message.map((d) => {
						const status_color = {
							"Pending": "#f59e0b",
							"Partially Paid": "#3b82f6",
							"Paid": "#10b981",
							"Overdue": "#ef4444",
							"Waived": "#8b5cf6",
							"Cancelled": "#6b7280",
						}[d.status] || "#6b7280";

						return `<tr>
							<td><a href="/desk#Form/Fee Demand/${d.name}" target="_blank">${d.name}</a></td>
							<td>${d.student_name || d.student}</td>
							<td>${d.description || d.fee_component || "-"}</td>
							<td>${d.demand_type || "-"}</td>
							<td>${d.academic_year || "-"}</td>
							<td>${frappe.datetime.str_to_user(d.due_date) || "-"}</td>
							<td style="text-align:right">₹${format_number(d.original_amount)}</td>
							<td style="text-align:right">₹${format_number(d.paid_amount)}</td>
							<td style="text-align:right; font-weight:bold">₹${format_number(d.outstanding_amount)}</td>
							<td><span style="color:${status_color}; font-weight:600">${d.status}</span></td>
						</tr>`;
					}).join("");

					const total_outstanding = r.message.reduce((s, d) => s + (d.outstanding_amount || 0), 0);
					const total_paid = r.message.reduce((s, d) => s + (d.paid_amount || 0), 0);
					const total_original = r.message.reduce((s, d) => s + (d.original_amount || 0), 0);

					const html = `
						<div style="margin-bottom:12px; font-size:13px; color:#555">
							Showing demands for <strong>${student_ids.length} students</strong> — ${r.message.length} total demands
						</div>
						<div style="overflow-x:auto">
						<table class="table table-bordered table-condensed" style="font-size:12px; width:100%">
							<thead style="background:#f5f5f5">
								<tr>
									<th>Demand ID</th>
									<th>Student</th>
									<th>Description</th>
									<th>Type</th>
									<th>Academic Year</th>
									<th>Due Date</th>
									<th style="text-align:right">Original</th>
									<th style="text-align:right">Paid</th>
									<th style="text-align:right">Outstanding</th>
									<th>Status</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
							<tfoot style="background:#f9f9f9; font-weight:bold">
								<tr>
									<td colspan="6">Total (${r.message.length} demands)</td>
									<td style="text-align:right">₹${format_number(total_original)}</td>
									<td style="text-align:right">₹${format_number(total_paid)}</td>
									<td style="text-align:right">₹${format_number(total_outstanding)}</td>
									<td></td>
								</tr>
							</tfoot>
						</table>
						</div>`;

					const dialog = new frappe.ui.Dialog({
						title: __("Fee Demands — {0} Students", [student_ids.length]),
						fields: [{ fieldtype: "HTML", fieldname: "demands_html" }],
						size: "extra-large",
						primary_action_label: __("Open Fee Demand List"),
						primary_action() {
							frappe.set_route("List", "Fee Demand", { student: ["in", student_ids] });
							dialog.hide();
						},
						secondary_action_label: __("Close"),
						secondary_action() { dialog.hide(); },
					});
					dialog.show();
					dialog.fields_dict.demands_html.$wrapper.html(html);
				},
			});
		});
		btn.css({
			"background-color": "#1f2937",
			"color": "#f9fafb",
			"border-color": "#1f2937",
		}).hover(
			function() { $(this).css({ "background-color": "#111827", "border-color": "#111827" }); },
			function() { $(this).css({ "background-color": "#1f2937", "border-color": "#1f2937" }); }
		);
	},
};
