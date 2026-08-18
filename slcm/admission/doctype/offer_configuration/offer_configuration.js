// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Offer Configuration", {
    refresh(frm) {
        // Disable past dates in the datepicker for offer_expiry_date
        frm.fields_dict.due_date.datepicker.update({
            minDate: new Date(frappe.datetime.get_today())
        });
    },
    onload: function (frm) {
        frm.set_query('pdf_format', function () {
            return {
                filters: {
                    'print_format_for': 'DocType',
                    'doc_type': 'Offer Letter'
                }
            }
        }),
            frm.set_query('admission_cycle', function () {
                return {
                    filters: {
                        'status': 'Active'
                    }
                }
            }),
            frm.set_query('fee_structure', function () {
                return {
                    filters: {
                        'status': 'Active',
                        'applicable': 'Applicant'
                    }
                }
            })
    }
});

