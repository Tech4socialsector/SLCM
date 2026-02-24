frappe.ui.form.on("Admission Cycle", {
    refresh: function(frm) {
        const status_colors = {
            "Draft": "gray",
            "Active": "green",
            "Closed": "red"
        };
        const color = status_colors[frm.doc.status] || "gray";
        frm.dashboard.set_headline(
            `<span style="color: ${color}; font-weight: bold;">
            Status: ${frm.doc.status}
            </span>`
        );
        if (!frm.is_new()) {
            frm.add_custom_button("View Rounds", function() {
                frappe.set_route("List", "Admission Round", {
                    admission_cycle: frm.doc.name
                });
            });
            frm.add_custom_button("View Applicants", function() {
                frappe.set_route("List", "Applicant", {
                    admission_cycle: frm.doc.name
                });
            });
        }
    },
    workflow_type: function(frm) {
        frm.set_value("clat_consortium_code", "");
        frm.set_value("nlsat_exam_date", "");
        const messages = {
            "CLAT": "CLAT workflow: Seat allotment is driven by Consortium of NLUs.",
            "NLSAT": "NLSAT workflow: NLSIU conducts exam and interview internally.",
            "PACE": "PACE workflow: Merit-based admission, no entrance exam required."
        };
        if (frm.doc.workflow_type) {
            frappe.show_alert({
                message: messages[frm.doc.workflow_type],
                indicator: "blue"
            }, 5);
        }
    }
});
