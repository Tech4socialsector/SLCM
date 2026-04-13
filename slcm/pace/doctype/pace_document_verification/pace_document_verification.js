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
                if (frm.is_dirty()) {
                    frappe.msgprint(__("Please click 'Save' before finalizing to prevent version conflicts."));
                    return;
                }
                frappe.confirm(__("Are you sure you want to finalize this verification?"), function() {
                    frappe.call({
                        method: "slcm.pace.doctype.pace_document_verification.get_document_api.finalize_verification",
                        args: { docname: frm.doc.name },
                        callback: function(r) {
                            frm.reload_doc().then(() => {
                                if (r.message && r.message.status) {
                                    let msg;
                                    let color;
                                    if (r.message.status === "Verified") {
                                        msg = __("Documents successfully verified!");
                                        color = "green";
                                    } else if (r.message.status === "Rejected") {
                                        msg = __("Application has been REJECTED.");
                                        color = "red";
                                    } else {
                                        msg = __("Application returned to applicant for correction.");
                                        color = "orange";
                                    }
                                    
                                    let text_color = color === "green" ? "#28a745" : (color === "red" ? "#dc3545" : "#fd7e14");
                                    frappe.msgprint({
                                        title: __("Verification Finalized"),
                                        message: `<div style='text-align: center; padding: 20px; font-size: 16px; font-weight: bold; color: ${text_color};'>${msg}</div>`,
                                        primary_action: {
                                            label: __("Acknowledge"),
                                            action: function(d) {
                                                d.hide();
                                            }
                                        }
                                    });
                                }
                            });
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
                        row.row.css("background-color", ""); // Remove blanket color
                        
                        // Selectively color only the Is Reuploaded column and the pencil icon column
                        row.row.find('[data-fieldname="is_reuploaded"]').css("background-color", "#fff3cd");
                        row.row.children().last().css("background-color", "#fff3cd");
                    }
                });
            }
        }, 500);
    }
});
