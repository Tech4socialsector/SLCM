// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Offer Letter", {

    refresh(frm) {
        if (frm.doc.rendered_content) {
            // Force the field to display as rendered HTML instead of an editor or raw code
            frm.set_df_property('rendered_content', 'fieldtype', 'HTML');
            frm.set_df_property('rendered_content', 'options', frm.doc.rendered_content);
        }

        if (frm.doc.offer_status === "Issued") {
            frm.add_custom_button(__('Send Reminder'), function () {
                const offers = [{
                    name: frm.doc.name,
                    applicant_name: frm.doc.applicant,
                    program: frm.doc.program,
                    payment_deadline: frm.doc.payment_deadline
                }];

                frappe.require('offer_letter_list.js', () => {
                    slcm.utils.show_offer_reminder_dialog(offers);
                });
            });
        }
        frm.fields_dict.accepted_on.datepicker.update({
            minDate: new Date(frappe.datetime.get_today()),
        });

        if (frm.doc.offer_status === "Accepted") {
            frm.add_custom_button(__('Record Manual Payment'), function () {
                if (frm.doc.offer_status === "Payment Completed") {
                    frappe.msgprint(__('Fee has already been paid for this offer.'));
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
                        frappe.confirm(__('Are you sure you want to record this {0} payment of {1}?', [values.payment_mode, format_currency(frm.doc.payable_amount)]), () => {
                            frappe.call({
                                method: 'slcm.api.service.fee_service.process_fee_payment',
                                args: {
                                    offer_name: frm.doc.name,
                                    payment_mode: values.payment_mode,
                                    reference_number: values.transaction_id,
                                    bank_name: values.bank_name,
                                    cheque_number: values.cheque_number,
                                    cheque_date: values.cheque_date,
                                    upi_id: values.upi_id,
                                    remarks: values.remarks
                                },
                                freeze: true,
                                freeze_message: __("Recording Payment..."),
                                callback: function (r) {
                                    if (r.message && !r.exc) {
                                        d.hide();
                                        frappe.msgprint({
                                            title: __('Payment Status'),
                                            message: __('Payment recorded successfully. Receipt <b>{0}</b> has been generated.', [r.message]),
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
    },
    onload: function (frm) {
        // Disable past dates in the payment_deadline datepicker
        frm.set_df_property('payment_deadline', 'datepicker_options', {
            minDate: frappe.datetime.now_date()
        });
    },

    validate(frm) {
        // Ensure payment_deadline is not in the past during validation
        if (frm.doc.payment_deadline && frm.doc.payment_deadline < frappe.datetime.now_datetime()) {
            frappe.throw(__('Payment Deadline cannot be in the past. Please select a future date and time.'));
        }

        /**
         * Requirement: Show dialog when updating a record that is already Issued.
         * The reason must be captured and sent to the action log.
         */

        // Conditions for prompting:
        // 1. Record is not new (updating)
        // 2. Status is Issued or beyond (locked state)
        // 3. Document has changes (dirty)
        // 4. Reason hasn't been captured yet
        if (!frm.is_new() && frm.doc.offer_status !== "Draft" && frm.is_dirty() && !frm.doc.edit_reason) {

            frappe.prompt([
                {
                    label: 'Reason for Modification',
                    fieldname: 'reason',
                    fieldtype: 'Small Text',
                    reqd: 1
                }
            ], (values) => {
                // Set the reason on the doc object so it reaches the server controller
                frm.doc.edit_reason = values.reason;

                // Re-trigger save with the reason attached
                frm.save();
            }, __('Modification Audit Reason Required'), __('Submit'));

            // Stop the current save process to wait for the dialog
            frappe.validated = false;
        }
    },

    after_save(frm) {
        // Clean up the transient reason after successful save
        if (frm.doc.edit_reason) {
            delete frm.doc.edit_reason;
        }
    }
});



