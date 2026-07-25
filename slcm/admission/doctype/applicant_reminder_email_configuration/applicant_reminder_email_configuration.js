frappe.ui.form.on("Applicant Reminder Email Configuration", {
    refresh(frm) {
        frm.add_custom_button(__("Send Reminders Now"), function () {
            _trigger_manual_reminders(frm);
        }, __("Actions"));
    }
});

function _trigger_manual_reminders(frm) {
    // Collect which reminders are Active
    const reminder_fields = [
        "enable_not_started_reminder",
        "enable_draft_reminder",
        "enable_unpaid_fee_reminder"
    ];

    const active_reminders = reminder_fields.filter(f => frm.doc[f] === "Active");

    if (!active_reminders.length) {
        frappe.msgprint({
            title: __("No Active Reminders"),
            message: __("Please activate at least one reminder type before triggering."),
            indicator: "orange"
        });
        return;
    }

    frappe.confirm(
        __("This will immediately send reminder emails to all eligible applicants for the selected active reminder types. Do you want to continue?"),
        function () {
            // Show progress dialog
            const dialog = new frappe.ui.Dialog({
                title: __("Sending Reminder Emails..."),
                fields: [{
                    fieldtype: "HTML",
                    fieldname: "progress_area"
                }]
            });

            dialog.show();
            dialog.get_field("progress_area").$wrapper.html(
                `<div class="text-muted" style="padding: 15px 0;">
                    <i class="fa fa-spinner fa-spin"></i> &nbsp;Processing reminders, please wait&hellip;
                </div>`
            );

            frappe.realtime.on("applicant_reminder_progress", function (data) {
                if (data.title === "Applicant Reminders" && data.progress) {
                    const [done, total] = data.progress;
                    const pct = total ? Math.round((done / total) * 100) : 0;
                    dialog.get_field("progress_area").$wrapper.html(
                        `<div style="padding: 10px 0;">
                            <div class="progress" style="height:18px;">
                                <div class="progress-bar" role="progressbar"
                                     style="width:${pct}%; background-color:#920c24;">
                                    ${pct}%
                                </div>
                            </div>
                            <p class="text-muted" style="margin-top:8px;">${data.description || ""}</p>
                        </div>`
                    );
                }
            });

            frappe.call({
                method: "slcm.admission.doctype.applicant_reminder_email_configuration.applicant_reminder_email_configuration.trigger_manual_reminders",
                args: { reminders: active_reminders },
                freeze: false,
                callback(r) {
                    frappe.realtime.off("applicant_reminder_progress");

                    if (r.message && r.message.status === "success") {
                        dialog.get_field("progress_area").$wrapper.html(
                            `<div style="padding: 10px 0;">
                                <div class="progress" style="height:18px;">
                                    <div class="progress-bar progress-bar-success" role="progressbar"
                                         style="width:100%; background-color:#28a745;">
                                        100%
                                    </div>
                                </div>
                                <p class="text-success" style="margin-top:8px;"><strong><i class="fa fa-check"></i> &nbsp;Completed Successfully!</strong></p>
                            </div>`
                        );
                    }

                    setTimeout(() => {
                        dialog.hide();
                        
                        if (r.message && r.message.status === "success") {
                            const count = r.message.sent_count;
                            let msg_dialog;
                            if (count > 0) {
                                msg_dialog = frappe.msgprint({
                                    title: __("Reminders Sent"),
                                    message: __("{0} reminder email(s) have been queued successfully.", [count]),
                                    indicator: "green"
                                });
                            } else {
                                msg_dialog = frappe.msgprint({
                                    title: __("No Emails Sent"),
                                    message: r.message.message || __("All eligible recipients have already received their reminders today, or there are no eligible recipients."),
                                    indicator: "orange"
                                });
                            }
                            
                            if (msg_dialog) {
                                setTimeout(() => {
                                    msg_dialog.hide();
                                }, 3000);
                            }
                        }
                    }, 3000);
                },
                error() {
                    frappe.realtime.off("applicant_reminder_progress");
                    dialog.hide();
                    let err_dialog = frappe.msgprint({
                        title: __("Error"),
                        message: __("An error occurred while sending reminders. Please check the Error Log for details."),
                        indicator: "red"
                    });
                    if (err_dialog) {
                        setTimeout(() => {
                            err_dialog.hide();
                        }, 3000);
                    }
                }
            });
        }
    );
}
