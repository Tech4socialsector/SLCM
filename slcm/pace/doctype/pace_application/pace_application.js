// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PACE Application", {
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Verify Documents"), function() {
                frappe.db.get_value("PACE Document Verification", { application: frm.doc.name }, "name")
                .then(r => {
                    if (r && r.message && r.message.name) {
                        frappe.set_route("Form", "PACE Document Verification", r.message.name);
                    } else {
                        frappe.msgprint(__("No Verification Record found for this application."));
                    }
                });
            });
        }
    }
});
