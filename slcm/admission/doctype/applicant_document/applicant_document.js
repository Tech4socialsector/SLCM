frappe.ui.form.on("Applicant Document", {
    refresh: function(frm) {
        if (frm.doc.is_locked) {
            frm.dashboard.set_headline(
                `<span style="color: red; font-weight: bold;">
                🔒 Document Locked
                </span>`
            );
            frm.disable_save();
        }
        if (frm.doc.is_verified) {
            frm.dashboard.add_comment(
                `✓ Verified by ${frm.doc.verified_by} on ${frm.doc.verified_on}`,
                "green"
            );
        } else if (frm.doc.docstatus === 1) {
            frm.dashboard.add_comment(
                "⚠ Pending Verification",
                "orange"
            );
            if (frappe.user.has_role("Admission Officer") ||
                frappe.user.has_role("Admission Admin")) {
                frm.add_custom_button("Mark as Verified", function() {
                    frappe.confirm(
                        "Are you sure you want to verify this document?",
                        function() {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Applicant Document",
                                    name: frm.doc.name,
                                    fieldname: {
                                        "is_verified": 1,
                                        "verified_by": frappe.session.user,
                                        "verified_on": frappe.datetime.now_datetime()
                                    }
                                },
                                callback: function() {
                                    frm.reload_doc();
                                }
                            });
                        }
                    );
                }, "Actions");
            }
        }
        if (frm.doc.checksum) {
            frm.dashboard.add_comment(
                `SHA-256: ${frm.doc.checksum.substring(0, 20)}...`,
                "gray"
            );
        }
    },
    file: function(frm) {
        if (frm.doc.file) {
            frappe.show_alert({
                message: "File uploaded. Checksum will be generated on save.",
                indicator: "blue"
            }, 4);
        }
    }
});