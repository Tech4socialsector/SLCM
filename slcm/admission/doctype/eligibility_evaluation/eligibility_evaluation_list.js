frappe.listview_settings["Eligibility Evaluation"] = {
    refresh: function (listview) {
        if (!listview.page.wrapper.find(".btn-update-status").length) {
            const btn = listview.page.add_inner_button(__("Update Status"), function () {
                const d = new frappe.ui.Dialog({
                    title: __("Update Applicant Status from Evaluations"),
                    fields: [
                        {
                            label: __("Campus"),
                            fieldname: "campus",
                            fieldtype: "Link",
                            options: "Campus",
                            reqd: 1,
                        },
                        {
                            label: __("Academic Year"),
                            fieldname: "academic_year",
                            fieldtype: "Link",
                            options: "Academic Year",
                            reqd: 1,
                        },
                        {
                            label: __("Admission Cycle"),
                            fieldname: "admission_cycle",
                            fieldtype: "Link",
                            options: "Admission Cycle",
                            reqd: 1,
                        },
                        {
                            label: __("Program Level"),
                            fieldname: "program_level",
                            fieldtype: "Select",
                            options: "Undergraduate\nPostgraduate\nResearch Course",
                            reqd: 1,
                        },
                    ],
                    primary_action_label: __("Update Status"),
                    primary_action(values) {
                        frappe.call({
                            method:
                                "slcm.admission.doctype.eligibility_evaluation.eligibility_evaluation.update_applicant_status_from_evaluations",
                            args: values,
                            freeze: true,
                            freeze_message: __("Updating Applicant statuses..."),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.msgprint(
                                        __("Updated application status for {0} applicant(s).", [
                                            r.message || 0,
                                        ])
                                    );
                                    d.hide();
                                    listview.refresh();
                                }
                            },
                        });
                    },
                });
                d.show();
            });
            btn.addClass("btn-update-status");
        }
    },
};
