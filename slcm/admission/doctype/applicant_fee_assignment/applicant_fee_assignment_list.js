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
					const dialog_ref = this.dialog;
					dialog_ref.hide();

					Promise.all([
						frappe.db.get_value("Email Account", { default_outgoing: 1 }, "name"),
						frappe.db.get_value("Email Template", { name: "Student Admission Confirmation" }, "name")
					]).then(results => {
						const default_account = results[0] && results[0].message ? results[0].message.name : "";
						const default_template = results[1] && results[1].message ? results[1].message.name : "";

						const d = new frappe.ui.Dialog({
							title: __("Notification Settings"),
							fields: [
								{
									label: __("Email Account"),
									fieldname: "email_account",
									fieldtype: "Link",
									options: "Email Account",
									reqd: 1,
									default: default_account
								},
								{
									label: __("Email Template"),
									fieldname: "email_template",
									fieldtype: "Link",
									options: "Email Template",
									reqd: 1,
									default: default_template
								}
							],
							primary_action_label: __("Convert"),
							primary_action: function (values) {
								d.hide();
								frappe.dom.freeze(__("Processing..."));
								frappe.call({
									method: "slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment.bulk_convert_to_student",
									args: {
										assignments: selections,
										email_template: values.email_template,
										email_account: values.email_account
									},
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
										const success_count = msg.success_count !== undefined ? msg.success_count : (msg.success || []).length;
										const error_count = msg.error_count !== undefined ? msg.error_count : (msg.errors || []).length;
										let message = __("Successfully converted {0} to students.", [success_count]);
										if (msg.skipped && msg.skipped.length) {
											message +=
												"<br><small>" +
												__("{0} row(s) were not eligible and were skipped.", [msg.skipped.length]) +
												"</small>";
										}
										if (error_count > 0) {
											message += "<br><br>" + __("{0} error(s):", [error_count]);
											message += '<div style="max-height: 200px; overflow-y: auto; font-size: 11px; margin-top: 8px; background: #fff5f5; border: 1px solid #ffcccc; padding: 10px; border-radius: 4px;">';
											(msg.errors || []).forEach(function (err) {
												message += "<br><b>" + (err.assignment || err.applicant || "") + ":</b> " + (err.error || "");
											});
											message += "</div>";
										}
										frappe.msgprint({
											title: __("Bulk Convert to Student Report"),
											message: message,
											indicator: error_count > 0 ? "orange" : "green",
										});
										listview.refresh();
									},
									error: function () {
										frappe.dom.unfreeze();
										listview.refresh();
									},
								});
							}
						});
						d.show();
					});
				},
			});
		});
	},
};
