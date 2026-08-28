// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Transcript Request", {
	refresh(frm) {
		if (frm.is_new()) return;

		const pending_states = ["Submitted", "Under Review", "Approved"];
		if (!pending_states.includes(frm.doc.status)) return;

		frm.add_custom_button(__("Approve & Generate"), () => {
			frappe.confirm(
				__("Generate the transcript for this request now?"),
				() => {
					frappe.call({
						method: "slcm.slcm.page.transcript_management_page.transcript_management_page.approve_request",
						args: { request_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Generating transcript..."),
						callback: (r) => {
							if (!r.message) return;
							if (r.message.success) {
								frappe.show_alert({
									message: __("Request status: {0}", [r.message.status]),
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					});
				}
			);
		}).addClass("btn-primary");

		frm.add_custom_button(__("Reject"), () => {
			frappe.prompt(
				{
					fieldname: "rejection_reason",
					label: __("Rejection Reason"),
					fieldtype: "Small Text",
					reqd: 1,
				},
				(values) => {
					frappe.call({
						method: "slcm.slcm.page.transcript_management_page.transcript_management_page.reject_request",
						args: {
							request_name: frm.doc.name,
							rejection_reason: values.rejection_reason,
						},
						freeze: true,
						callback: (r) => {
							if (r.message && r.message.success) {
								frappe.show_alert({ message: __("Request rejected"), indicator: "orange" });
								frm.reload_doc();
							}
						},
					});
				},
				__("Reject Request")
			);
		});
	},
});
