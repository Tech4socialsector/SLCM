frappe.ready(function () {
    // --------------------------------------------------
    // Master-level Guest Restrictor:
    // Prevent direct access to the web form without login
    // --------------------------------------------------
    if (frappe.session.user === 'Guest') {
        $('body').removeClass('theme-loaded').css({ 'opacity': '0', 'visibility': 'hidden', 'display': 'none' });
        frappe.msgprint({
            title: __('Authentication Required'),
            indicator: 'red',
            message: __('You must be logged in to access this application form. Redirecting to login...')
        });
        setTimeout(function () {
            window.location.replace('/login.html');
        }, 2000);
        return;
    }


    // Capitalize each word in all fields dynamically
    const excluded_fields = ['email_address', 'parent_email_address'];
    if (frappe.web_form && frappe.web_form.fields_dict) {
        $.each(frappe.web_form.fields_dict, function (fieldname, field) {
            if (['Data', 'Small Text', 'Text'].includes(field.df.fieldtype) && !excluded_fields.includes(fieldname)) {
                frappe.web_form.on(fieldname, function (_f, value) {
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


    // Pre-fill email and mobile from URL parameters if present
    const params = new URLSearchParams(window.location.search);
    const email = params.get('email');
    const mobile = params.get('mobile');

    setTimeout(() => {
        if (email) {
            frappe.web_form.set_value('email_address', email);
            if (frappe.web_form.fields_dict && frappe.web_form.fields_dict['email_address']) {
                frappe.web_form.fields_dict['email_address'].df.read_only = 1;
                frappe.web_form.fields_dict['email_address'].refresh();
            }
        }
        if (mobile) {
            frappe.web_form.set_value('candidate_contact_number', mobile);
            if (frappe.web_form.fields_dict && frappe.web_form.fields_dict['candidate_contact_number']) {
                frappe.web_form.fields_dict['candidate_contact_number'].df.read_only = 1;
                frappe.web_form.fields_dict['candidate_contact_number'].refresh();
            }
        }
    }, 500);

    // Poll until the phone control is fully initialised (make_input is async),
    // then set India (+91) as default if no country has been selected yet.
    function set_india_default(attempts) {
        attempts = attempts || 0;
        const phone_field = frappe.web_form.fields_dict &&
            frappe.web_form.fields_dict['candidate_contact_number'];
        if (phone_field && phone_field.country_code_picker &&
            phone_field.country_codes && phone_field.$isd) {
            if (!phone_field.$isd.text().trim()) {
                phone_field.country_code_picker.on_change('India', false);
            }
        } else if (attempts < 20) {
            setTimeout(function () { set_india_default(attempts + 1); }, 200);
        }
    }
    set_india_default();
});


// Call the global custom header/footer injector
$(function () {
    if (typeof inject_fle_header_footer === 'function') {
        inject_fle_header_footer();
    }
});
