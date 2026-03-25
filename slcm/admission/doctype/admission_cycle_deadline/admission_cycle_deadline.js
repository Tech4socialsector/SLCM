frappe.ui.form.on("Admission Cycle Deadline", {
    refresh: function(frm) {
        if (frm.doc.end_datetime) {
            const end = new Date(frm.doc.end_datetime);
            const now = new Date();
            const diff = Math.ceil((end - now) / (1000 * 60 * 60 * 24));
            if (diff > 0) {
                frm.dashboard.set_headline(
                    `<span style="color:green">⏳ ${diff} day(s) remaining</span>`
                );
            } else {
                frm.dashboard.set_headline(
                    `<span style="color:red">🔴 Deadline has passed</span>`
                );
            }
        }
    }
});
