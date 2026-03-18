// Poll until the phone control is fully initialised, then set India (+91)
// as default when no country code is present.
// Defined at module scope so it can be called from both frappe.ready and after_load.
function set_india_default(attempts) {
    attempts = attempts || 0;
    const phone_field = frappe.web_form.fields_dict &&
        frappe.web_form.fields_dict['candidate_contact_number'];
    if (phone_field && phone_field.country_code_picker &&
        phone_field.country_codes && phone_field.$isd) {
        // Set India if: the ISD picker shows nothing, OR the stored value has
        // no '+' prefix (meaning no country code was saved with the number).
        const stored_value = (phone_field.value || '').toString().trim();
        const isd_empty = !phone_field.$isd.text().trim();
        const no_country_code = !stored_value.startsWith('+');
        if (isd_empty || no_country_code) {
            phone_field.country_code_picker.on_change('India', false);
        }
    } else if (attempts < 20) {
        setTimeout(function () { set_india_default(attempts + 1); }, 200);
    }
}


frappe.ready(function () {
    // Mask the URL — replace any path like /foundations-for-a-legal-education/FLE-2026-XXXX
    // with the clean base route so document names are never visible in the browser bar.
    if (window.location.pathname !== '/foundations-for-a-legal-education') {
        history.replaceState(null, '', '/foundations-for-a-legal-education');
    }

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


    // Pre-fill email and mobile from server-side cache (URL is kept clean)
    frappe.call({
        method: 'slcm.api.user.get_fle_prefill_data',
        callback: function (r) {
            const data = r.message || {};
            setTimeout(() => {
                if (data.email) {
                    frappe.web_form.set_value('email_address', data.email);
                    if (frappe.web_form.fields_dict && frappe.web_form.fields_dict['email_address']) {
                        frappe.web_form.fields_dict['email_address'].df.read_only = 1;
                        frappe.web_form.fields_dict['email_address'].refresh();
                    }
                }
                if (data.mobile) {
                    const phone_fld = frappe.web_form.fields_dict &&
                        frappe.web_form.fields_dict['candidate_contact_number'];
                    let mobile = data.mobile.trim();
                    // Pre-format with country code so the phone control uses the simple
                    // branch-1 path (value.includes("-")) instead of the async else-if
                    // branch, which can cause the number to appear doubled.
                    if (!mobile.startsWith('+') && phone_fld && phone_fld.$isd) {
                        const isd = phone_fld.$isd.text().trim();
                        if (isd) {
                            mobile = isd + '-' + mobile;
                        }
                    }
                    frappe.web_form.set_value('candidate_contact_number', mobile);
                    if (phone_fld) {
                        phone_fld.df.read_only = 1;
                        phone_fld.refresh();
                    }
                }
            }, 500);
        }
    });

    set_india_default();
});


// Runs after frappe.web_form.make() → set_field_values(), so field values
// (including the phone number) are already loaded at this point.
frappe.web_form.after_load = function () {
    // Re-apply India (+91) default now that field values are populated.
    // This is the definitive call — the frappe.ready call handles new forms
    // but after_load is needed for existing documents where set_field_values()
    // runs after frappe.ready and may reset the ISD picker.
    set_india_default();

    if (frappe.web_form.is_new || frappe.web_form.in_edit_mode) return;

    // Fallback: form loaded in read-only mode — redirect to /edit URL.
    var docname = frappe.web_form.doc && frappe.web_form.doc.name;
    if (docname) {
        window.location.replace(
            '/' + frappe.web_form.route + '/' + encodeURIComponent(docname) + '/edit'
        );
    }
};


// Call the global custom header/footer injector
$(function () {
    if (typeof inject_fle_header_footer === 'function') {
        inject_fle_header_footer();
    }
});
