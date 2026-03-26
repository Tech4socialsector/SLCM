// ===============================
// LIST VIEW — Download buttons in Actions dropdown
// ===============================

frappe.listview_settings["Foundations for a Legal Education"] = {
    onload: function (listview) {
        listview.page.add_action_item(__("Download Receipt"), function () {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__("Please select at least one record."));
                return;
            }
            selected.forEach(function (doc) {
                const url =
                    "/api/method/slcm.api.user.download_fle_receipt?docname=" +
                    encodeURIComponent(doc.name);
                const a = document.createElement("a");
                a.href = url;
                a.target = "_blank";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            });
        });

        listview.page.add_action_item(__("Download Application"), function () {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__("Please select at least one record."));
                return;
            }
            selected.forEach(function (doc) {
                const url =
                    "/api/method/slcm.api.user.download_fle_application_pdf?docname=" +
                    encodeURIComponent(doc.name);
                const a = document.createElement("a");
                a.href = url;
                a.target = "_blank";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            });
        });
    },
};

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

            // Download Receipt button
            let receiptBtn = frm.add_custom_button(__('Download Receipt'), function () {
                const url = '/api/method/slcm.api.user.download_fle_receipt?docname='
                    + encodeURIComponent(frm.doc.name);
                window.open(url, '_blank');
            });
            $(receiptBtn).removeClass('btn-default')
                .css({
                    "background-color": "#a81119",
                    "color": "white",
                    "border-color": "#a81119"
                });

            // Download Application button
            let appBtn = frm.add_custom_button(__('Download Application'), function () {
                const url = '/api/method/slcm.api.user.download_fle_application_pdf?docname='
                    + encodeURIComponent(frm.doc.name);
                window.open(url, '_blank');
            });
            $(appBtn).removeClass('btn-default')
                .css({
                    "background-color": "#a81119",
                    "color": "white",
                    "border-color": "#a81119"
                });
        }
    }
});
