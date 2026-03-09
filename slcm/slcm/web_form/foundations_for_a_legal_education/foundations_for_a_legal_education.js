// --------------------------------------------------
// Sets the declaration consent as mandatory based on the candidate's age (under 18).
// --------------------------------------------------
function toggle_declaration_section() {
    try {
        const dob_val = frappe.web_form.get_value('candidate_dob');
        let is_mandatory = false;
        let age = null;

        if (dob_val) {
            const dob = new Date(dob_val);
            const today = new Date();
            age = today.getFullYear() - dob.getFullYear();
            const m = today.getMonth() - dob.getMonth();

            if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
                age--;
            }

            if (age < 18) {
                is_mandatory = true;
            }
        }

        if (typeof frappe.web_form.set_df_property === 'function') {
            frappe.web_form.set_df_property('declaration_consent', 'reqd', is_mandatory ? 1 : 0);
        } else if (frappe.web_form.fields_dict && frappe.web_form.fields_dict['declaration_consent']) {
            frappe.web_form.fields_dict['declaration_consent'].df.reqd = is_mandatory ? 1 : 0;
            frappe.web_form.fields_dict['declaration_consent'].refresh();
        }

    } catch (e) {
        // Error handling silently in production or log to system console if available
    }
}

frappe.ready(function () {
    frappe.web_form.on('candidate_dob', function () {
        toggle_declaration_section();
    });

    // Capitalize each word in all fields dynamically
    const excluded_fields = ['email_address', 'parent_email_address'];
    if (frappe.web_form && frappe.web_form.fields_dict) {
        $.each(frappe.web_form.fields_dict, function (fieldname, field) {
            if (['Data', 'Small Text', 'Text'].includes(field.df.fieldtype) && !excluded_fields.includes(fieldname)) {
                frappe.web_form.on(fieldname, function (f, value) {
                    value = value || frappe.web_form.get_value(fieldname);
                    if (value && typeof value === 'string') {
                        const capitalized = value.replace(/\b[a-zA-Z]/g, function (l) { return l.toUpperCase(); });
                        if (capitalized !== value) {
                            frappe.web_form.set_value(fieldname, capitalized);
                        }
                    }
                });
            }
        });
    }

    // Run on load
    toggle_declaration_section();

    // Pre-fill email and mobile from encoded URL parameters if present
    const params = new URLSearchParams(window.location.search);

    let param_email = params.get('email_address');
    let param_mobile = params.get('candidate_contact_number');

    function try_set_fields() {
        const set_read_only = (fieldname, val) => {
            if (val) {
                // Safely update the value
                if (frappe.web_form.get_value(fieldname) !== val) {
                    frappe.web_form.set_value(fieldname, val);
                }
                const $input = $('[data-fieldname="' + fieldname + '"] input');
                if ($input.length && $input.val() !== val) {
                    $input.val(val).trigger('change');
                }
                if (frappe.web_form.fields_dict && frappe.web_form.fields_dict[fieldname]) {
                    frappe.web_form.fields_dict[fieldname].df.read_only = 1;
                    frappe.web_form.set_df_property(fieldname, 'read_only', 1);
                }
            }
        };

        set_read_only('email_address', param_email);
        set_read_only('candidate_contact_number', param_mobile);
    }

    frappe.web_form.after_load = () => {
        try_set_fields();
    };

    let set_attempts = 0;
    let interval = setInterval(() => {
        try_set_fields();
        set_attempts++;
        if (set_attempts > 20) clearInterval(interval);
    }, 100);
});


// Call the global custom header/footer injector
$(function () {
    if (typeof inject_fle_header_footer === 'function') {
        inject_fle_header_footer();
    }
});
