frappe.ui.form.on("PACE Verifier Configuration", {
    refresh: function(frm) {
        frm.trigger("update_verifier_stats");

        frm.set_query("user", "verifiers", function() {
            return {
                query: "slcm.pace.api.get_verifiers"
            };
        });
    },
    programme: function(frm) {
        frm.trigger("update_verifier_stats");
    },
    academic_year: function(frm) {
        frm.trigger("update_verifier_stats");
    },
    update_verifier_stats: function(frm) {
        if (!frm.doc.verifiers || frm.doc.verifiers.length === 0) return;

        // Pass objects with user and programme for more accurate row-level stats
        const verifier_data = frm.doc.verifiers
            .filter(v => v.user)
            .map(v => ({
                user: v.user,
                programme: v.programme || frm.doc.programme
            }));

        if (verifier_data.length === 0) return;

        frappe.call({
            method: "slcm.pace.assignment_logic.get_verifier_stats",
            args: {
                verifier_list: verifier_data,
                programme: frm.doc.programme,
                academic_year: frm.doc.academic_year
            },
            callback: function(r) {
                if (r.message) {
                    const stats = r.message;
                    frm.doc.verifiers.forEach(row => {
                        const key = row.user + ":" + (row.programme || frm.doc.programme || "");
                        if (stats[key]) {
                            row.total_assigned = stats[key].total_assigned || 0;
                            row.verified = stats[key].verified || 0;
                            row.pending = stats[key].pending || 0;
                        } else if (stats[row.user]) {
                            row.total_assigned = stats[row.user].total_assigned || 0;
                            row.verified = stats[row.user].verified || 0;
                            row.pending = stats[row.user].pending || 0;
                        }
                    });
                    frm.refresh_field("verifiers");
                }
            }
        });
    }
});

frappe.ui.form.on("PACE Verifier Mapping", {
    user: function(frm, cdt, cdn) {
        check_duplicate_verifier_row(frm, cdt, cdn);
        frm.trigger("update_verifier_stats");
    },
    programme: function(frm, cdt, cdn) {
        check_duplicate_verifier_row(frm, cdt, cdn);
        frm.trigger("update_verifier_stats");
    }
});

function check_duplicate_verifier_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row.user || !row.programme) return;

    // 1. Direct client-side duplicate check within the current grid
    let assigned_verifier = null;
    (frm.doc.verifiers || []).forEach(r => {
        if (r.name !== row.name && r.programme === row.programme) {
            assigned_verifier = r.user;
        }
    });

    if (assigned_verifier) {
        frappe.model.set_value(cdt, cdn, "programme", "");
        frappe.msgprint({
            title: __("Duplicate Assignment"),
            indicator: "orange",
            message: __("Row #{0}: Programme '{1}' is already assigned to verifier '{2}' in this configuration.", [row.idx, row.programme, assigned_verifier])
        });
        return;
    }

    // 2. Cross-document duplicate check for the same Academic Year
    if (frm.doc.academic_year) {
        frappe.call({
            method: "slcm.pace.assignment_logic.check_duplicate_verifier_mapping",
            args: {
                academic_year: frm.doc.academic_year,
                user: row.user,
                programme: row.programme,
                current_docname: frm.doc.name || ""
            },
            callback: function(r) {
                if (r.message) {
                    let other_parent = r.message.parent;
                    let other_user = r.message.user;
                    frappe.model.set_value(cdt, cdn, "programme", "");
                    frappe.msgprint({
                        title: __("Duplicate Assignment"),
                        indicator: "orange",
                        message: __("Row #{0}: Programme '{1}' is already assigned to verifier '{2}' in another configuration '{3}' for Academic Year {4}.", 
                            [row.idx, row.programme, other_user, other_parent, frm.doc.academic_year])
                    });
                }
            }
        });
    }
}

