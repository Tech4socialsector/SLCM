// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Entrance Test', {

    refresh: function (frm) {
        restrict_dates(frm);
    },

    valid_from: function (frm) {
        validate_dates(frm);
    },

    valid_to: function (frm) {
        validate_dates(frm);
    },

    validate: function (frm) {
        validate_dates(frm);
    }
});


function restrict_dates(frm) {
    const today = frappe.datetime.get_today();

    if (frm.fields_dict.valid_from?.datepicker) {
        frm.fields_dict.valid_from.datepicker.update({ minDate: today });
    }

    if (frm.fields_dict.valid_to?.datepicker) {
        frm.fields_dict.valid_to.datepicker.update({ minDate: today });
    }
}


function validate_dates(frm) {
    const today = frappe.datetime.get_today();

    // valid_from - cannot be in the past
    if (frm.doc.valid_from && frm.doc.valid_from < today) {
        frappe.msgprint({
            title: __('Invalid Date'),
            message: __('Valid From date cannot be in the past.'),
            indicator: 'red'
        });
        frm.set_value('valid_from', '');
        frappe.validated = false;
        return;
    }

    // valid_to requires valid_from first
    if (frm.doc.valid_to && !frm.doc.valid_from) {
        frappe.msgprint({
            title: __('Missing Valid From'),
            message: __('Please select Valid From date before selecting Valid To date.'),
            indicator: 'orange'
        });
        frm.set_value('valid_to', '');
        frappe.validated = false;
        return;
    }

    // valid_to - cannot be in the past
    if (frm.doc.valid_to && frm.doc.valid_to < today) {
        frappe.msgprint({
            title: __('Invalid Date'),
            message: __('Valid To date cannot be in the past.'),
            indicator: 'red'
        });
        frm.set_value('valid_to', '');
        frappe.validated = false;
        return;
    }

    // valid_to cannot be earlier than valid_from
    if (frm.doc.valid_from && frm.doc.valid_to &&
        frm.doc.valid_to < frm.doc.valid_from) {
        frappe.msgprint({
            title: __('Invalid Date Range'),
            message: __('Valid To date cannot be earlier than Valid From date.'),
            indicator: 'red'
        });
        frm.set_value('valid_to', '');
        frappe.validated = false;
    }
}
