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
        })
    }
});
