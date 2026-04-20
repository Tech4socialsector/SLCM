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

        // Toggle degree certificate visibility
        set_ug_degree_certificate_visibility(frm);
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
    },
    ug_degree_add(frm) {
        // The new row defaults to "Declared" — immediately show the certificate field.
        // Then re-check after a delay once frm.doc is fully updated.
        frm.toggle_display("ug_degree_certificate", true);
        frm.set_df_property("ug_degree_certificate", "reqd", 1);
        setTimeout(() => {
            set_ug_degree_certificate_visibility(frm);
        }, 300);
    },
    ug_degree_remove(frm) {
        set_ug_degree_certificate_visibility(frm);
    },
    ug_degree_on_grid_refresh(frm) {
        set_ug_degree_certificate_visibility(frm);
    }
});

frappe.ui.form.on("PACE UG Degree Details", {
    result_status: function(frm, cdt, cdn) {
        set_ug_degree_certificate_visibility(frm);
    },
    form_render: function(frm, cdt, cdn) {
        // Fires when a row dialog opens — re-evaluate in case defaults just loaded
        setTimeout(() => {
            set_ug_degree_certificate_visibility(frm);
        }, 150);
    }
});

function set_ug_degree_certificate_visibility(frm) {
    let waiting = false;
    let declared = false;

    if (frm.doc.ug_degree && frm.doc.ug_degree.length > 0) {
        frm.doc.ug_degree.forEach(row => {
            if (row.result_status === "Waiting for result") {
                waiting = true;
            } else if (row.result_status === "Declared") {
                declared = true;
            }
        });
    }

    // Show and make mandatory if ANY row is "Declared"
    if (declared) {
        frm.toggle_display("ug_degree_certificate", true);
        frm.set_df_property("ug_degree_certificate", "reqd", 1);
    } else {
        // All rows are "Waiting for result", or table is empty — hide and not mandatory
        frm.toggle_display("ug_degree_certificate", false);
        frm.set_df_property("ug_degree_certificate", "reqd", 0);
    }
}

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
