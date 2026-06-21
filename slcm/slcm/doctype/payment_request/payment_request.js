// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Payment Request", {
	refresh(frm) {
        if (frm.doc.status !== "Paid" && frm.doc.status !== "Cancelled" && frm.doc.payment_gateway === "Razorpay") {
            frm.add_custom_button(__("Reconcile with Razorpay"), function() {
                frappe.call({
                    method: "slcm.api.service.fee_service.reconcile_single_payment",
                    args: {
                        payment_request_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: r.message.message || __("Reconciliation triggered."),
                                indicator: r.message.status === "success" ? "green" : r.message.status === "info" ? "blue" : "red"
                            });
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
	},
});
