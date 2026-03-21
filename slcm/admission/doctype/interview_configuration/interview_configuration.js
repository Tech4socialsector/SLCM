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
            !frm.is_new() &&
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
                        `<div style="text-align: center; padding: 10px;">
                            <div style="background: #eef2f7; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px;">
                                <i class="fa fa-info-circle fa-2x" style="color: #007bff;"></i>
                            </div>
                            <h4 style="font-weight: 800; color: #212529; margin-bottom: 10px;">Confirm Generation</h4>
                            <p style="color: #6c757d; font-size: 14px; line-height: 1.5;">Are you sure you want to generate the Interview list with the following configuration?</p>
                            
                            <div style="background: #fff; border: 1.5px solid #f1f3f5; border-radius: 12px; padding: 16px; margin: 24px 0; text-align: left;">
                                <table style="width: 100%; font-size: 13px; border-collapse: separate; border-spacing: 0 8px;">
                                    <tr><td style="color: #adb5bd; font-weight: 500;">Academic Year</td><td style="font-weight: 700; text-align: right; color: #495057;">{0}</td></tr>
                                    <tr><td style="color: #adb5bd; font-weight: 500;">Campus</td><td style="font-weight: 700; text-align: right; color: #495057;">{1}</td></tr>
                                    <tr><td style="color: #adb5bd; font-weight: 500;">Admission Cycle</td><td style="font-weight: 700; text-align: right; color: #495057;">{2}</td></tr>
                                    <tr><td style="color: #adb5bd; font-weight: 500;">Program Level</td><td style="font-weight: 700; text-align: right; color: #495057;">{3}</td></tr>
                                </table>
                            </div>
                            <p style="font-size: 12px; color: #adb5bd; font-style: italic;">This process will only fetch new eligible candidates.</p>
                        </div>`,
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
