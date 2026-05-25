frappe.ui.form.on("Bulk Fee Collection", {
	refresh(frm) {
		frm.disable_save();

		if (frm.doc.status === "Draft" || frm.is_new()) {
			frm.add_custom_button(__("Fetch Students with Dues"), () => {
				if (!frm.doc.academic_year) {
					frappe.msgprint(__("Please select Academic Year first."));
					return;
				}
				frappe.show_progress(__("Fetching..."), 0, 100, __("Loading students with pending dues..."));
				frm.call("fetch_students").then(r => {
					frappe.hide_progress();
					if (r.message !== undefined) {
						frm.refresh_field("students");
						frm.refresh_field("total_students");
						if (r.message === 0) {
							frappe.show_alert({ message: __("No students with pending dues found for the selected filters."), indicator: "orange" });
						} else {
							frappe.show_alert({ message: __("{0} students loaded with pending dues.", [r.message]), indicator: "green" });
							// Auto-save to persist rows
							frm.save();
						}
					}
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Draft" && frm.doc.students && frm.doc.students.length) {
			frm.add_custom_button(__("Process Bulk Payment"), () => {
				if (!frm.doc.payment_mode) {
					frappe.msgprint(__("Please select Payment Mode before processing."));
					return;
				}
				const pending = frm.doc.students.filter(r => r.status === "Pending").length;
				frappe.confirm(
					__("This will create {0} Fee Payment(s) and Receipts. Proceed?", [pending]),
					() => {
						frappe.show_progress(__("Processing..."), 0, 100, __("Creating payments and receipts..."));
						frm.call("process_bulk_payment").then(r => {
							frappe.hide_progress();
							if (r.message) {
								const res = r.message;
								frm.reload_doc();
								frappe.msgprint({
									title: __("Bulk Payment Complete"),
									message: `
										<table class="table table-bordered" style="margin-top:8px">
											<tr><td>✅ Processed</td><td><strong>${res.processed}</strong></td></tr>
											<tr><td>❌ Failed</td><td><strong>${res.failed}</strong></td></tr>
											<tr><td>⏭ Skipped</td><td><strong>${res.skipped}</strong></td></tr>
											<tr><td>💰 Total Collected</td><td><strong>₹${format_number(res.total_collected)}</strong></td></tr>
										</table>`,
									indicator: res.failed === 0 ? "green" : "orange",
								});
							}
						}).catch(() => {
							frappe.hide_progress();
						});
					}
				);
			}).addClass("btn-success");
		}

		if (frm.doc.status && frm.doc.status !== "Draft") {
			frm.set_intro(
				`Status: <strong>${frm.doc.status}</strong> — Processed: ${frm.doc.processed_count || 0} | Failed: ${frm.doc.failed_count || 0} | Skipped: ${frm.doc.skipped_count || 0}`,
				frm.doc.status === "Completed" ? "green" : "orange"
			);
		}
	},

	academic_year(frm) {
		// Clear students table when filters change
		if (frm.doc.students && frm.doc.students.length) {
			frm.clear_table("students");
			frm.refresh_field("students");
		}
	},

	batch_year(frm) {
		if (frm.doc.students && frm.doc.students.length) {
			frm.clear_table("students");
			frm.refresh_field("students");
		}
	},
});
