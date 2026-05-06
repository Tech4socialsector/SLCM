/** Effective Country link — blank treated as India for legacy records. */
function slcm_applicant_effective_country(country_field_value) {
    const v = (country_field_value && String(country_field_value).trim()) || "";
    return v || "India";
}

function slcm_applicant_setup_country_state_city_queries(frm) {
    frm.set_query("state", () => {
        const eff = slcm_applicant_effective_country(frm.doc.country);
        if (eff.toLowerCase() === "india") {
            return { filters: { country: eff } };
        }
        return { filters: { name: "Other" } };
    });

    frm.set_query("city", () => {
        if (!frm.doc.state) {
            return { filters: { name: "!__noop__" } };
        }
        return {
            filters: {
                state: frm.doc.state
            }
        };
    });
}

frappe.ui.form.on("Applicant", {

    // ── REFRESH ──────────────────────────────
    refresh: function (frm) {
        // Auto-refresh when application_status is updated from Entrance Test Seat Allocation
        if (!window._applicant_status_realtime_subscribed) {
            window._applicant_status_realtime_subscribed = true;
            frappe.realtime.on("applicant_application_status_updated", function (data) {
                const frm = cur_frm;
                if (frm && frm.doctype === "Applicant" && frm.doc && frm.doc.name === data.docname) {
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __("Application status was updated to {0}", [data.application_status || ""]),
                        indicator: "blue",
                    }, 4);
                }
            });
        }

        // Status badge in dashboard headline
        const status_colors = {
            "Draft": "gray",
            "Submitted": "blue",
            "Under Evaluation": "blue",
            "Shortlisted": "orange",
            "Interview Scheduled": "purple",
            "Entrance Test Scheduled": "purple",
            "Interview Excempted": "teal",
            "Entrance Test Exempted": "teal",
            "Excempted Entrance Test And Interview": "teal",
            "Entrance Test Rejected": "red",
            "Entrance Test Completed": "green",
            "Interview Rejected": "red",
            "Interview Completed": "green",
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

        // Application completion indicator
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

        // Custom buttons for submitted docs
        // if (frm.doc.application_status && frm.doc.application_status !== "Draft") {
        //     frm.add_custom_button(__("View Campus Status"), function () {
        //         frappe.set_route("List", "Applicant Campus Preference", {
        //             applicant: frm.doc.name
        //         });
        //     });
        //     frm.add_custom_button(__("View Documents"), function () {
        //         frappe.set_route("List", "Applicant Document", {
        //             applicant: frm.doc.name
        //         });
        //     });
        // }

        // Record Application Fee Payment (offline)
        const feeStatus = (frm.doc.application_fee_status || "").trim();
        if (!frm.doc.__islocal && frm.doc.application_status === "Draft" &&
            (feeStatus === "Pending" || feeStatus === "Requested") &&
            frm.doc.program && frm.doc.admission_cycle) {
            frm.add_custom_button(__("Record Application Fee Payment"), function () {
                const d = new frappe.ui.Dialog({
                    title: __("Record Application Fee Payment"),
                    fields: [
                        { label: __("Payment Mode"), fieldname: "payment_mode", fieldtype: "Select",
                            options: "Cash\nCheque\nUPI\nQR Code\nBank Transfer\nDemand Draft", default: "Cash", reqd: 1 },
                        { label: __("Reference No / UTR / Cheque No"), fieldname: "reference_number", fieldtype: "Data", reqd: 1 },
                        { label: __("Bank Name"), fieldname: "bank_name", fieldtype: "Data" },
                        { label: __("Cheque Number"), fieldname: "cheque_number", fieldtype: "Data" },
                        { label: __("Cheque Date"), fieldname: "cheque_date", fieldtype: "Date" },
                        { label: __("UPI ID"), fieldname: "upi_id", fieldtype: "Data" },
                        { label: __("Remarks"), fieldname: "remarks", fieldtype: "Small Text" }
                    ],
                    primary_action_label: __("Record Payment"),
                    primary_action(values) {
                        frappe.call({
                            method: "slcm.api.service.fee_service.process_application_fee_payment",
                            args: {
                                applicant_name: frm.doc.name,
                                payment_mode: values.payment_mode,
                                reference_number: values.reference_number,
                                bank_name: values.bank_name,
                                cheque_number: values.cheque_number,
                                cheque_date: values.cheque_date,
                                upi_id: values.upi_id,
                                remarks: values.remarks
                            },
                            callback(r) {
                                if (!r.exc) {
                                    d.hide();
                                    frm.reload_doc();
                                    frappe.show_alert({ message: __("Payment recorded. Receipt: {0}", [r.message || ""]), indicator: "green" });
                                }
                            }
                        });
                    }
                });
                d.show();
            }, __("Actions"));
        }

        if (frm.doc.application_fee_status === "Pending" || frm.doc.application_fee_status === "Requested") {
            frm.add_custom_button(__("Waive Application Fee"), function () {
                frappe.confirm(
                    __("Mark application fee as Waived for this applicant?"),
                    function () {
                        frappe.call({
                            method: "slcm.admission.doctype.applicant.applicant.waive_fee",
                            args: { name: frm.doc.name },
                            callback: function (r) {
                                frm.reload_doc();
                                frappe.show_alert({ message: __("Fee marked as Waived"), indicator: "green" }, 5);
                            }
                        });
                    }
                );
            }, __("Portal"));
        }
        // Guardian fields required only when flag is set
        frm.toggle_reqd("guardian_name", frm.doc.guardian_required);
        frm.toggle_reqd("guardian_mobile", frm.doc.guardian_required);
        // Percentage required when National test is selected
        frm.toggle_reqd("percentage", !!frm.doc.national_test_name);

        slcm_applicant_setup_country_state_city_queries(frm);
    },

    country: function (frm) {
        frm.set_value("state", "");
        frm.set_value("city", "");
    },

    state: function (frm) {
        frm.set_value("city", "");
    },

    // ── VALIDATE (runs before every save / submit) ──
    validate: function (frm) {
        if (frm.doc.application_status === "Draft") {
            frm.ignore_mandatory = true;
        } else {
            frm.ignore_mandatory = false;
        }

        let errors = [];

        // HSC Percentage
        if (frm.doc.hsc_percentage !== undefined && frm.doc.hsc_percentage !== null && frm.doc.hsc_percentage !== "") {
            if (frm.doc.hsc_percentage < 35) {
                errors.push(__("HSC percentage should be above 35%"));
            } else if (frm.doc.hsc_percentage > 100) {
                errors.push(__("HSC percentage cannot be more than 100%"));
            }
        }

        // UG CGPA (child table)
        if (frm.doc.ug_degree_details && frm.doc.ug_degree_details.length) {
            frm.doc.ug_degree_details.forEach(row => {
                if (row.ug_cgpa !== undefined && row.ug_cgpa !== null && row.ug_cgpa !== "") {
                    if (row.ug_cgpa < 4 || row.ug_cgpa > 10) {
                        errors.push(__("UG CGPA for degree \"{0}\" should be between 4 and 10",
                            [row.degree || __("(unnamed)")]));
                    }
                }
            });
        }

        // PG CGPA (child table)
        if (frm.doc.pg_degree_details && frm.doc.pg_degree_details.length) {
            frm.doc.pg_degree_details.forEach(row => {
                if (row.pg_cgpa !== undefined && row.pg_cgpa !== null && row.pg_cgpa !== "") {
                    if (row.pg_cgpa < 4 || row.pg_cgpa > 10) {
                        errors.push(__("PG CGPA for degree \"{0}\" should be between 4 and 10",
                            [row.degree || __("(unnamed)")]));
                    }
                }
            });
        }

        // When National test is selected, percentage is required
        if (frm.doc.national_test_name && (frm.doc.percentage === undefined || frm.doc.percentage === null || frm.doc.percentage === "")) {
            errors.push(__("Score or percentage is required when National test is selected."));
        }

        // Declaration must be accepted when submitting
        if (frm.doc.application_status === "Submitted" && !frm.doc.declaration_undertaking) {
            errors.push(__("You must accept the Declaration & Undertaking before submitting."));
        }

        // Campus preference duplicates
        const prefs = [frm.doc.first_preference, frm.doc.second_preference, frm.doc.third_preference]
            .filter(Boolean);
        if (new Set(prefs).size !== prefs.length) {
            errors.push(__("Campus preferences must all be unique. Please remove duplicate selections."));
        }

        if (errors.length) {
            frappe.msgprint({
                title: __("Validation Error"),
                indicator: "red",
                message: errors.join("<br>")
            });
            frappe.validated = false;
        }
    },

    // ── APPLICATION TYPE ──────────────────────
    application_type: function (frm) {
        const messages = {
            "External Test": __("CLAT workflow: Your CLAT rank will be imported from the Consortium."),
            "Internal Test": __("NLSAT workflow: You must appear for the NLSAT exam."),
            "PACE": __("PACE workflow: Admission is based on academic merit only.")
        };
        if (frm.doc.application_type && messages[frm.doc.application_type]) {
            frappe.show_alert({ message: messages[frm.doc.application_type], indicator: "blue" }, 6);
        }
    },

    // ── GUARDIAN REQUIRED ────────────────────
    guardian_required: function (frm) {
        frm.toggle_reqd("guardian_name", frm.doc.guardian_required);
        frm.toggle_reqd("guardian_mobile", frm.doc.guardian_required);
    },

    national_test_name: function (frm) {
        frm.toggle_reqd("percentage", !!frm.doc.national_test_name);
    },

    // ── DECLARATION UNDERTAKING ──────────────
    declaration_undertaking: function (frm) {
        if (!frm.doc.declaration_undertaking) {
            frappe.msgprint({
                title: __("Declaration Required"),
                indicator: "orange",
                message: __("You must accept the Declaration & Undertaking to submit.")
            });
        }
    },

    // ── HSC PERCENTAGE ───────────────────────
    hsc_percentage: function (frm) {
        const val = frm.doc.hsc_percentage;
        if (val === null || val === undefined || val === "") return;

        if (val < 35) {
            frappe.show_alert({ message: __("HSC percentage must be at least 35%."), indicator: "orange" });
            frm.set_value("hsc_percentage", null);
        } else if (val > 100) {
            frappe.show_alert({ message: __("HSC percentage cannot exceed 100%."), indicator: "orange" });
            frm.set_value("hsc_percentage", null);
        }
    },

    // ── CAMPUS PREFERENCES ───────────────────
    first_preference: function (frm) {
        if (frm.doc.first_preference &&
            frm.doc.first_preference === frm.doc.second_preference) {
            frappe.msgprint({
                title: __("Duplicate Preference"),
                indicator: "red",
                message: __("First and Second preference cannot be the same campus.")
            });
            frm.set_value("second_preference", "");
        }
    },

    second_preference: function (frm) {
        if (frm.doc.second_preference &&
            frm.doc.second_preference === frm.doc.first_preference) {
            frappe.msgprint({
                title: __("Duplicate Preference"),
                indicator: "red",
                message: __("Second preference cannot be the same as First preference.")
            });
            frm.set_value("second_preference", "");
            return;
        }
        if (frm.doc.second_preference &&
            frm.doc.second_preference === frm.doc.third_preference) {
            frappe.msgprint({
                title: __("Duplicate Preference"),
                indicator: "red",
                message: __("Second and Third preference cannot be the same campus.")
            });
            frm.set_value("third_preference", "");
        }
    },

    third_preference: function (frm) {
        if (frm.doc.third_preference && (
            frm.doc.third_preference === frm.doc.first_preference ||
            frm.doc.third_preference === frm.doc.second_preference
        )) {
            frappe.msgprint({
                title: __("Duplicate Preference"),
                indicator: "red",
                message: __("Third preference must differ from First and Second preference.")
            });
            frm.set_value("third_preference", "");
        }
    }
});

// ─────────────────────────────────────────────
//  UG Degree Detail — Child Table
// ─────────────────────────────────────────────
frappe.ui.form.on("UG Degree Detail", {
    ug_cgpa: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.ug_cgpa === null || row.ug_cgpa === undefined || row.ug_cgpa === "") return;

        if (row.ug_cgpa < 4 || row.ug_cgpa > 10) {
            frappe.show_alert({ message: __("UG CGPA must be between 4 and 10."), indicator: "orange" });
            frappe.model.set_value(cdt, cdn, "ug_cgpa", null);
        }
    }
});

// ─────────────────────────────────────────────
//  PG Degree Details — Child Table
// ─────────────────────────────────────────────
frappe.ui.form.on("PG Degree Details", {
    pg_cgpa: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.pg_cgpa === null || row.pg_cgpa === undefined || row.pg_cgpa === "") return;

        if (row.pg_cgpa < 4 || row.pg_cgpa > 10) {
            frappe.show_alert({ message: __("PG CGPA must be between 4 and 10."), indicator: "orange" });
            frappe.model.set_value(cdt, cdn, "pg_cgpa", null);
        }
    }
});