frappe.ui.form.on("PACE Document Verification", {
    onload(frm) {
        frm.set_query("assigned_verifier", () => {
            return {
                query: "slcm.pace.api.get_verifiers"
            };
        });
    },
    refresh(frm) {
        if (frm.doc.overall_status === "Pending" || frm.doc.overall_status === "Returned for Correction") {
            frm.add_custom_button(__("Finalize Verification"), function() {
                frappe.confirm(__("Are you sure you want to finalize this verification?"), function() {
                    frappe.call({
                        method: "slcm.pace.doctype.pace_document_verification.get_document_api.finalize_verification",
                        args: { docname: frm.doc.name },
                        callback: function(r) {
                            frm.reload_doc();
                            if (r.message && r.message.status) {
                                frappe.show_alert({
                                    message: __("Verification finalized: {0}").format(r.message.status),
                                    indicator: 'green'
                                });
                            }
                        }
                    });
                });
            }).addClass("btn-primary");
        }

        // Highlight re-uploaded items
        setTimeout(() => {
            if (frm.fields_dict.verification_items && frm.fields_dict.verification_items.grid) {
                frm.fields_dict.verification_items.grid.grid_rows.forEach(row => {
                    if (row.doc.is_reuploaded) {
                        row.row.css("background-color", "#fff3cd"); // light yellow
                    }
                });
            }
        }, 500);
    }
});
