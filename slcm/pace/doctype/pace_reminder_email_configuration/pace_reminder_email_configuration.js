frappe.ui.form.on("PACE Reminder Email Configuration", {
	refresh(frm) {
		frm.add_custom_button(__('Send Reminder Email'), () => {
			frm.events.show_manual_reminder_dialog(frm);
		}).addClass("btn-primary");
	},

	show_manual_reminder_dialog(frm) {
		let active_reminders = [];
		let field_labels = {
			"enable_application_reminder": __("Application Reminder"),
			"enable_draft_reminder": __("Draft Reminder"),
			"enable_payment_reminder": __("Payment Reminder"),
			"enable_missing_document_reminder": __("Missing Document Reminder"),
			"enable_correction_reminder": __("Correction Reminder"),
			"enable_course_fee_reminder": __("Course Fee Reminder"),
			"enable_verifier_pending_reminder": __("Verifier Pending Reminder"),
			"enable_verifier_overdue_reminder": __("Verifier Overdue Reminder")
		};

		// Collect only Active reminders from the configuration
		Object.keys(field_labels).forEach(fieldname => {
			if (frm.doc[fieldname] === "Active") {
				active_reminders.push({
					label: field_labels[fieldname],
					fieldname: fieldname,
					fieldtype: "Check",
					default: 1
				});
			}
		});

		if (active_reminders.length === 0) {
			frappe.msgprint({
				title: __("No Active Reminders"),
				message: __("There are no reminders currently set to 'Active' in the configuration."),
				indicator: "orange"
			});
			return;
		}

		let d = new frappe.ui.Dialog({
			title: __("Manually Send Reminder Emails"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "help_text",
					options: `<p class="text-muted small">${__("Select the reminders you want to trigger manually. The system will only send emails to those who have not received the same reminder today.")}</p>`
				},
				...active_reminders
			],
			primary_action_label: __("Send Reminder"),
			primary_action(values) {
				let selected_reminders = Object.keys(values).filter(k => values[k] === 1 && k !== "help_text");
				
				if (selected_reminders.length === 0) {
					frappe.msgprint(__("Please select at least one reminder to send."));
					return;
				}

				d.get_primary_btn().html(__("Sending..."));
				d.disable_primary_action();

				// Ensure any previous progress bars are closed
				frappe.hide_progress();

				// Initialize progress bar with standard title
				frappe.show_progress(__("PACE Reminders"), 0, 100, __("Starting..."));

				frappe.call({
					method: "slcm.pace.doctype.pace_reminder_email_configuration.pace_reminder_email_configuration.trigger_manual_reminders",
					args: {
						reminders: selected_reminders
					},
					callback: function(r) {
						d.hide();
						
						// Update to 100% and close immediately
						frappe.show_progress(__("PACE Reminders"), 100, 100, __("Completed"));
						
						setTimeout(() => {
							frappe.hide_progress();
							
							let data = r.message || {};
							if (data.sent_count > 0) {
								frappe.show_alert({
									message: __("Reminder email(s) sent successfully."),
									indicator: "green"
								}, 5);
							} else {
								frappe.show_alert({
									message: data.message || __("No reminder emails were sent. All eligible recipients have already received their reminders today."),
									indicator: "orange"
								}, 5);
							}
						}, 200);
					},
					error: function(r) {
						frappe.hide_progress();
						d.get_primary_btn().html(__("Send Reminder"));
						d.enable_primary_action();
					}
				});
			}
		});

		d.show();
	}
});
