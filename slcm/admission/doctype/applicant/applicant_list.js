// Copyright (c) 2026, TFSS and contributors

/** ZIP is ready: confirm + Download (avoids popup blockers from async window.open). */
function slcm_applicant_bulk_zip_download_dialog(file_url, stats) {
	if (!file_url) {
		return;
	}
	const fullUrl = frappe.urllib.get_full_url(file_url);
	let body = "<p>" + __("Your ZIP archive is ready.") + "</p>";
	if (stats && stats.success != null) {
		body =
			"<p>" + __("Added {0} application form(s) to the ZIP.", [stats.success]) + "</p>";
		if (stats.from_cache != null && stats.generated_live != null) {
			body +=
				'<p class="text-muted small">' +
				__("{0} from stored PDF, {1} generated live.", [stats.from_cache, stats.generated_live]) +
				"</p>";
		}
	}
	body +=
		'<p class="text-muted small">' +
		__("Click Download to open the file in a new tab (or save it). If nothing happens, check the browser popup blocker.") +
		"</p>";
	frappe.msgprint({
		title: __("Application forms ZIP ready"),
		message: body,
		indicator: "green",
		primary_action: {
			label: __("Download"),
			action() {
				frappe.hide_msgprint();
				window.open(fullUrl, "_blank");
			},
		},
	});
}

frappe.listview_settings['Applicant'] = {
	onload: function (listview) {
		frappe.realtime.on("bulk_convert_to_student_progress", function (data) {
			if (frappe.get_route_str() === "List/Applicant") {
				frappe.show_progress(
					__("Converting to Student"),
					data.progress,
					data.total,
					data.message || ""
				);
			}
		});
		frappe.realtime.on("bulk_convert_to_student_done", function (data) {
			if (frappe.get_route_str() !== "List/Applicant") {
				return;
			}
			frappe.hide_progress();
			const s = data.success != null ? data.success : 0;
			const e = data.errors != null ? data.errors : 0;
			frappe.msgprint({
				title: __("Bulk convert to Student"),
				message: __("Finished: {0} converted successfully, {1} failed.", [s, e]),
				indicator: e ? "orange" : "green",
				primary_action: {
					label: __("Open Student Master"),
					action(values, dialog) {
						dialog.hide();
						frappe.set_route("List", "Student Master");
					},
				},
			});
			listview.refresh();
		});

		frappe.realtime.on("bulk_download_progress", (data) => {
			if (frappe.get_route_str() === "List/Applicant") {
				frappe.show_progress(__("Building ZIP"), data.progress, data.total, data.message);
			}
		});
		frappe.realtime.on("bulk_download_complete", (data) => {
			if (data.doctype === "Applicant" && frappe.get_route_str() === "List/Applicant") {
				frappe.hide_progress();
				if (data.file_url) {
					slcm_applicant_bulk_zip_download_dialog(data.file_url, {
						success: data.success,
						from_cache: data.from_cache,
						generated_live: data.generated_live,
					});
				}
			}
		});

		listview.page.add_inner_button(__("Convert to Student"), function () {
			new frappe.ui.form.MultiSelectDialog({
				doctype: "Applicant",
				target: listview,
				title: __("Select Applicants (Fee Paid only)"),
				primary_action_label: __("Convert to Student"),
				add_filters_group: 1,
				get_query: function () {
					return {
						filters: {
							application_status: "Fee Paid",
						},
					};
				},
				columns: ["name", "candidate_name", "program", "application_status", "campus"],
				setters: {
					candidate_name: "",
					program: "",
				},
				action: function (selections) {
					if (!selections || selections.length === 0) {
						frappe.msgprint(__("Please select at least one applicant."));
						return;
					}
					this.dialog.hide();
					frappe.dom.freeze(__("Processing..."));
					frappe.call({
						method: "slcm.admission.doctype.applicant.applicant.bulk_convert_applicants_to_student",
						args: { applicants: selections },
						callback: function (r) {
							frappe.dom.unfreeze();
							if (r.exc) {
								frappe.msgprint({ title: __("Error"), indicator: "red", message: r.exc });
								listview.refresh();
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
								let body = msg.message;
								if (msg.skipped && msg.skipped.length) {
									body +=
										'<div style="max-height:200px;overflow-y:auto;font-size:11px;margin-top:10px;">';
									msg.skipped.forEach(function (row) {
										const label = frappe.utils.escape_html(row.applicant || row.assignment || "");
										const reason = frappe.utils.escape_html(row.reason || row.error || "");
										body += "<p><b>" + label + ":</b> " + reason + "</p>";
									});
									body += "</div>";
								}
								frappe.msgprint({
									title: __("Cannot convert"),
									message: body,
									indicator: "orange",
								});
								listview.refresh();
								return;
							}
							const success_count = (msg.success || []).length;
							const error_count = (msg.errors || []).length;
							let message = __("Successfully converted {0} applicant(s) to students.", [success_count]);
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
									const label = frappe.utils.escape_html(row.applicant || row.assignment || "");
									const reason = frappe.utils.escape_html(row.reason || row.error || "");
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
										frappe.utils.escape_html(err.assignment || "") +
										":</b> " +
										frappe.utils.escape_html(err.error || "") +
										"</p>";
								});
								message += "</div>";
							}
							frappe.msgprint({
								title: __("Convert to Student — report"),
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
	},
	refresh: function (listview) {
		// Bulk ZIP: server zips cached Application Form PDFs when present; missing PDFs are rendered then.
		// Draft applications are never included (even if list filters would match them).
		listview.page.add_inner_button(__("Bulk Download Forms"), function () {
			// Safer way to get filter values
			const get_val = (fieldname) => {
				if (listview.filter_area && listview.filter_area.get_filter_value) {
					return listview.filter_area.get_filter_value(fieldname);
				}
				return null;
			};

			let d = new frappe.ui.Dialog({
				title: __("Bulk Download Application Forms"),
				fields: [
					{
						fieldname: "bulk_download_info",
						fieldtype: "HTML",
						options:
							"<p class='text-muted small' style='margin-bottom:12px'>" +
							__("Draft applications are excluded. Submitted applications use the stored Application Form PDF when available (faster); otherwise the selected print format is used to generate a PDF.") +
							"</p>",
					},
					{ label: __("Campus"), fieldname: "campus", fieldtype: "Link", options: "Campus", default: get_val("campus") },
					{ label: __("Programme"), fieldname: "program", fieldtype: "Link", options: "Program", default: get_val("program") },
					{ label: __("Admission Cycle"), fieldname: "admission_cycle", fieldtype: "Link", options: "Admission Cycle", default: get_val("admission_cycle") },
					{ label: __("Academic Year"), fieldname: "academic_year", fieldtype: "Link", options: "Academic Year", default: get_val("academic_year") },
					{ label: __("Admission Year"), fieldname: "admission_year", fieldtype: "Link", options: "Admission Year", default: get_val("admission_year") },
					{ label: __("Status"), fieldname: "application_status", fieldtype: "Link", options: "Applicant Status", default: get_val("application_status") },
					{ fieldtype: "Section Break" },
					{
						label: __("Print Format"),
						fieldname: "print_format",
						fieldtype: "Link",
						options: "Print Format",
						default: "Applicant Application Form",
						get_query: () => {
							return { filters: { doc_type: "Applicant" } };
						},
					},
				],
				primary_action_label: __("Generate ZIP"),
				primary_action(values) {
					d.hide();

					frappe.dom.freeze(__("Preparing Bulk Download..."));

					frappe.call({
						method: "slcm.admission.doctype.applicant.applicant.get_bulk_applications_zip",
						args: values,
						callback: function (r) {
							frappe.dom.unfreeze();
							if (r.exc) {
								return;
							}
							if (r.message && r.message.queued) {
								frappe.show_progress(__("Starting Download"), 0, 100, __("Preparing background task..."));
							} else if (r.message && r.message.file_url) {
								slcm_applicant_bulk_zip_download_dialog(r.message.file_url, {
									success: r.message.success,
									from_cache: r.message.from_cache,
									generated_live: r.message.generated_live,
								});
							}
						},
						error: function () {
							frappe.dom.unfreeze();
						},
					});
				},
			});
			d.show();
		});
	},
};
