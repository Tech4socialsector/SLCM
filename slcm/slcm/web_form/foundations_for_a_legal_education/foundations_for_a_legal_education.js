frappe.ready(function () {
	function toggle_declaration_section() {
		try {
			const dob_val = frappe.web_form.get_value('candidate_dob');
			// Default to false (hidden) if no DOB or error
			let show_declaration = false;
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
					show_declaration = true;
				}
			}

			console.log("[Web Form] DOB:", dob_val, "Calculated Age:", age, "Show Declaration:", show_declaration);

			// --- 1. Toggle Section Break (Declaration) ---
			// Try standard API first
			toggle_field('section_break_declaration', show_declaration);

			// MASTER FALLBACK: Find the section header by text 'Declaration'
			// We search for header elements containing "Declaration" and hide their parent container
			const $headers = $('.section-head, .section-header, h2, h3, h4, h5, h6').filter(function () {
				return $(this).text().trim() === 'Declaration';
			});

			if ($headers.length > 0) {
				// Determine the container (usually .web-form-section or .section-break)
				const $section_container = $headers.closest('.web-form-section, .section-break');
				if ($section_container.length > 0) {
					$section_container.toggle(show_declaration);
				} else {
					// Fallback: hide the header and maybe its next sibling if it's a flat structure
					$headers.toggle(show_declaration);
					// This is risky without a container, but better than nothing
				}
			}

			// --- 2. Toggle HTML Content ---
			toggle_field('declaration_html', show_declaration);

			// MASTER FALLBACK: Find by content text
			const unique_text = "This declaration is only for the students below 18 years of age";
			// Find elements containing this text
			const $html_content = $(`div:contains("${unique_text}"), p:contains("${unique_text}")`).filter(function () {
				// Ensure it's the actual content element, not a parent container
				return $(this).children().length === 0 || $(this).hasClass('control-value') || $(this).hasClass('form-control');
			});
			$html_content.closest('.form-group, .web-form-field').toggle(show_declaration);

			// --- 3. Toggle Consent Checkbox ---
			toggle_field('declaration_consent', show_declaration);

		} catch (e) {
			console.warn("[Web Form] Error toggling declaration:", e);
		}
	}

	function toggle_field(fieldname, show) {
		try {
			// Method 1: Try toggle_display (v15+)
			if (typeof frappe.web_form.toggle_display === 'function') {
				frappe.web_form.toggle_display(fieldname, show);
				return;
			}

			// Method 2: Try set_field_property (v13/14)
			if (typeof frappe.web_form.set_field_property === 'function') {
				frappe.web_form.set_field_property(fieldname, 'hidden', show ? 0 : 1);
				return;
			}

			// Method 3: Direct DOM manipulation via get_field
			var field = frappe.web_form.get_field(fieldname);
			if (field && field.$wrapper) {
				field.$wrapper.toggle(show);
				return;
			}

			// Method 4: Data attribute selector
			var $el = $('[data-fieldname="' + fieldname + '"]');
			if ($el.length) {
				// If it's a section break, hide the container
				if ($el.hasClass('section-break') || $el.hasClass('web-form-section')) {
					$el.toggle(show);
				} else {
					$el.closest('.form-group, .web-form-field').toggle(show);
				}
			}
		} catch (e) {
			console.warn("[Web Form] Error into toggle_field for " + fieldname + ":", e);
		}
	}

	frappe.web_form.on('candidate_dob', function () {
		toggle_declaration_section();
	});

	// Run on load
	toggle_declaration_section();
});