frappe.ui.form.on("Parent Login Invite Tool", {
    onload(frm) {
        frm.set_query("batch", () => {
            const filters = {};
            if (frm.doc.academic_year) filters.academic_year = frm.doc.academic_year;
            return { filters };
        });
    },

    get_students_btn(frm) {
        const fetch_students = () => {
            frappe.dom.freeze("Fetching students…");
            frm.call("get_students")
                .then(r => {
                    const count = r.message || 0;
                    frappe.show_alert({
                        message: `${count} parent record(s) loaded.`,
                        indicator: "blue",
                    });
                    return frm.reload_doc();
                })
                .then(() => frappe.dom.unfreeze())
                .catch(() => frappe.dom.unfreeze());
        };

        if (frm.is_new() || frm.is_dirty()) {
            frm.save().then(fetch_students);
        } else {
            fetch_students();
        }
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
                        return frm.reload_doc();
                    })
                    .then(() => frappe.dom.unfreeze())
                    .catch(() => frappe.dom.unfreeze());
            }
        );
    },
});
