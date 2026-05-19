frappe.listview_settings['PACE Application'] = {
	onload: function(listview) {
		// Add to the 'Actions' menu that appears when records are selected
		listview.page.add_actions_menu_item(__('Bulk Records Download'), function() {
			const selected_items = listview.get_checked_items();
			
			if (selected_items.length === 0) {
				frappe.msgprint(__('Please select at least one record to download.'));
				return;
			}

			const names = selected_items.map(item => item.name);
			
			// Show a progress indicator
			frappe.show_alert({
				message: __('Preparing Records...'),
				indicator: 'blue'
			});

			frappe.call({
				method: 'slcm.pace.doctype.pace_application.pace_application.bulk_download_all_records',
				args: {
					names: names
				},
				freeze: true,
				freeze_message: __('Generating ZIP Archive...'),
				callback: function(r) {
					if (r.message) {
						const file_url = r.message;
						const link = document.createElement('a');
						link.href = file_url;
						link.download = file_url.split('/').pop();
						document.body.appendChild(link);
						link.click();
						document.body.removeChild(link);
						
						frappe.show_alert({
							message: __('Download started successfully.'),
							indicator: 'green'
						});
					}
				}
			});
		});
	},
	refresh: function(listview) {
		listview.page.add_inner_button(__("Convert to Student"), function () {
			frappe.model.with_doctype('PACE Application', function() {
				new frappe.ui.form.MultiSelectDialog({
					doctype: "PACE Application",
					target: listview,
					title: __("Select PACE Applications (Fee Paid only)"),
					primary_action_label: __("Convert to Student"),
					add_filters_group: 1,
					get_query: function () {
						return {
							filters: {
								status: "Fee Paid",
							},
						};
					},
					columns: ["name", "applicant_name", "programme", "status", "academic_year"],
					setters: {
						applicant_name: "",
						programme: "",
					},
					action: function (selections) {
						if (!selections || selections.length === 0) {
							frappe.msgprint(__("Please select at least one application."));
							return;
						}
						this.dialog.hide();
						frappe.dom.freeze(__("Processing..."));
						frappe.call({
							method: "slcm.pace.api.service.pace_to_student.bulk_convert_pace_to_student",
							args: { pace_apps: selections },
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
								let message = __("Successfully converted {0} application(s) to students.", [success_count]);
								
								if (error_count > 0) {
									message += "<br>" + __("{0} conversion(s) failed.", [error_count]);
								}
								
								if (msg.skipped && msg.skipped.length) {
									message +=
										"<br><small>" +
										__("{0} row(s) were skipped.", [msg.skipped.length]) +
										"</small>";
									message +=
										'<div style="max-height:180px;overflow-y:auto;font-size:11px;margin-top:8px;background:#f8fafc;border:1px solid #e2e8f0;padding:10px;border-radius:4px;">';
									msg.skipped.forEach(function (row) {
										const label = frappe.utils.escape_html(row.applicant || "");
										const reason = frappe.utils.escape_html(row.reason || "");
										message += "<p><b>" + label + ":</b> " + reason + "</p>";
									});
									message += "</div>";
								}
								
								if (error_count > 0) {
									message +=
										'<div style="max-height:200px;overflow-y:auto;font-size:11px;margin-top:8px;background:#fff5f5;border:1px solid #ffcccc;padding:10px;border-radius:4px;">';
									(msg.errors || []).forEach(function (err) {
										message +=
											"<p><b>" +
											frappe.utils.escape_html(err.applicant || "") +
											":</b> " +
											frappe.utils.escape_html(err.error || "") +
											"</p>";
									});
									message += "</div>";
								}
								
								frappe.msgprint({
									title: __("Convert to Student — Report"),
									message: message,
									indicator: error_count > 0 ? "orange" : "green",
									primary_action: {
										label: __("Open Student Master"),
										action(values, dialog) {
											dialog.hide();
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
	}
};
