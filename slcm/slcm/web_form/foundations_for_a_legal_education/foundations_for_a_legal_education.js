frappe.ready(function () {

    // List of mandatory fields to validate
    const mandatoryFields = [
        'email_address',
        'candidate_name',
        'where_did_you_hear',
        'last_class_attended',
        'latest_board_attended',
        'year_of_passing'
    ];

    // Function to check if all mandatory fields are filled
    function checkMandatoryFields() {
        let allFilled = true;

        mandatoryFields.forEach(function (fieldName) {
            const fieldValue = frappe.web_form.get_field(fieldName)
                ? frappe.web_form.get_field(fieldName).get_value()
                : null;

            if (!fieldValue || fieldValue.toString().trim() === '') {
                allFilled = false;
            }
        });

        return allFilled;
    }

    // Function to update button state
    function updatePayButton() {
        const $payBtn = $('button[data-action="pay"], .btn-proceed-to-pay, button:contains("Proceed to Pay")').filter(':visible').first();

        if ($payBtn.length === 0) return;

        if (checkMandatoryFields()) {
            // Enable the button
            $payBtn.prop('disabled', false);
            $payBtn.removeClass('disabled btn-disabled');
            $payBtn.css({
                'pointer-events': 'auto',
                'opacity': '1',
                'cursor': 'pointer'
            });
        } else {
            // Disable the button
            $payBtn.prop('disabled', true);
            $payBtn.addClass('disabled');
            $payBtn.css({
                'pointer-events': 'none',
                'opacity': '0.5',
                'cursor': 'not-allowed'
            });
        }
    }

    // Wait for the web form to fully render
    setTimeout(function () {

        // Initial disable on page load
        updatePayButton();

        // Attach change/input listeners to each mandatory field
        mandatoryFields.forEach(function (fieldName) {
            const field = frappe.web_form.get_field(fieldName);
            if (!field) return;

            // For input/textarea fields
            $(field.wrapper).find('input, textarea, select').on('input change blur', function () {
                updatePayButton();
            });

            // For Select fields (frappe uses a custom select)
            if (field.df && field.df.fieldtype === 'Select') {
                $(field.wrapper).find('select').on('change', function () {
                    updatePayButton();
                });
            }

            // For Link fields
            if (field.df && field.df.fieldtype === 'Link') {
                $(field.wrapper).find('input').on('change blur', function () {
                    updatePayButton();
                });
            }
        });

        // Also observe DOM changes in case button renders late
        const observer = new MutationObserver(function () {
            updatePayButton();
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        // Disconnect observer after form is stable (10 seconds)
        setTimeout(function () {
            observer.disconnect();
        }, 10000);

    }, 800);

    // Hook into frappe web_form's change event if available
    if (frappe.web_form) {
        frappe.web_form.on('change', function () {
            updatePayButton();
        });
    }

});