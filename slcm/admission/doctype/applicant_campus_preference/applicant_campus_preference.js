frappe.ui.form.on("Applicant Campus Preference", {
    refresh: function(frm) {
        const status_colors = {
            "Pending": "gray",
            "Under Evaluation": "blue",
            "Shortlisted": "orange",
            "Interview Scheduled": "purple",
            "Offered": "green",
            "Accepted": "darkgreen",
            "Rejected": "red",
            "Waitlisted": "yellow"
        };
        const color = status_colors[frm.doc.status] || "gray";
        frm.dashboard.set_headline(
            `<span style="color: ${color}; font-weight: bold;">
            Campus Status: ${frm.doc.status}
            </span>`
        );
        if (frm.doc.status === "Offered" && frm.doc.acceptance_deadline) {
            const deadline = new Date(frm.doc.acceptance_deadline);
            const now = new Date();
            const diff = deadline - now;
            if (diff > 0) {
                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                frm.dashboard.add_comment(
                    `⚠ Offer expires in ${days} days. Accept before deadline.`,
                    "orange"
                );
            }
        }
    },
    campus: function(frm) {
        if (frm.doc.campus && frm.doc.admission_cycle) {
            frappe.db.count("Applicant Campus Preference", {
                applicant: frm.doc.applicant,
                admission_cycle: frm.doc.admission_cycle
            }, function(count) {
                if (count >= 3) {
                    frappe.msgprint({
                        title: "Limit Reached",
                        indicator: "red",
                        message: "You can only select 3 campus preferences."
                    });
                    frm.set_value("campus", "");
                }
            });
        }
    }
});