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

        // Listen for background email status pushed via publish_realtime
        frappe.realtime.off("pace_email_status");
        frappe.realtime.on("pace_email_status", function(data) {
            if (data.doc_name !== frm.doc.name) return;

            if (data.status === "success") {
                let recipient = data.recipient ? `<br><small style="opacity:0.85;">Sent to: <strong>${data.recipient}</strong></small>` : "";
                frappe.show_alert({
                    message: `
                        <div style="display:flex; align-items:flex-start; gap:10px;">
                            <span style="font-size:22px; line-height:1;">✅</span>
                            <div>
                                <strong style="font-size:13px;">Confirmation Email Sent!</strong>
                                <div style="font-size:12px; margin-top:2px; color:#444;">
                                    Your application has been submitted successfully.${recipient}
                                </div>
                            </div>
                        </div>`,
                    indicator: "green"
                }, 8);
            } else {
                frappe.show_alert({
                    message: `
                        <div style="display:flex; align-items:flex-start; gap:10px;">
                            <span style="font-size:22px; line-height:1;">⚠️</span>
                            <div>
                                <strong style="font-size:13px;">Email Could Not Be Sent</strong>
                                <div style="font-size:12px; margin-top:2px; color:#555;">
                                    Your application is saved. Please contact support if you don't receive a confirmation.
                                </div>
                            </div>
                        </div>`,
                    indicator: "orange"
                }, 10);
            }
        });
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
