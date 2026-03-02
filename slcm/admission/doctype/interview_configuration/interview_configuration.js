frappe.ui.form.on("Interview Configuration", {

    refresh: function (frm) {

        // Remove any previously added buttons (safety)
        frm.remove_custom_button("Generate Interview List");
        frm.remove_custom_button("View Interview List");

        // ── "Generate Interview List" button ─────────────────────────────────
        // Visible only when:
        //   1. Document is unsaved / not submitted (docstatus = 0)
        //   2. Status is Draft, In Progress or Failed
        //   3. All required fields are filled
        if (
            frm.doc.docstatus === 0 &&
            ["Draft", "In Progress", "Failed"].includes(frm.doc.status || "Draft") &&
            frm.doc.academic_year &&
            frm.doc.campus &&
            frm.doc.admission_cycle &&
            frm.doc.program_level
        ) {
            frm.add_custom_button(__("Generate Interview List"), function () {

                frappe.confirm(
                    __(
                        "Generate Interview List for this configuration?<br><br>"
                        + "<b>Filters:</b><br>"
                        + "Academic Year: {0}<br>"
                        + "Campus: {1}<br>"
                        + "Cycle: {2}<br>"
                        + "Level: {3}",
                        [
                            frm.doc.academic_year,
                            frm.doc.campus,
                            frm.doc.admission_cycle,
                            frm.doc.program_level
                        ]
                    ),
                    () => {
                        // ── Yes → call server method ────────────────────────
                        frm.call({
                            method: "generate_interview_list",
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __("Generating Interview List… Please wait"),
                            callback: (r) => {
                                if (r.message) {
                                    frm.reload_doc();
                                }
                            }
                        });
                    },
                    () => {
                        // No → do nothing
                    }
                );

            }, __("Actions"))
                .addClass("btn-primary")
                .css({ "font-weight": "bold" });
        }

        // ── "View Interview List" button ──────────────────────────────────────
        // Visible when the list has already been generated
        if (["Completed"].includes(frm.doc.status)) {
            frm.add_custom_button(__("View Interview List"), function () {
                frappe.db.get_value("Interview List", {
                    academic_year: frm.doc.academic_year,
                    campus: frm.doc.campus,
                    admission_cycle: frm.doc.admission_cycle,
                    program_level: frm.doc.program_level
                }, "name", (r) => {
                    if (r && r.name) {
                        frappe.set_route("Form", "Interview List", r.name);
                    } else {
                        frappe.msgprint(__("Associated Interview List not found."));
                    }
                });
            }, __("Actions"));
        }
    },

    // Re-evaluate button visibility on field changes
    academic_year: function (frm) { frm.trigger("refresh"); },
    campus: function (frm) { frm.trigger("refresh"); },
    admission_cycle: function (frm) { frm.trigger("refresh"); },
    program_level: function (frm) { frm.trigger("refresh"); },
    status: function (frm) { frm.trigger("refresh"); }

});
