// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Offer Configuration", {
    refresh(frm) {
        // Disable past dates in the datepicker for offer_expiry_date
        frm.fields_dict.offer_expiry_date.datepicker.update({
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
            frm.set_query('email_template', function () {
                return {
                    filters: {
                        'template_for_offer_letter': 1
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

frappe.ui.form.on("Offer Letter PDF", {
    program: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let duplicate = (frm.doc.offer_letter_pdf || []).find(d => d.program === row.program && d.name !== row.name);
        if (duplicate) {
            frappe.msgprint({
                title: __('Duplicate Program'),
                message: __('Program {0} is already added in another row.', [row.program.bold()]),
                indicator: 'orange'
            });
            frappe.model.set_value(cdt, cdn, 'program', '');
        }
    }
});
