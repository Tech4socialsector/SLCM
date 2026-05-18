frappe.ui.form.on("Improvement Exam Payment Log", {
    refresh(frm) {
        if (frm.is_new()) return;

        // ── Open Registration ─────────────────────────────────────────
        if (frm.doc.improvement_exam_registration) {
            frm.add_custom_button(__("Open Registration"), function () {
                frappe.set_route("Form", "Improvement Exam Registration", frm.doc.improvement_exam_registration);
            }).css({ "background-color": "#1e293b", "color": "#fff", "border-color": "#1e293b" });
        }

        // ── Download Receipt (only when Paid) ─────────────────────────
        if (["Paid", "Captured"].includes(frm.doc.payment_status) && frm.doc.improvement_exam_registration) {
            frm.add_custom_button(__("Download Receipt"), function () {
                const url = `/printview?doctype=Improvement%20Exam%20Registration&name=${encodeURIComponent(frm.doc.improvement_exam_registration)}&format=Improvement%20Exam%20Receipt&trigger_print=0`;
                window.open(url, "_blank");
            }).css({ "background-color": "#0f766e", "color": "#fff", "border-color": "#0f766e" });
        }

        // ── Status indicator ──────────────────────────────────────────
        const statusColors = {
            "Payment Initiated": "yellow",
            "Authorized":        "yellow",
            "Paid":              "green",
            "Captured":          "green",
            "Failed":            "red",
            "Refunded":          "orange",
            "Cancelled":         "gray",
        };
        const color = statusColors[frm.doc.payment_status] || "blue";
        frm.page.set_indicator(frm.doc.payment_status || "Draft", color);
    },
});
