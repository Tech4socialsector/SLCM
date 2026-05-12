frappe.ui.form.on("Parent Login Invite Tool", {
    get_students_btn(frm) {
        frappe.dom.freeze("Fetching students…");
        frm.call("get_students")
            .then(r => {
                frappe.dom.unfreeze();
                const count = r.message || 0;
                frappe.show_alert({
                    message: `${count} parent record(s) loaded.`,
                    indicator: "blue",
                });
                frm.refresh();
            })
            .catch(() => frappe.dom.unfreeze());
    },

    send_invites_btn(frm) {
        const pending = (frm.doc.student_list || []).filter(r => r.invite_status === "Pending");
        if (!pending.length) {
            frappe.msgprint({
                title: __("Nothing to Send"),
                message: __("There are no pending invites. All parents either already have accounts or have no email address recorded."),
                indicator: "orange",
            });
            return;
        }

        frappe.confirm(
            `Send login invites to <strong>${pending.length}</strong> parent(s)?`,
            () => {
                frappe.dom.freeze("Sending invites…");
                frm.call("send_invites")
                    .then(r => {
                        frappe.dom.unfreeze();
                        const { invited, failed, skipped } = r.message || {};
                        frappe.msgprint({
                            title: __("Invites Sent"),
                            message: `
                                <b>${invited}</b> invite(s) sent successfully.<br>
                                ${failed ? `<span style="color:#dc2626"><b>${failed}</b> failed — check Error Log.</span><br>` : ""}
                                ${skipped ? `<b>${skipped}</b> skipped (already have accounts or no email).` : ""}
                            `,
                            indicator: failed ? "orange" : "green",
                        });
                        frm.refresh();
                    })
                    .catch(() => frappe.dom.unfreeze());
            }
        );
    },
});
