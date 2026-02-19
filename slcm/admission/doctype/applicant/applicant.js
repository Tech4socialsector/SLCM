// frappe.ui.form.on('Applicant', {

//     refresh: function(frm) {
//         // No longer manage evaluation_status field - it's in Eligibility Evaluation
//     },

//     after_save: function(frm) {
//         // Eligibility Evaluation record is created automatically in Python after_insert/on_update
//         frappe.msgprint({
//             title: __('Applicant Saved'),
//             message: __('Applicant details have been saved. Eligibility evaluation has been recorded.'),
//             indicator: 'green'
//         });
//     }

// });
