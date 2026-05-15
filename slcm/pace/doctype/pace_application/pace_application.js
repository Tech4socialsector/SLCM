// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

/** Country link equals India → all states for that country; otherwise only State named "Other". */
function pace_country_link_is_india(country_link_name) {
    return ((country_link_name || "") + "").trim().toLowerCase() === "india";
}

function pace_setup_address_link_queries(frm) {
    const blocks = [
        { country: "country", state: "state", district: "district", city_field: "city" },
        { country: "p_country", state: "p_state", district: "p_district", city_field: "p_city" },
    ];

    blocks.forEach(({ country, state, district }) => {
        frm.set_query(state, () => {
            const raw = frm.doc[country];
            const effective_country = ((raw || "") + "").trim() || "India";
            if (pace_country_link_is_india(effective_country)) {
                return { filters: { country: effective_country } };
            }
            return { filters: { name: "Other" } };
        });

        frm.set_query(district, () => {
            const st = frm.doc[state];
            if (!st) {
                return { filters: { name: "!__noop__" } };
            }
            return { filters: { state: st } };
        });
    });
}

frappe.ui.form.on("PACE Application", {
    onload(frm) {
        frm.set_query("assigned_verifier", () => {
            return {
                query: "slcm.pace.api.get_verifiers"
            };
        });
        pace_setup_address_link_queries(frm);
    },

    country(frm) {
        frm.set_value("state", "");
        frm.set_value("district", "");
        frm.set_value("city", "");
    },

    state(frm) {
        frm.set_value("district", "");
        frm.set_value("city", "");
    },

    p_country(frm) {
        frm.set_value("p_state", "");
        frm.set_value("p_district", "");
        frm.set_value("p_city", "");
    },

    p_state(frm) {
        frm.set_value("p_district", "");
        frm.set_value("p_city", "");
    },
    refresh(frm) {
        pace_setup_address_link_queries(frm);

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

        // Convert to Student button
        if (!frm.doc.__islocal && frm.doc.status === 'Fee Paid') {
            frm.add_custom_button(__('Convert to Student'), function () {
                frappe.confirm(
                    __('Convert application {0} to a Student Master? This will also update the user role.', [frm.doc.applicant_name || frm.doc.name]),
                    function () {
                        frappe.call({
                            method: 'slcm.pace.api.service.pace_to_student.convert_pace_to_student',
                            args: {
                                pace_app_name: frm.doc.name
                            },
                            freeze: true,
                            freeze_message: __('Creating Student Master...'),
                            callback: function (r) {
                                if (r.message) {
                                    const res = r.message;
                                    if (res.created) {
                                        frappe.show_alert({
                                            message: __('Student Master {0} created successfully.', [res.student_name]),
                                            indicator: 'green'
                                        }, 6);
                                    } else {
                                        frappe.show_alert({
                                            message: __('Student Master {0} already exists for this application.', [res.student_name]),
                                            indicator: 'blue'
                                        }, 6);
                                    }
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __('Actions'));
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
    // TEMPORARY: always show UG Degree Certificate and keep it mandatory.
    // Restore the block below when tying visibility to UG result status again.
    frm.toggle_display("ug_degree_certificate", true);
    frm.set_df_property("ug_degree_certificate", "reqd", 1);

    /*
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

    if (declared) {
        frm.toggle_display("ug_degree_certificate", true);
        frm.set_df_property("ug_degree_certificate", "reqd", 1);
    } else {
        frm.toggle_display("ug_degree_certificate", false);
        frm.set_df_property("ug_degree_certificate", "reqd", 0);
    }
    */
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
