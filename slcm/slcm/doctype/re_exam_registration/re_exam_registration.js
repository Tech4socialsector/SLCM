// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Re Exam Registration", {
    refresh(frm) {
        if (frm.is_new()) return;

        // ── Status indicator colour ───────────────────────────────────
        const paymentColors = {
            "Pending":            "blue",
            "Payment Initiated":  "yellow",
            "Payment Cancelled":  "orange",
            "Authorized":         "yellow",
            "Paid":               "green",
            "Payment Failed":     "red",
            "Refunded":           "orange",
            "Cancelled":          "gray",
        };

        let indicatorLabel, indicatorColor;
        if (frm.doc.status === "Cancelled") {
            indicatorLabel = "Cancelled";
            indicatorColor = "gray";
        } else if (frm.doc.payment_status && paymentColors[frm.doc.payment_status]) {
            indicatorLabel = frm.doc.payment_status;
            indicatorColor = paymentColors[frm.doc.payment_status];
        } else {
            indicatorLabel = "Registered";
            indicatorColor = "blue";
        }
        frm.page.set_indicator(indicatorLabel, indicatorColor);

        // ── View Payment Log (always visible) ────────────────────────
        frm.add_custom_button(__("View Payment Log"), function () {
            frappe.set_route("List", "Re Exam Payment Log", {
                re_exam_registration: frm.doc.name,
            });
        }).addClass("btn-primary");

        // ── Download Receipt (visible when Paid) ─────────────────────
        if (["Paid", "Captured"].includes(frm.doc.payment_status)) {
            frm.add_custom_button(__("Download Receipt"), function () {
                const url = `/printview?doctype=Re%20Exam%20Registration&name=${encodeURIComponent(frm.doc.name)}&format=Re%20Exam%20Receipt&trigger_print=0`;
                window.open(url, "_blank");
            }).css({ "background-color": "#1e293b", "color": "#fff", "border-color": "#1e293b" });
        }

        const isTerminal = ["Paid", "Cancelled", "Refunded"].includes(frm.doc.payment_status)
            || frm.doc.status === "Cancelled";

        // ── Mark as Paid (visible when not terminal) ─────────────────
        if (!isTerminal) {
            frm.add_custom_button(__("Mark as Paid"), function () {
                frappe.prompt(
                    {
                        label: __("Payment Reference"),
                        fieldname: "payment_reference",
                        fieldtype: "Data",
                        reqd: 0,
                        description: __("Cheque / DD number or any offline reference"),
                    },
                    function (values) {
                        frappe.call({
                            method: "frappe.client.set_value",
                            args: {
                                doctype: "Re Exam Registration",
                                name: frm.doc.name,
                                fieldname: {
                                    payment_status:    "Paid",
                                    payment_reference: values.payment_reference || "",
                                },
                            },
                            freeze: true,
                            freeze_message: __("Updating…"),
                            callback: function () {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __("Payment status updated to Paid"),
                                    indicator: "green",
                                });
                            },
                        });
                    },
                    __("Mark as Paid"),
                    __("Confirm")
                );
            }).addClass("btn-success");
        }

        // ── Cancel Registration (visible when not terminal) ──────────
        if (!isTerminal) {
            frm.add_custom_button(__("Cancel Registration"), function () {
                frappe.confirm(
                    __("Are you sure you want to cancel this registration?"),
                    function () {
                        frappe.call({
                            method: "frappe.client.set_value",
                            args: {
                                doctype: "Re Exam Registration",
                                name: frm.doc.name,
                                fieldname: {
                                    status:         "Cancelled",
                                    payment_status: "Cancelled",
                                },
                            },
                            freeze: true,
                            freeze_message: __("Cancelling…"),
                            callback: function () {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __("Registration cancelled"),
                                    indicator: "orange",
                                });
                            },
                        });
                    }
                );
            }).addClass("btn-danger");
        }
    },
});
