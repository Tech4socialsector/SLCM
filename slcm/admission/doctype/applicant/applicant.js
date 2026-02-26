frappe.ui.form.on("Applicant", {

    refresh: function(frm) {
        const status_colors = {
            "Draft": "gray",
            "Submitted": "blue",
            "Under Evaluation": "blue",
            "Shortlisted": "orange",
            "Interview Scheduled": "purple",
            "Offered": "green",
            "Accepted": "darkgreen",
            "Rejected": "red",
            "Waitlisted": "yellow"
        };
        const color = status_colors[frm.doc.application_status] || "gray";
        frm.dashboard.set_headline(
            `<span style="color:${color}; font-weight:bold;">
            Status: ${frm.doc.application_status}
            </span>`
        );

        const required_fields = [
            "candidate_name", "email", "mobile_number",
            "date_of_birth", "first_preference",
            "class_x_percentage", "class_xii_percentage",
            "declaration_undertaking"
        ];
        const filled = required_fields.filter(f => frm.doc[f]).length;
        const pct = Math.round((filled / required_fields.length) * 100);
        frm.dashboard.add_comment(
            `Application Completion: ${pct}%`,
            pct === 100 ? "green" : pct >= 50 ? "orange" : "red"
        );

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button("View Campus Status", function() {
                frappe.set_route("List", "Applicant Campus Preference", {
                    applicant: frm.doc.name
                });
            });
            frm.add_custom_button("View Documents", function() {
                frappe.set_route("List", "Applicant Document", {
                    applicant: frm.doc.name
                });
            });
        }

        if (frm.doc.application_fee_status === "Pending") {
            frm.add_custom_button(__("Waive Application Fee"), function() {
                frappe.confirm(
                    __("Mark application fee as Waived for this applicant?"),
                    function() {
                        frappe.call({
                            method: "slcm.admission.doctype.applicant.applicant.waive_fee",
                            args: { name: frm.doc.name },
                            callback: function(r) {
                                frm.reload_doc();
                                frappe.show_alert({ message: __("Fee marked as Waived"), indicator: "green" }, 5);
                            }
                        });
                    }
                );
            }, __("Portal"));
        }
    },

    application_type: function(frm) {
        const messages = {
            "CLAT": "CLAT workflow: Your CLAT rank will be imported from the Consortium.",
            "NLSAT": "NLSAT workflow: You must appear for the NLSAT exam.",
            "PACE": "PACE workflow: Admission is based on academic merit only."
        };
        if (frm.doc.application_type && messages[frm.doc.application_type]) {
            frappe.show_alert({
                message: messages[frm.doc.application_type],
                indicator: "blue"
            }, 6);
        }
    },

    reservation_category: function(frm) {
        frm.set_value("ews_certificate", "");
        frm.set_value("caste_certificate", "");
        frm.set_value("pwd_certificate", "");
        frm.set_value("ews", 0);
        frm.set_value("pwd", 0);
    },

    guardian_required: function(frm) {
        frm.toggle_reqd("guardian_name", frm.doc.guardian_required);
        frm.toggle_reqd("guardian_mobile", frm.doc.guardian_required);
    },

    declaration_undertaking: function(frm) {
        if (!frm.doc.declaration_undertaking) {
            frappe.msgprint({
                title: "Declaration Required",
                indicator: "orange",
                message: "You must accept the Declaration Undertaking to submit."
            });
        }
    },

    first_preference: function(frm) {
        if (frm.doc.first_preference &&
            frm.doc.first_preference === frm.doc.second_preference) {
            frappe.msgprint({
                title: "Duplicate Preference",
                indicator: "red",
                message: "First and Second preference cannot be the same campus."
            });
            frm.set_value("second_preference", "");
        }
    },

    second_preference: function(frm) {
        if (frm.doc.second_preference &&
            frm.doc.second_preference === frm.doc.third_preference) {
            frappe.msgprint({
                title: "Duplicate Preference",
                indicator: "red",
                message: "Second and Third preference cannot be the same campus."
            });
            frm.set_value("third_preference", "");
        }
    }
});