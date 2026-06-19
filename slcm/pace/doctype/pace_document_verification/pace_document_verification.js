frappe.ui.form.on("PACE Document Verification", {
    onload(frm) {
        frm.set_query("assigned_verifier", () => {
            return {
                query: "slcm.pace.api.get_verifiers"
            };
        });

        setTimeout(() => {

            // Hide Assignments
            frm.page.wrapper.find('.form-assignments').hide();

            // Hide Tags
            frm.page.wrapper.find('.form-tags').hide();

            // Hide Shared
            frm.page.wrapper.find('.form-shared').hide();

            frm.page.wrapper.find('.form-attachments').hide();

        }, 200);
    },
    refresh(frm) {
        // Prevent deleting or adding rows in verification_items for non-managers (e.g. PACE Verifiers)
        const manager_roles = ["System Manager", "Academic Manager", "PACE Admission Manager", "Admission Admin", "Document Verification Admin", "PACE Verification Admin", "Administrator"];
        const is_manager = manager_roles.some(role => frappe.user_roles.includes(role));
        
        if (!is_manager) {
            frm.set_df_property("due_date", "read_only", 1);
            if (frm.fields_dict.verification_items && frm.fields_dict.verification_items.grid) {
                frm.fields_dict.verification_items.grid.cannot_add_rows = true;
                frm.fields_dict.verification_items.grid.cannot_delete_rows = true;
                frm.fields_dict.verification_items.grid.refresh();
            }
        } else {
            frm.set_df_property("due_date", "read_only", 0);
        }

        if (frm.doc.status === "Pending" || frm.doc.status === "Returned for Correction") {
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
                                    
                                    let text_color = color === "green" ? "#1b5e20" : (color === "red" ? "#b71c1c" : "#e65100");
                                    
                                    let d = new frappe.ui.Dialog({
                                        title: __("Verification Finalized"),
                                        size: "small",
                                        fields: [
                                            {
                                                fieldtype: "HTML",
                                                options: `<div style="text-align: center; padding: 15px 10px; font-size: 15px; font-weight: 600; color: ${text_color};">${msg}</div>`
                                            }
                                        ],
                                        primary_action_label: __("OK"),
                                        primary_action() {
                                            d.hide();
                                        }
                                    });
                                    d.show();
                                }
                            });
                        }
                    });
                });
            }).addClass("btn-primary");
            
            frm.add_custom_button(__("Reject Application"), function() {
                if (frm.is_dirty()) {
                    frappe.msgprint(__("Please click 'Save' before rejecting."));
                    return;
                }
                frappe.prompt([
                    {
                        label: __("Reason for Rejection"),
                        fieldname: "reason",
                        fieldtype: "Small Text",
                        reqd: 1
                    }
                ], (values) => {
                    frappe.call({
                        method: "slcm.pace.doctype.pace_document_verification.get_document_api.reject_application",
                        args: { 
                            docname: frm.doc.name,
                            reason: values.reason
                        },
                        callback: function(r) {
                            if (r.message && r.message.status) {
                                frappe.show_alert({message: __("Application Rejected"), indicator: "red"});
                                frm.reload_doc();
                            }
                        }
                    });
                }, __("Reject Application"), __("Reject"));
            },);
        }

        if (frm.doc.status === "Verified") {
            frm.add_custom_button(__("View Invoice"), function() {
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "PACE Applicant Fee Assignment",
                        filters: { applicant: frm.doc.application, fee_type: "Course Fee" },
                        fieldname: "name"
                    },
                    callback: function(r) {
                        if (r.message && r.message.name) {
                            const url = `/printview?doctype=PACE%20Applicant%20Fee%20Assignment&name=${encodeURIComponent(r.message.name)}&format=PACE%20Payment%20Invoice&trigger_print=0`;
                            window.open(url, "_blank");
                        } else {
                            frappe.msgprint(__("No PACE Applicant Fee Assignment found for this application."));
                        }
                    }
                });
            });
        }

        // Re-assign Verifier Button for Managers
        if (!frm.is_new() && (frappe.user_roles.includes("PACE Admission Manager") || frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("Admission Admin"))) {
            frm.add_custom_button(__("Re-assign Verifier"), function() {
                let d = new frappe.ui.Dialog({
                    title: __("Re-assign Verifier"),
                    fields: [
                        {
                            label: __("Current Verifier"),
                            fieldname: "current_verifier",
                            fieldtype: "Data",
                            default: frm.doc.assigned_verifier || __("Unassigned"),
                            read_only: 1
                        },
                        {
                            label: __("New Verifier"),
                            fieldname: "new_verifier",
                            fieldtype: "Link",
                            options: "User",
                            reqd: 1,
                            get_query: () => {
                                return {
                                    query: "slcm.pace.api.get_verifiers"
                                };
                            }
                        }
                    ],
                    primary_action_label: __("Re-assign"),
                    primary_action(values) {
                        frappe.call({
                            method: "slcm.pace.assignment_logic.reassign_to_user",
                            args: {
                                name: frm.doc.name,
                                verifier: values.new_verifier
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frappe.show_alert({
                                        message: r.message,
                                        indicator: "green"
                                    });
                                    d.hide();
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                });
                d.show();
            },);
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

        // Intercept private file clicks in grid to view securely and bypass direct Nginx block (404)
        if (frm.fields_dict.verification_items && frm.fields_dict.verification_items.grid) {
            frm.fields_dict.verification_items.grid.wrapper.on("click", "a", function(e) {
                const href = $(this).attr("href");
                if (href && href.startsWith("/private/files/") && !href.includes("view_private_file")) {
                    e.preventDefault();
                    e.stopPropagation();
                    const secureUrl = "/api/method/slcm.pace.api.view_private_file?file_url=" + encodeURIComponent(href);
                    window.open(secureUrl, "_blank");
                }
            });
        }
    }
});

frappe.ui.form.on("PACE Verification Item", {
    before_verification_items_remove: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        let docname = row.document_type || "this item";

        return new Promise((resolve, reject) => {
            frappe.confirm(
                __("Are you sure you want to remove the document verification item for '{0}'?", [docname]),
                function() {
                    // User clicked Yes - resolve to proceed with native deletion
                    resolve();
                },
                function() {
                    // User clicked No - reject to abort deletion
                    reject();
                }
            );
        });
    }
});
