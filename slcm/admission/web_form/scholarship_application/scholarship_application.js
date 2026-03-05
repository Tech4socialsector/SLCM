frappe.ready(function () {
    // Inject CSS for mandatory field symbols
    const style = document.createElement('style');
    style.innerHTML = `
        .form-group.required label::after {
            content: " *";
            color: red;
            font-weight: bold;
        }
        /* Alternative for some versions of Frappe web forms */
        .reqd label::after {
            content: " *";
            color: red;
            font-weight: bold;
        }
    `;
    document.head.appendChild(style);

    // Both onload and after_load for maximum compatibility
    frappe.web_form.onload = function () {
        init_form();
    };

    frappe.web_form.on('after_load', () => {
        init_form();
    });

    function init_form() {
        if (window.scholarship_form_initialized) return;
        window.scholarship_form_initialized = true;

        console.log("Scholarship Web Form Initialization. User:", frappe.session.user);

        // Set default status for new applications
        if (window.location.pathname.endsWith('/new')) {
            frappe.web_form.set_value("status", "Submitted");

            // Hide the workflow section and fields
            frappe.web_form.set_df_property("section_workflow", "hidden", 1);
            ["status", "reviewed_by", "approved_by", "approval_date", "rejection_reason"].forEach(f => {
                frappe.web_form.set_df_property(f, "hidden", 1);
            });
        } else if (!frappe.web_form.get_value("status")) {
            frappe.web_form.set_value("status", "Submitted");
        }

        // Fetch applicant details on load
        frappe.call({
            method: "slcm.admission.doctype.scholarship_application.scholarship_application.get_applicant_details",
            callback: function (r) {
                console.log("Applicant Details Response:", r);
                if (r.message) {
                    var details = r.message;
                    frappe.web_form.set_value("applicant_id", details.name);
                    frappe.web_form.set_value("applicant_name", details.candidate_name);
                    frappe.web_form.set_value("admission_cycle", details.admission_cycle);
                    frappe.web_form.set_value("campus", details.campus);
                    frappe.web_form.set_value("program", details.program);

                    // Set to read-only since it's auto-filled
                    set_fields_read_only(true);

                    // Fetch fee and schemes
                    fetch_fee(details);
                    filter_schemes(details);
                } else {
                    console.warn("No applicant record found for this user.");
                    set_fields_read_only(false);
                    if (frappe.session.user === "Administrator") {
                        frappe.msgprint(__("<b>Administrator mode:</b> Please manually select an Applicant ID."));
                    }
                }
            }
        });
        refresh_mandatory_classes();
    }

    function set_fields_read_only(read_only) {
        const fields = ["applicant_id", "applicant_name", "admission_cycle", "campus", "program"];
        fields.forEach(f => {
            frappe.web_form.set_df_property(f, "read_only", read_only ? 1 : 0);
        });
        refresh_mandatory_classes();
    }

    function refresh_mandatory_classes() {
        // Manually ensure the required class is on the form groups
        ["family_income", "income_certificate"].forEach(f => {
            const field = frappe.web_form.get_field(f);
            if (field && field.$wrapper) {
                field.$wrapper.addClass('required');
                field.$wrapper.addClass('reqd');
            }
        });
    }

    // Manual selection trigger
    frappe.web_form.on("applicant_id", (field, value) => {
        if (value) {
            console.log("Manual Applicant ID selected:", value);
            frappe.db.get_value("Applicant", value, ["candidate_name", "program", "campus", "admission_cycle"], (r) => {
                if (r) {
                    console.log("Fetched Applicant Details:", r);
                    frappe.web_form.set_value("applicant_name", r.candidate_name);
                    frappe.web_form.set_value("admission_cycle", r.admission_cycle);
                    frappe.web_form.set_value("campus", r.campus);
                    frappe.web_form.set_value("program", r.program);

                    fetch_fee({
                        name: value,
                        program: r.program,
                        campus: r.campus,
                        admission_cycle: r.admission_cycle
                    });
                    filter_schemes({
                        name: value,
                        program: r.program,
                        campus: r.campus,
                        admission_cycle: r.admission_cycle
                    });
                    refresh_mandatory_classes();
                }
            });
        }
    });

    function fetch_fee(details) {
        frappe.call({
            method: "slcm.admission.doctype.scholarship_application.scholarship_application.get_original_fee_amount",
            args: {
                applicant_id: details.name,
                program: details.program,
                campus: details.campus,
                cycle: details.admission_cycle
            },
            callback: function (r) {
                if (r.message) {
                    frappe.web_form.set_value("original_fee_amount", r.message);
                }
            }
        });
    }

    function filter_schemes(details) {
        frappe.call({
            method: "slcm.admission.doctype.scholarship_application.scholarship_application.get_eligible_scholarship_schemes",
            args: {
                applicant_id: details.name,
                program: details.program,
                campus: details.campus,
                admission_cycle: details.admission_cycle
            },
            callback: function (r) {
                if (r.message) {
                    var eligible_schemes = r.message;
                    console.log("Eligible Schemes:", eligible_schemes);
                    frappe.web_form.set_query("scholarship_scheme", function () {
                        return {
                            filters: [
                                ["Scholarship Scheme", "name", "in", eligible_schemes]
                            ]
                        };
                    });
                }
            }
        });
    }

    frappe.web_form.on("scholarship_scheme", (field, value) => {
        if (value) {
            frappe.web_form.set_df_property("family_income", "hidden", 0);
            frappe.web_form.set_df_property("family_income", "reqd", 1);
            frappe.web_form.set_df_property("income_certificate", "hidden", 0);
            frappe.web_form.set_df_property("income_certificate", "reqd", 1);
        }
    });

    frappe.web_form.validate = () => {
        let data = frappe.web_form.get_values();
        if (!data.family_income) {
            frappe.msgprint(__("Family Income is mandatory"));
            return false;
        }
        if (!data.income_certificate) {
            frappe.msgprint(__("Income Certificate is mandatory"));
            return false;
        }
        return true;
    };
});
