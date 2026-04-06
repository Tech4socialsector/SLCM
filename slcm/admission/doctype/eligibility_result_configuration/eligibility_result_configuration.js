frappe.ui.form.on("Eligibility Result Configuration", {
    onload: function (frm) {
        frm.set_query("admission_cycle", function () {
            return {
                filters: {
                    "status": "Active"
                }
            };
        });
    },

    refresh: function (frm) {
        if (!frm.is_new() && frm.doc.docstatus === 0 && ["Draft", "In Progress", "Failed"].includes(frm.doc.status) &&
            frm.doc.academic_year && frm.doc.campus && frm.doc.admission_cycle && frm.doc.program_level) {

            frm.add_custom_button(__("Generate Result"), function () {
                frappe.confirm(__("Generate Eligibility Results for the selected criteria?"), function () {
                    frm.call({
                        method: "generate_result",
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __("Starting result generation..."),
                        callback: function (r) {
                            if (r.message && typeof r.message === 'object') {
                                let m = r.message;
                                let msg = `
                                    <div style="padding: 10px;">
                                        <div style="font-size: 16px; font-weight: 600; color: #16a34a; margin-bottom: 12px;">
                                            <i class="fa fa-check-circle"></i> Successfully generated ${m.total} records
                                        </div>
                                        <div style="background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 15px;">
                                            <table style="width: 100%; font-size: 13px;">
                                                <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 6px 0; color: #64748b;">Interview Pass</td><td style="padding: 6px 0; font-weight: 700; text-align: right;">${m.interview_pass}</td></tr>
                                                <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 6px 0; color: #64748b;">ET Pass (Interview Exempt)</td><td style="padding: 6px 0; font-weight: 700; text-align: right;">${m.et_pass_exempt}</td></tr>
                                                <tr><td style="padding: 6px 0; color: #64748b;">Dual Exempted</td><td style="padding: 6px 0; font-weight: 700; text-align: right;">${m.dual_exempt}</td></tr>
                                            </table>
                                        </div>
                                        <p style="margin-top: 15px; font-size: 12px; color: #94a3b8;">
                                            Eligibility Results are now available in the portal and for download.
                                        </p>
                                    </div>
                                `;
                                frappe.msgprint({
                                    title: __("Generation Complete"),
                                    indicator: "green",
                                    message: msg,
                                    wide: true
                                });
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