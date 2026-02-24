frappe.ui.form.on("Merit List", {
    refresh: function(frm) {
        if (frm.doc.is_published) {
            frm.dashboard.set_headline(
                `<span style="color: green; font-weight: bold;">
                ✓ Published - Public Merit List
                </span>`
            );
            frm.disable_save();
            frm.add_custom_button("Export PDF", function() {
                frappe.call({
                    method: "slcm.admission_managment.utils.merit.export_merit_list_pdf",
                    args: { merit_list_name: frm.doc.name },
                    callback: function(r) {
                        if (r.message) {
                            window.open(r.message);
                        }
                    }
                });
            }, "Actions");
        } else {
            frm.dashboard.set_headline(
                `<span style="color: orange; font-weight: bold;">
                ⚠ Draft - Not yet published
                </span>`
            );
        }
    }
});