frappe.ui.form.on('National Test Exemption Rule', {
    onload: function (frm) {
        frm.set_query("admission_cycle", function () {
            return {
                filters: {
                    "status": "Active"
                }
            };
        });
    },

    mark_percentage: function (frm) {
        if (frm.doc.mark_percentage && (frm.doc.mark_percentage < 35 || frm.doc.mark_percentage > 100)) {
            frappe.show_alert({
                message: __('Percentage should be between 35 and 100'),
                indicator: 'orange'
            });
            frm.set_value('mark_percentage', null);
        }
    },

    validate: function (frm) {
        if (frm.doc.mark_percentage && (frm.doc.mark_percentage < 35 || frm.doc.mark_percentage > 100)) {
            frappe.msgprint({
                title: __("Validation Error"),
                message: __("Mark Percentage should be between 35 and 100"),
                indicator: "red"
            });
            frappe.validated = false;
        }
    }
});



