frappe.listview_settings['Admission Result'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__('Sync Applicants'), function () {
            let d = new frappe.ui.Dialog({
                title: __('Sync Applicants to Results'),
                fields: [
                    {
                        label: __('Admission Cycle'),
                        fieldname: 'admission_cycle',
                        fieldtype: 'Link',
                        options: 'Admission Cycle',
                        reqd: 1
                    },
                    {
                        label: __('Campus'),
                        fieldname: 'campus',
                        fieldtype: 'Link',
                        options: 'Campus',
                        reqd: 1
                    },
                    {
                        label: __('Program Level'),
                        fieldname: 'program_level',
                        fieldtype: 'Select',
                        options: '\nUG\nPG\nPhD'
                    }
                ],
                primary_action_label: __('Sync'),
                primary_action(values) {
                    frappe.call({
                        method: 'slcm.admission.doctype.admission_result.admission_result.bulk_sync_from_applicants',
                        args: {
                            admission_cycle: values.admission_cycle,
                            campus: values.campus,
                            program_level: values.program_level
                        },
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint(__('Synced {0} applicants successfully.', [r.message]));
                                listview.refresh();
                                d.hide();
                            }
                        }
                    });
                }
            });
            d.show();
        });
    }
};
