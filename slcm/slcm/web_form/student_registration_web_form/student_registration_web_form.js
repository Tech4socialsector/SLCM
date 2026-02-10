frappe.ready(function () {
	function toggle_declaration() {
		const dob = frappe.web_form.get_value('candidate_dob');

		// If DOB is empty, hide the declaration
		if (!dob) {
			frappe.web_form.toggle_display('section_break_declaration', false);
			return;
		}

		// Convert DOB to Date object
		const dobDate = new Date(dob);
		const today = new Date();

		// Calculate age
		let age = today.getFullYear() - dobDate.getFullYear();
		const monthDiff = today.getMonth() - dobDate.getMonth();

		if (
			monthDiff < 0 ||
			(monthDiff === 0 && today.getDate() < dobDate.getDate())
		) {
			age--;
		}

		// Show declaration only if age < 18
		frappe.web_form.toggle_display(
			'section_break_declaration',
			age < 18
		);
	}

	// Bind event
	frappe.web_form.on('candidate_dob', function () {
		toggle_declaration();
	});

	// Trigger on load
	toggle_declaration();
});
