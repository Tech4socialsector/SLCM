frappe.ui.form.on("Admission Cycle", {

    refresh: function (frm) {
        // Status indicator
        const colors = { "Draft": "gray", "Active": "green", "Closed": "red" };
        frm.dashboard.set_headline_alert(
            __(frm.doc.status),
            colors[frm.doc.status] || "gray"
        );

        // Program count warning
        if (!frm.is_new()) {
            const active_programs = (frm.doc.programs || [])
                .filter(p => p.is_active).length;
            if (frm.doc.status === "Active" && active_programs === 0) {
                frm.dashboard.set_headline_alert(
                    __("No programs added. Portal will show empty."),
                    "orange"
                );
            } else if (active_programs > 0) {
                frm.dashboard.set_headline_alert(
                    __("{0} program(s) visible on portal", [active_programs]),
                    "green"
                );
            }
        }

        // Quick actions
        if (!frm.is_new()) {
            if (frm.doc.status === "Draft") {
                frm.add_custom_button(__("Activate"), function () {
                    frappe.confirm(
                        __("Activate this cycle? Only one cycle can be Active at a time."),
                        function () {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Admission Cycle",
                                    name: frm.doc.name,
                                    fieldname: "status",
                                    value: "Active"
                                },
                                callback: function () { frm.reload_doc(); }
                            });
                        }
                    );
                }, __("Actions"));
            }

            if (frm.doc.status === "Active") {
                frm.add_custom_button(__("Close Cycle"), function () {
                    frappe.confirm(
                        __("Close this cycle? No more applications will be accepted."),
                        function () {
                            frappe.call({
                                method: "frappe.client.set_value",
                                args: {
                                    doctype: "Admission Cycle",
                                    name: frm.doc.name,
                                    fieldname: "status",
                                    value: "Closed"
                                },
                                callback: function () { frm.reload_doc(); }
                            });
                        }
                    );
                }, __("Actions"));
            }

            frm.add_custom_button(__("Preview Portal"), function () {
                window.open("/desk/applicant-portal", "_blank");
            }, __("Actions"));
        }
    },

    status: function (frm) {
        if (frm.doc.status === "Active") {
            frappe.show_alert({
                message: __("Cycle activated. Programs will appear on the portal."),
                indicator: "green"
            }, 5);
        }
    }
});
