frappe.ui.form.on("ID Card Generation Tool", {
	refresh: function (frm) {
		frm.disable_save();

		frm.page.set_primary_action(__("Generate Cards"), () => {
			// Client-side guards
			if (!frm.doc.id_card_template) {
				frappe.msgprint({
					title: __("Missing Template"),
					message: __("Please select an ID Card Template before generating cards."),
					indicator: "orange",
				});
				return;
			}

			const rows = frm.doc.student_list || [];
			if (rows.length === 0) {
				frappe.msgprint({
					title: __("No Students"),
					message: __(
						'No students in the list. Please click <b>"Get Students"</b> to load students ' +
						"using filters, or add students manually."
					),
					indicator: "orange",
				});
				return;
			}

			const pendingRows = rows.filter((r) => r.status !== "Already Exists");
			if (pendingRows.length === 0) {
				frappe.msgprint({
					title: __("Nothing to Generate"),
					message: __(
						"All students in the list already have an active ID card. No new cards to generate."
					),
					indicator: "blue",
				});
				return;
			}

			frappe.confirm(
				__("Generate ID cards for {0} student(s)?", [pendingRows.length]),
				() => {
					frm.call("generate_cards").then(() => {
						frm.reload_doc();
					});
				}
			);
		});

		frm.add_custom_button(__("Reset Filters"), function () {
			frappe.confirm(
				__("Reset all filters and clear the student list?"),
				function () {
					frm.call("reset_filters").then(() => {
						frm.reload_doc();
						frappe.show_alert({ message: __("Filters reset."), indicator: "blue" });
					});
				}
			);
		});

		frm.add_custom_button(__("Get Students"), function () {
			const hasFilter = frm.doc.academic_year || frm.doc.program || frm.doc.batch;
			if (!hasFilter) {
				frappe.msgprint({
					title: __("No Filters Selected"),
					message: __(
						"Please select at least one filter — <b>Academic Year</b>, <b>Program</b>, " +
						"or <b>Batch</b> — before fetching students."
					),
					indicator: "orange",
				});
				return;
			}

			frm.call("get_students").then(() => {
				frm.refresh_field("student_list");
				const count = (frm.doc.student_list || []).length;
				if (count === 0) {
					frappe.msgprint({
						title: __("No Students Found"),
						message: __(
							"No active students found matching the selected filters. " +
							"Please adjust your filters and try again."
						),
						indicator: "orange",
					});
				} else {
					frappe.show_alert({
						message: __("{0} student(s) loaded.", [count]),
						indicator: "green",
					});
				}
			});
		});

		if (frm.doc.student_list && frm.doc.student_list.length > 0) {
			frm.add_custom_button(__("Download ZIP"), function () {
				frm.call("download_zip").then((r) => {
					if (r.message) {
						window.open(r.message, "_blank");
					}
				});
			});

			frm.add_custom_button(__("Download Print Layout"), function () {
				frm.call("generate_print_layout").then((r) => {
					if (r.message) {
						window.open(r.message, "_blank");
					}
				});
			});
		}
	},

	id_card_template: function (frm) {
		if (frm.doc.id_card_template && frm.doc.student_list && frm.doc.student_list.length > 0) {
			// Trigger preview update
			frm.trigger("render_preview");
		}
	},

	render_preview: function (frm) {
		if (!frm.doc.id_card_template) return;

		// Take first student for preview
		let student = null;
		if (frm.doc.student_list && frm.doc.student_list.length > 0) {
			student = frm.doc.student_list[0].student;
		} else {
			return;
		}

		frappe.call({
			method: "slcm.slcm.doctype.id_card_generation_tool.id_card_generation_tool.get_preview_html",
			args: {
				template_name: frm.doc.id_card_template,
				student: student,
			},
			callback: function (r) {
				if (r.message) {
					frm.set_df_property("preview_section", "hidden", 0);
					$(frm.fields_dict["preview_html"].wrapper).html(r.message);
				}
			},
		});
	},
});
