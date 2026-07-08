// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("RFID SQL Agent Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "slcm.slcm.rfid_sql_agent.poller.test_connection",
				freeze: true,
				freeze_message: __("Testing connection..."),
				callback(r) {
					if (!r.message) return;
					if (r.message.success) {
						frappe.msgprint({ message: r.message.message, indicator: "green", title: __("Success") });
					} else {
						frappe.msgprint({ message: r.message.message, indicator: "red", title: __("Failed") });
					}
				},
			});
		});

		frm.add_custom_button(__("Run Now"), () => {
			frappe.call({
				method: "slcm.slcm.rfid_sql_agent.poller.poll_now",
				freeze: true,
				freeze_message: __("Polling..."),
				callback(r) {
					if (!r.message) return;
					frappe.msgprint({
						message: r.message.message,
						indicator: r.message.success ? "green" : "red",
						title: r.message.success ? __("Done") : __("Failed"),
					});
					frm.reload_doc();
				},
			});
		});
	},
});
