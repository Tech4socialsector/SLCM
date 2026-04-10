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
    },
    ug_degree_certificate(frm) {
        trigger_reupload(frm, "ug_degree_certificate");
    },
    govt_id(frm) {
        trigger_reupload(frm, "govt_id");
    },
    student_signature(frm) {
        trigger_reupload(frm, "student_signature");
    },
    passport_oci(frm) {
        trigger_reupload(frm, "passport_oci");
    },
    self_declaration(frm) {
        trigger_reupload(frm, "self_declaration");
    }
});

function trigger_reupload(frm, fieldname) {
    if (frm.doc[fieldname] && ["Returned for Correction", "Under Verification", "Submitted"].includes(frm.doc.status)) {
        frappe.call({
            method: "slcm.pace.api.reset_verification_status",
            args: {
                application: frm.doc.name,
                fieldname: fieldname,
                file: frm.doc[fieldname]
            },
            callback: function(r) {
                if (r.message && r.message.status === "success") {
                    frappe.show_alert({
                        message: __("Document updated. Marked for re-verification."),
                        indicator: 'orange'
                    });
                }
            }
        });
    }
}
