frappe.ui.form.on("Quota Policy", {
    refresh: function(frm) {
        if (frm.doc.is_legal_mandate && frm.doc.docstatus === 1) {
            frm.dashboard.set_headline(
                '<span style="color:red;font-weight:bold;">🔒 Legally Mandated — Permanently Locked</span>'
            );
        }
        if (!frm.is_new()) {
            frm.add_custom_button("View Seat Distribution", function() {
                frappe.set_route("List", "Campus Seat Matrix");
            });
        }
    }
});
