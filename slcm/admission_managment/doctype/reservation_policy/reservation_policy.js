frappe.ui.form.on("Reservation Policy", {
    refresh: function(frm) {
        if (frm.doc.is_locked) {
            frm.dashboard.set_headline(
                `<span style="color: red; font-weight: bold;">
                 Policy Locked - Legally Enforced
                </span>`
            );
            frm.disable_save();
        }
        if (frm.doc.docstatus === 0 && !frm.doc.is_locked) {
            frm.dashboard.set_headline(
                `<span style="color: orange;">
                ⚠ Submit to legally enforce this policy
                </span>`
            );
        }
    },
    mandated_percentage: function(frm) {
        if (frm.doc.mandated_percentage < 0 || frm.doc.mandated_percentage > 100) {
            frappe.msgprint({
                title: "Invalid Value",
                indicator: "red",
                message: "Percentage must be between 0 and 100"
            });
            frm.set_value("mandated_percentage", 0);
        }
    }
});