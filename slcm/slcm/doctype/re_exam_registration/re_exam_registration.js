// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Re Exam Registration", {
    refresh(frm) {
        if (frm.is_new()) return;

        // ── Status indicator colour ───────────────────────────────────
        const statusColors = {
            "Registered":        "blue",
            "Payment Initiated": "yellow",
            "Authorized":        "yellow",
            "Paid":              "green",
            "Payment Failed":    "red",
            "Refunded":          "orange",
            "Cancelled":         "gray",
        };
        if (frm.doc.status && statusColors[frm.doc.status]) {
            frm.page.set_indicator(frm.doc.status, statusColors[frm.doc.status]);
        }

        // ── View Payment Log (always visible) ────────────────────────
        frm.add_custom_button(__("View Payment Log"), function () {
            frappe.set_route("List", "Re Exam Payment Log", {
                re_exam_registration: frm.doc.name,
            });
        }).addClass("btn-primary");

        // ── Mark as Paid (visible when payment is not yet settled) ───
        if (!["Paid", "Cancelled", "Refunded"].includes(frm.doc.status)) {
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
                                    status: "Paid",
                                    payment_reference: values.payment_reference || "",
                                },
                            },
                            freeze: true,
                            freeze_message: __("Updating…"),
                            callback: function () {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __("Status updated to Paid"),
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

        // ── Mark as Cancelled (visible when not already terminal) ────
        if (!["Paid", "Cancelled", "Refunded"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Cancel Registration"), function () {
                frappe.confirm(
                    __("Are you sure you want to cancel this registration?"),
                    function () {
                        frappe.call({
                            method: "frappe.client.set_value",
                            args: {
                                doctype: "Re Exam Registration",
                                name: frm.doc.name,
                                fieldname: { status: "Cancelled" },
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
