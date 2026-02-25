frappe.ui.form.on("Admission Cycle", {
    refresh: function(frm) {
        // Status badge headline
        const colors = {Draft: "gray", Active: "green", Closed: "red"};
        const color = colors[frm.doc.status] || "gray";
        if (frm.doc.status) {
            frm.dashboard.set_headline(
                `<span style="background:${color};color:white;padding:3px 14px;
                border-radius:12px;font-size:12px;font-weight:bold;">
                ${frm.doc.status}</span>`
            );
        }

        // Show exam type details
        if (frm.doc.exam_type && !frm.is_new()) {
            frappe.db.get_value("Exam Type Config", frm.doc.exam_type,
                ["exam_category", "score_import_method"],
                function(r) {
                    if (r) {
                        frm.dashboard.add_comment(
                            `Exam: ${frm.doc.exam_type} | Category: ${r.exam_category} | Import: ${r.score_import_method}`,
                            "blue", true
                        );
                    }
                }
            );
        }

        // Quick status change buttons
        if (!frm.is_new() && frm.doc.docstatus !== 1) {
            if (frm.doc.status === "Draft") {
                frm.add_custom_button("Activate Cycle", function() {
                    frappe.confirm(
                        "Activate this cycle? Deadlines will be enforced after activation.",
                        function() {
                            frm.set_value("status", "Active");
                            frm.save();
                        }
                    );
                }, "Actions").addClass("btn-success");
            }
            if (frm.doc.status === "Active") {
                frm.add_custom_button("Close Cycle", function() {
                    frappe.confirm("Close this cycle? No further changes will be allowed.", function() {
                        frm.set_value("status", "Closed");
                        frm.save();
                    });
                }, "Actions");
            }
        }

        // Hide legacy workflow_type field always
        frm.set_df_property("workflow_type", "hidden", 1);
    },

    admission_year: function(frm) {
        if (frm.doc.admission_year) {
            frappe.db.get_value("Admission Year",
                frm.doc.admission_year,
                ["academic_start", "academic_end"],
                function(r) {
                    if (r && r.academic_start) {
                        frm.dashboard.add_comment(
                            `Academic Year: ${r.academic_start} to ${r.academic_end}`,
                            "blue", true
                        );
                    }
                }
            );
        }
    },

    exam_type: function(frm) {
        if (frm.doc.exam_type) {
            frappe.show_alert({
                message: `Exam type set to ${frm.doc.exam_type}. Score import and merit calculation will follow this exam's configuration.`,
                indicator: "green"
            }, 5);
        }
    },

    have_multiple_rounds: function(frm) {
        frappe.show_alert({
            message: frm.doc.have_multiple_rounds
                ? "Multiple rounds enabled. Add rounds below."
                : "Single round mode. Round table hidden.",
            indicator: frm.doc.have_multiple_rounds ? "green" : "blue"
        }, 4);
    }
});
