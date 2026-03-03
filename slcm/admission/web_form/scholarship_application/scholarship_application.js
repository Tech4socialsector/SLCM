frappe.ready(function () {
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
    }

    function set_fields_read_only(read_only) {
        const fields = ["applicant_id", "applicant_name", "admission_cycle", "campus", "program"];
        fields.forEach(f => {
            frappe.web_form.set_df_property(f, "read_only", read_only ? 1 : 0);
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
            frappe.db.get_value("Scholarship Scheme", value, ["scheme_type", "income_certificate_required"], (r) => {
                if (r) {
                    const is_need = r.scheme_type === "Need" || r.income_certificate_required;
                    frappe.web_form.set_df_property("family_income", "hidden", !is_need);
                    frappe.web_form.set_df_property("family_income", "reqd", is_need);
                    frappe.web_form.set_df_property("income_certificate", "hidden", !is_need);
                    frappe.web_form.set_df_property("income_certificate", "reqd", is_need);
                }
            });
        }
    });
});
