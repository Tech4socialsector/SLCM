// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Entrance Test', {
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
        if (!frm.is_new()) {
            // Add Export Marks Template custom button
            frm.add_custom_button(__('Export Marks Template'), function () {
                open_export_marks_dialog({
                    academic_year: frm.doc.academic_year,
                    admission_cycle: frm.doc.admission_cycle,
                    campus: frm.doc.campus,
                    entrance_test: frm.doc.name
                });
            });
        }
    }
});

/**
 * Dialog to export marks template with filters & shortlisted option
 */
function open_export_marks_dialog(defaults = {}) {
    let d = new frappe.ui.Dialog({
        title: __('Export Entrance Test Marks Template'),
        fields: [
            {
                label: __('Academic Year'),
                fieldname: 'academic_year',
                fieldtype: 'Link',
                options: 'Academic Year',
                default: defaults.academic_year || ''
            },
            {
                label: __('Admission Cycle'),
                fieldname: 'admission_cycle',
                fieldtype: 'Link',
                options: 'Admission Cycle',
                default: defaults.admission_cycle || ''
            },
            {
                label: __('Campus'),
                fieldname: 'campus',
                fieldtype: 'Link',
                options: 'Campus',
                default: defaults.campus || ''
            },
            {
                label: __('Programme Level'),
                fieldname: 'program_level',
                fieldtype: 'Select',
                options: '\nUndergraduate\nPostgraduate\nResearch Course',
                default: defaults.program_level || ''
            },
            {
                label: __('Programme'),
                fieldname: 'program',
                fieldtype: 'Link',
                options: 'Programme',
                default: defaults.program || ''
            },
            {
                label: __('Entrance Test'),
                fieldname: 'entrance_test',
                fieldtype: 'Link',
                options: 'Entrance Test',
                default: defaults.entrance_test || ''
            },
            {
                label: __('Shortlisted Only (Stage 2 - Part B)'),
                fieldname: 'shortlisted_only',
                fieldtype: 'Check',
                default: 0,
                description: __('Check this for Stage 2 (Part B marks entry) to export shortlisted applicants only with Part A marks pre-filled.')
            },
            {
                label: __('File Format'),
                fieldname: 'file_format',
                fieldtype: 'Select',
                options: 'xlsx\ncsv',
                default: 'xlsx',
                reqd: 1
            }
        ],
        primary_action_label: __('Export Template'),
        primary_action(values) {
            d.hide();
            frappe.show_alert({ message: __('Generating Marks Template...'), indicator: 'blue' });

            frappe.call({
                method: 'slcm.admission.utils.entrance_test_marks_manager.export_entrance_test_marks_template',
                args: values,
                freeze: true,
                freeze_message: __('Building Export File...'),
                callback: function (r) {
                    if (r.message && r.message.file_url) {
                        const link = document.createElement('a');
                        link.href = r.message.file_url;
                        link.download = r.message.filename || 'Marks_Template.xlsx';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);

                        frappe.show_alert({
                            message: __('Template downloaded successfully.'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    });

    d.set_query("admission_cycle", function () {
        return { filters: { "status": "Active" } };
    });

    d.show();
}
