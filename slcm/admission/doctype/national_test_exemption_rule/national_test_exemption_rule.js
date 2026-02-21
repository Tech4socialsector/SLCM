frappe.ui.form.on('National Test Exemption Rule', {

    refresh: function (frm) {
        restrict_dates(frm);
    },

    valid_from: function (frm) {
        validate_dates(frm);
    },

    valid_until: function (frm) {
        validate_dates(frm);
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
        validate_dates(frm);

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


function restrict_dates(frm) {

    let today = frappe.datetime.get_today();

    if (frm.fields_dict.valid_from?.datepicker) {
        frm.fields_dict.valid_from.datepicker.update({
            minDate: today
        });
    }

    if (frm.fields_dict.valid_until?.datepicker) {
        frm.fields_dict.valid_until.datepicker.update({
            minDate: today
        });
    }
}


function validate_dates(frm) {

    let today = frappe.datetime.get_today();

    // Valid From - Past Date
    if (frm.doc.valid_from && frm.doc.valid_from < today) {
        frappe.msgprint({
            title: "Invalid Date",
            message: "Valid From date cannot be in the past.",
            indicator: "red"
        });
        frm.set_value('valid_from', '');
        frappe.validated = false;
        return;
    }

    // Valid Until without Valid From
    if (frm.doc.valid_until && !frm.doc.valid_from) {
        frappe.msgprint({
            title: "Missing Valid From",
            message: "Please select Valid From date before selecting Valid Until date.",
            indicator: "orange"
        });
        frm.set_value('valid_until', '');
        frappe.validated = false;
        return;
    }

    // Valid Until - Past Date
    if (frm.doc.valid_until && frm.doc.valid_until < today) {
        frappe.msgprint({
            title: "Invalid Date",
            message: "Valid Until date cannot be in the past.",
            indicator: "red"
        });
        frm.set_value('valid_until', '');
        frappe.validated = false;
        return;
    }

    // Valid Until < Valid From
    if (frm.doc.valid_from && frm.doc.valid_until &&
        frm.doc.valid_until < frm.doc.valid_from) {

        frappe.msgprint({
            title: "Invalid Date Range",
            message: "Valid Until date cannot be earlier than Valid From date.",
            indicator: "red"
        });
        frm.set_value('valid_until', '');
        frappe.validated = false;
    }
}
