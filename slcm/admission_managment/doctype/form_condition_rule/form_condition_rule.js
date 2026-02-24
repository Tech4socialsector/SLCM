frappe.ui.form.on("Form Condition Rule", {
    refresh: function(frm) {
        if (frm.doc.trigger_field && frm.doc.condition &&
            frm.doc.target_field && frm.doc.action) {
            const rule = `IF ${frm.doc.trigger_field} 
                ${frm.doc.condition} 
                "${frm.doc.trigger_value || ''}" 
                → ${frm.doc.action} "${frm.doc.target_field}"`;
            frm.dashboard.add_comment(rule, "blue");
        }
    },
    trigger_field: function(frm) {
        if (frm.doc.trigger_field === frm.doc.target_field) {
            frappe.msgprint({
                title: "Invalid",
                indicator: "red",
                message: "Trigger and Target fields cannot be the same."
            });
            frm.set_value("trigger_field", "");
        }
    }
});