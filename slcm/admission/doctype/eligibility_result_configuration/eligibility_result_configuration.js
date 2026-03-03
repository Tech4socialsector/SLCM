frappe.ui.form.on("Eligibility Result Configuration", {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 && ["Draft", "In Progress", "Failed"].includes(frm.doc.status) &&
            frm.doc.academic_year && frm.doc.campus && frm.doc.admission_cycle && frm.doc.program_level) {

            frm.add_custom_button(__("Generate Result"), function () {
                frappe.confirm(__("Generate Eligibility Results for the selected criteria?"), function () {
                    frm.call({
                        method: "generate_result",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Generating Results..."),
                        callback: function (r) {
                            if (r.message) {
                                frm.reload_doc();
                            }
                        }
                    });
                });
            }).addClass("btn-primary");
        }
    },

    academic_year: function (frm) { frm.trigger("refresh"); },
    campus: function (frm) { frm.trigger("refresh"); },
    admission_cycle: function (frm) { frm.trigger("refresh"); },
    program_level: function (frm) { frm.trigger("refresh"); },
    status: function (frm) { frm.trigger("refresh"); }
});
