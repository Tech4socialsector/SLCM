frappe.ui.form.on("Marks Import Log", {
	refresh(frm) {
		if (frm.doc.status === "Completed with Errors" || frm.doc.status === "Failed") {
			frm.add_custom_button(__("Retry Failed/Edited Rows"), function() {
				frappe.call({
					method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.retry_failed_rows",
					args: {
						import_log: frm.doc.name
					},
					callback: function(r) {
						if (!r.exc) {
							frappe.msgprint(__("Retry job queued."));
							frm.reload_doc();
						}
					}
				});
			});
		}
	}
});
