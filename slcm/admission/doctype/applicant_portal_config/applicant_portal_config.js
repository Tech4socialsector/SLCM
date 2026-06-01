// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Applicant Portal Config', {
    font_size_preset: function(frm) {
        var preset = frm.doc.font_size_preset;
        var presets = {
            'Small':  { font_size_heading: '24px', font_size_subheading: '19px',
                        font_size_body: '13px', font_size_form_title: '17px',
                        font_size_toast: '14px' },
            'Normal': { font_size_heading: '26px', font_size_subheading: '21px',
                        font_size_body: '14px', font_size_form_title: '20px',
                        font_size_toast: '16px' },
            'Large':  { font_size_heading: '28px', font_size_subheading: '23px',
                        font_size_body: '15px', font_size_form_title: '22px',
                        font_size_toast: '17px' }
        };
        if (presets[preset]) {
            $.each(presets[preset], function(field, value) {
                frm.set_value(field, value);
            });
        } else if (preset === 'Custom') {
            frappe.show_alert({
                message: 'Adjust individual sizes below. These values override the preset.',
                indicator: 'blue'
            });
        }
    }
});
