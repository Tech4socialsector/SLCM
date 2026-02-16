frappe.ui.form.on('National Test Exemption Rule', {

    refresh: function(frm) {
        restrict_dates(frm);
    },

    valid_from: function(frm) {
        validate_dates(frm);
    },

    valid_until: function(frm) {
        validate_dates(frm);
    },

    validate: function(frm) {
        validate_dates(frm);
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
