// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Offer Configuration", {
    refresh(frm) {

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
        })
    }
});
