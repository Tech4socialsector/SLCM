frappe.ui.form.on("PACE Document Verification", {
    refresh(frm) {
        if (frm.doc.overall_status === "Pending") {
            frm.add_custom_button(__("Finalize Verification"), function() {
                frappe.confirm(__("Are you sure you want to finalize this verification?"), function() {
                    frappe.call({
                        method: "slcm.pace.doctype.pace_document_verification.get_document_api.finalize_verification",
                        args: { docname: frm.doc.name },
                        callback: function(r) {
                            frm.reload_doc();
                            frappe.msgprint(__("Verification finalized successfully."));
                        }
                    });
                });
            }).addClass("btn-primary");
        }
    }
});
