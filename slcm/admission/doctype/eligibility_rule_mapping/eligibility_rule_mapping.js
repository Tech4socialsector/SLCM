frappe.ui.form.on('Eligibility Rule Mapping', {

    priority: function(frm) {

        if (frm.doc.priority && frm.doc.priority > 100) {

            frappe.msgprint({
                title: "Invalid Priority",
                message: "Priority value cannot be greater than 100.",
                indicator: "red"
            });

            frm.set_value('priority', '');
        }
    },

    validate: function(frm) {

        if (frm.doc.priority && frm.doc.priority > 100) {

            frappe.msgprint({
                title: "Invalid Priority",
                message: "Priority value must be 100 or less.",
                indicator: "red"
            });

            frappe.validated = false;
        }
    }
});
