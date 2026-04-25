frappe.ui.form.on("PACE Verifier Configuration", {
    refresh: function(frm) {
        frm.trigger("update_verifier_stats");
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
                        if (stats[row.user]) {
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
        frm.trigger("update_verifier_stats");
    },
    programme: function(frm, cdt, cdn) {
        frm.trigger("update_verifier_stats");
    }
});
