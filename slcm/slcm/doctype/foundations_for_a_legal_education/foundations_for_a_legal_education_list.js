frappe.ui.form.on('Foundations for a Legal Education', {
    refresh: function (frm) {
        if (!frm.is_new()) {
            let btn = frm.add_custom_button('Payment Log', function () {
                frappe.set_route('List', 'FLE Payment Log', {
                    reference_no: frm.doc.name
                });
            });

            // Make button black
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