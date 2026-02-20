
frappe.ui.form.on('Applicant Fee Assignment', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status !== "Converted") {
            frm.add_custom_button(__('Create Invoice & Convert Student'), function () {
                frappe.confirm(__('This action will create a Student Master, Enrollment, and Fee Invoice. Continue?'),
                    function () {
                        frappe.call({
                            method: 'slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment.create_invoice',
                            args: {
                                docname: frm.doc.name
                            },
                            callback: function (r) {
                                if (r.message) {
                                    frappe.msgprint(__('Fee Invoice {0} created and Student converted successfully.', [r.message]));
                                    frm.reload_doc();
                                }
                            }
                        });
                    });
            }).addClass('btn-primary');
        }

        if (frm.doc.fee_invoice) {
            frm.add_custom_button(__('View Fee Invoice'), function () {
                frappe.set_route('Form', 'Fee Invoice', frm.doc.fee_invoice);
            }, __('View'));

            frm.add_custom_button(__('View Payment History'), function () {
                frappe.set_route('List', 'Fee Payment', {
                    fee_invoice: frm.doc.fee_invoice
                });
            }, __('View'));
        }
    }
});

frappe.ui.form.on('Applicant Fee Component Child', {
    amount: function (frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    },
    fee_component: function (frm, cdt, cdn) {
        // Child table fetch_from handles field update, but we need to trigger calculation
        // Since fetch_from is async on the client, we might need a small timeout or rely on server-side validation
        // For better UX, we can manually fetch if needed, but let's try to trigger it
        setTimeout(() => {
            calculate_row_total(frm, cdt, cdn);
        }, 100);
    }
});

function calculate_row_total(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    if (row.is_taxable) {
        row.tax_amount = flt(row.amount) * flt(row.tax_rate) / 100;
    } else {
        row.tax_amount = 0;
    }
    row.total_amount = flt(row.amount) + flt(row.tax_amount);
    frm.refresh_field('fee_components');

    calculate_grand_total(frm);
}

function calculate_grand_total(frm) {
    let total = 0;
    (frm.doc.fee_components || []).forEach(row => {
        total += flt(row.total_amount);
    });
    frm.set_value('total_amount', total);
}
