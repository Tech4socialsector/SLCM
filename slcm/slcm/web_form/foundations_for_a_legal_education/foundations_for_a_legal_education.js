frappe.ready(function () {
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

	frappe.web_form.on('candidate_dob', function () {
		toggle_declaration_section();
	});

	// Run on load
	// Run on load
	toggle_declaration_section();
});

