frappe.ui.form.on("Campus Program Offering", {
    refresh: function(frm) {
        if (frm.doc.is_active) {
            frm.dashboard.set_headline(
                `<span style="color: green; font-weight: bold;">
                ✓ Active Offering
                </span>`
            );
        } else {
            frm.dashboard.set_headline(
                `<span style="color: gray; font-weight: bold;">
                ○ Inactive Offering
                </span>`
            );
        }
        if (!frm.is_new()) {
            frm.add_custom_button("View Seat Matrix", function() {
                frappe.set_route("List", "Campus Seat Matrix", {
                    campus: frm.doc.campus,
                    program: frm.doc.program,
                    admission_cycle: frm.doc.admission_cycle
                });
            });
        }
    },
    admission_cycle: function(frm) {
        if (frm.doc.admission_cycle) {
            frappe.db.get_value(
                "Admission Cycle",
                frm.doc.admission_cycle,
                "workflow_type",
                function(r) {
                    if (r && r.workflow_type) {
                        frm.set_value("workflow_type", r.workflow_type);
                        frappe.show_alert({
                            message: `Workflow set to ${r.workflow_type} from cycle`,
                            indicator: "blue"
                        }, 3);
                    }
                }
            );
        }
    }
});