frappe.ui.form.on("Admission Year", {
    refresh: function(frm) {
        if (frm.doc.is_active) {
            frm.dashboard.set_headline(
                `<span style="color: green; font-weight: bold;">
                ✓ Active Admission Year: ${frm.doc.year}
                </span>`
            );
        }
        if (!frm.is_new()) {
            frm.add_custom_button("View Admission Cycles", function() {
                frappe.set_route("List", "Admission Cycle", {
                    admission_year: frm.doc.name
                });
            });
        }
    },
    is_active: function(frm) {
        if (frm.doc.is_active) {
            frappe.db.get_value(
                "Admission Year",
                {"is_active": 1, "name": ["!=", frm.doc.name]},
                "year",
                function(r) {
                    if (r && r.year) {
                        frappe.msgprint({
                            title: "Warning",
                            indicator: "orange",
                            message: `Admission Year <b>${r.year}</b> is currently active.
                            Saving will deactivate it.`
                        });
                    }
                }
            );
        }
    }
});