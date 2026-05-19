
frappe.ui.form.on('Applicant Fee Assignment', {
    after_save: function (frm) {
        if (frm.doc.fee_type === 'Application Fee') {
            frm.reload_doc();
        }
    },
    refresh: function (frm) {
        if (frm.doc.applicant && frm.doc.fee_type === 'Application Fee' && frm.doc.name) {
            frm.add_custom_button(__('Sync rows from applicant'), function () {
                frappe.call({
                    method: 'slcm.api.service.application_fee_service.desk_resync_application_fee_assignment',
                    args: { afa_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __('Updating fee components...'),
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('Fee components updated from applicant.'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Actions'));
        }

        if (frm.doc.docstatus === 1 && ["Partially Paid", "Paid"].includes(frm.doc.status) && frm.doc.fee_type === "Admission Fee") {
            frm.add_custom_button(__('Convert to Student'), function () {
                frappe.confirm(__('This action will create a Student Master, Enrollment, and Fee Invoice. Continue?'),
                    function () {
                        Promise.all([
                            frappe.db.get_value("Email Account", { default_outgoing: 1 }, "name"),
                            frappe.db.get_value("Email Template", { name: "Student Admission Confirmation" }, "name")
                        ]).then(results => {
                            const default_account = results[0] && results[0].message ? results[0].message.name : "";
                            const default_template = results[1] && results[1].message ? results[1].message.name : "";

                            const d = new frappe.ui.Dialog({
                                title: __("Notification Settings"),
                                fields: [
                                    {
                                        label: __("Email Account"),
                                        fieldname: "email_account",
                                        fieldtype: "Link",
                                        options: "Email Account",
                                        reqd: 1,
                                        default: default_account
                                    },
                                    {
                                        label: __("Email Template"),
                                        fieldname: "email_template",
                                        fieldtype: "Link",
                                        options: "Email Template",
                                        reqd: 1,
                                        default: default_template
                                    }
                                ],
                                primary_action_label: __("Convert"),
                                primary_action: function (values) {
                                    d.hide();
                                    frappe.call({
                                        method: 'slcm.admission.doctype.applicant_fee_assignment.applicant_fee_assignment.create_invoice',
                                        args: {
                                            docname: frm.doc.name,
                                            email_template: values.email_template,
                                            email_account: values.email_account
                                        },
                                        freeze: true,
                                        freeze_message: __('Converting applicant to student...'),
                                        callback: function (r) {
                                            if (r.message) {
                                                frappe.msgprint(__('Fee Invoice {0} created and Student converted successfully.', [r.message]));
                                                frm.reload_doc();
                                            }
                                        }
                                    });
                                }
                            });
                            d.show();
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

        if (frm.doc.docstatus === 1 && ["Assigned", "Partially Paid"].includes(frm.doc.status) && frm.doc.fee_type === "Admission Fee" && frm.doc.offer_letter) {
            frm.add_custom_button(__('Record Manual Payment'), function () {
                if (frm.doc.status === "Paid") {
                    frappe.msgprint(__('Fee has already been paid for this assignment.'));
                    return;
                }

                let d = new frappe.ui.Dialog({
                    title: __('Record Manual Payment'),
                    fields: [
                        {
                            label: __('Payment Mode'),
                            fieldname: 'payment_mode',
                            fieldtype: 'Select',
                            options: 'Cash\nCheque\nUPI\nQR Code\nBank Transfer\nDemand Draft',
                            default: 'Cash',
                            reqd: 1
                        },
                        {
                            label: __('Reference No / TXN ID'),
                            fieldname: 'transaction_id',
                            fieldtype: 'Data',
                            depends_on: 'eval:doc.payment_mode !== "Cash"'
                        },
                        {
                            label: __('Bank Name'),
                            fieldname: 'bank_name',
                            fieldtype: 'Data',
                            depends_on: 'eval:["Cheque", "Bank Transfer", "Demand Draft"].includes(doc.payment_mode)'
                        },
                        {
                            label: __('Cheque Number'),
                            fieldname: 'cheque_number',
                            fieldtype: 'Data',
                            depends_on: 'eval:doc.payment_mode === "Cheque"'
                        },
                        {
                            label: __('Cheque Date'),
                            fieldname: 'cheque_date',
                            fieldtype: 'Date',
                            depends_on: 'eval:doc.payment_mode === "Cheque"'
                        },
                        {
                            label: __('UPI ID'),
                            fieldname: 'upi_id',
                            fieldtype: 'Data',
                            depends_on: 'eval:["UPI", "QR Code"].includes(doc.payment_mode)'
                        },
                        {
                            label: __('Remarks'),
                            fieldname: 'remarks',
                            fieldtype: 'Small Text'
                        }
                    ],
                    primary_action_label: __('Submit Payment'),
                    primary_action(values) {
                        frappe.confirm(__('Are you sure you want to record this {0} payment of {1}?', [values.payment_mode, format_currency(frm.doc.total_amount)]), () => {
                            frappe.call({
                                method: 'slcm.api.service.fee_service.process_fee_payment',
                                args: {
                                    offer_name: frm.doc.offer_letter,
                                    payment_mode: values.payment_mode,
                                    reference_number: values.transaction_id,
                                    bank_name: values.bank_name,
                                    cheque_number: values.cheque_number,
                                    cheque_date: values.cheque_date,
                                    upi_id: values.upi_id,
                                    remarks: values.remarks
                                },
                                callback: function (r) {
                                    if (!r.exc) {
                                        d.hide();
                                        frappe.show_alert({
                                            message: __('Payment recorded successfully. Receipt {0} generated.', [r.message]),
                                            indicator: 'green'
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        });
                    }
                });
                d.show();
            }, __('Actions'));
        }

        // ── Filter Scholarship Application ──────────────────────────────────────
        if (frm.doc.applicant) {
            frm.set_query('scholarship_application', function () {
                return {
                    filters: {
                        applicant_id: frm.doc.applicant,
                        status: 'Approved'
                    }
                };
            });
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
