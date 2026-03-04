// ===============================
// FORM VIEW BUTTON
// Opens specific Payment Log record directly
// ===============================

frappe.ui.form.on('Foundations for a Legal Education', {
    refresh: function (frm) {

        if (!frm.is_new()) {

            let btn = frm.add_custom_button('Payment Log', function () {

                // Find linked Payment Log record
                frappe.db.get_value(
                    'FLE Payment Log',
                    { reference_no: frm.doc.name },
                    'name'
                ).then(r => {

                    if (r && r.message && r.message.name) {
                        // Open specific record directly
                        frappe.set_route('Form', 'FLE Payment Log', r.message.name);
                    } else {
                        frappe.msgprint(__('No Payment Log Found'));
                    }

                });

            });

            // Black Button Styling
            $(btn).removeClass('btn-default')
                .addClass('btn-dark')
                .css({
                    "background-color": "black",
                    "color": "white",
                    "border-color": "black"
                });
        }
    }
});
