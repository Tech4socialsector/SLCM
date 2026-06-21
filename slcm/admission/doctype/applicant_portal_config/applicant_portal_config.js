// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Applicant Portal Config', {
    font_size_preset: function(frm) {
        var preset = frm.doc.font_size_preset;
        var presets = {
            'Small':  { font_size_heading: '18pt', font_size_subheading: '14pt',
                        font_size_body: '10pt', font_size_form_title: '13pt',
                        font_size_toast: '11pt' },
            'Normal': { font_size_heading: '19pt', font_size_subheading: '16pt',
                        font_size_body: '10.5pt', font_size_form_title: '15pt',
                        font_size_toast: '12pt' },
            'Large':  { font_size_heading: '21pt', font_size_subheading: '17pt',
                        font_size_body: '11.5pt', font_size_form_title: '16pt',
                        font_size_toast: '13pt' }
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
    },
    enable_pace_site: function(frm) {
        if (frm.doc.enable_pace_site == 1) {
            var base_url = frappe.urllib.get_base_url();
            frm.set_value("route", base_url + "/paceadmissions");
        } else {
            frm.set_value("route", "");
        }
    }
});
