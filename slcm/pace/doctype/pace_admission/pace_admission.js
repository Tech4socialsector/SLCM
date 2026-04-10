// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PACE Admission", {
	refresh(frm) {

	},
    onload(frm){
        frm.set_query("payment_receipt_template", function() {
            return {
                filters: {
                    'print_format_for': 'DocType',
                    'doc_type': 'Applicant Payment Receipt'
                }
            }
        })
    }
});
