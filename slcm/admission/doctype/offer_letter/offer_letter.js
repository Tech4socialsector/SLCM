// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Offer Letter", {

    refresh(frm) {
        if (frm.fields_dict['rendered_content']) {
            frm.set_df_property('rendered_content', 'options', frm.doc.rendered_content);
            // Optional: Set the field to read-only to enforce preview
            frm.set_df_property('rendered_content', 'read_only', 1);
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



