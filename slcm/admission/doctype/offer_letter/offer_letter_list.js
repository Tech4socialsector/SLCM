frappe.listview_settings['Offer Letter'] = {
    add_fields: ["offer_status", "payable_amount"],
    get_indicator: function (doc) {
        if (doc.offer_status === "Payment Completed") {
            return [__("Paid"), "blue", "offer_status,=,Payment Completed"];
        } else if (doc.offer_status === "Accepted") {
            return [__("Accepted"), "green", "offer_status,=,Accepted"];
        }
    },
    refresh: function (listview) {
        // Add a bulk action or individual button logic if needed
    },
    onload: function (listview) {
        listview.page.add_action_item(__("Pay Fees (Online)"), function () {
            const selected = listview.get_checked_items();
            if (selected.length !== 1) {
                frappe.msgprint(__("Please select exactly one offer to pay."));
                return;
            }
            const offer = selected[0];
            if (offer.offer_status === "Payment Completed") {
                frappe.msgprint(__("Payment already completed for this offer."));
                return;
            }

            frappe.dom.freeze(__('Redirecting...'));
            frappe.call({
                method: "slcm.api.service.offer_service.get_online_payment_url",
                args: {
                    offer_name: offer.name
                },
                callback: function (r) {
                    frappe.dom.unfreeze();
                    if (r.message) {
                        window.location.href = r.message;
                    }
                }
            });
        });
    }
};
