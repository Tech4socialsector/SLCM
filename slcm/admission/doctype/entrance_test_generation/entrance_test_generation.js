frappe.ui.form.on("Entrance Test Generation", {

    refresh: function (frm) {

        // Remove any previously added buttons with the same label (safety)
        frm.remove_custom_button("Generate Test List");

        // Show button only when:
        // 1. Document is Draft (not submitted)
        // 2. Status is Draft or In Progress
        // 3. Required fields are filled (basic validation)

        if (
            !frm.is_new() &&                                    // Check if document is saved
            frm.doc.docstatus === 0 &&                          // still draft / not submitted
            ["Draft", "In Progress"].includes(frm.doc.status || "Draft") &&
            frm.doc.academic_year &&
            frm.doc.campus &&
            frm.doc.admission_cycle
            // you can add more required checks if needed → && frm.doc.program_level
        ) {
            frm.add_custom_button(__("Generate Test List"), function () {

                // Optional: extra client-side confirmation / validation
                if (!frm.doc.program_level) {
                    frappe.throw("Please select Program Level before generating");
                    return;
                }

                frappe.confirm(
                    __(
                        "Generate Entrance Test List for this configuration?<br><br>"
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
                        // Start generation
                        frm.call({
                            method: "generate_test_list",
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __("Generating Entrance Test List... Please wait"),
                            callback: (r) => {
                                if (r.message) {
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );


            }, __("Actions"))
                .addClass("btn-primary")
                .css({ "font-weight": "bold" });
        }

        // Remove and Add "View Entrance Test List" button when status is Completed or Allocation Done
        frm.remove_custom_button("View Entrance Test List");
        if (["Completed", "Allocation Done"].includes(frm.doc.status)) {
            frm.add_custom_button(__("View Entrance Test List"), function () {
                frappe.db.get_value("Entrance Test List", {
                    academic_year: frm.doc.academic_year,
                    campus: frm.doc.campus,
                    admission_cycle: frm.doc.admission_cycle,
                    program_level: frm.doc.program_level
                }, "name", (r) => {
                    if (r && r.name) {
                        frappe.set_route("Form", "Entrance Test List", r.name);
                    } else {
                        frappe.msgprint(__("Associated Entrance Test List not found."));
                    }
                });
            }, __("Actions"));
        }
    },

    // Optional: refresh button visibility when these fields change
    academic_year: function (frm) { frm.trigger("refresh"); },
    campus: function (frm) { frm.trigger("refresh"); },
    admission_cycle: function (frm) { frm.trigger("refresh"); },
    program_level: function (frm) { frm.trigger("refresh"); },
    status: function (frm) { frm.trigger("refresh"); }

});