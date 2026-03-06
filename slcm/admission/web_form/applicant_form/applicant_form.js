frappe.ready(function () {

	// ── Fields that trigger eligibility re-check ─────────────────────────────
	var ELIGIBILITY_FIELDS = ['program', 'campus', 'admission_cycle', 'academic_year'];

	// ── Debounce timer handle ────────────────────────────────────────────────
	var eligibilityTimer = null;

	// ── Toast / alert container (injected once) ──────────────────────────────
	var $alertBox = null;

	function ensureAlertBox() {
		if ($alertBox && $alertBox.length) return;
		$alertBox = $('<div id="eligibility-alert-box" style="display:none; margin: 16px 0; border-radius: 8px; padding: 14px 18px; font-size: 14px; line-height: 1.6;"></div>');
		// Insert just before the first .frappe-control or after the first section
		var $form = $('form.web-form, .web-form-container').first();
		if ($form.length) {
			$form.prepend($alertBox);
		} else {
			$('body').prepend($alertBox);
		}
	}

	function showEligibilityAlert(status, rawMessage) {
		ensureAlertBox();
		$alertBox.removeClass('alert-eligible alert-ineligible alert-incomplete alert-error');

		if (status === 'Eligible') {
			$alertBox
				.css({
					background: '#f0fdf4',
					border: '1px solid #86efac',
					color: '#166534'
				})
				.html('<strong>✅ Eligible</strong> — ' + rawMessage)
				.slideDown(200);

		} else if (status === 'Ineligible') {
			// rawMessage is an HTML string from frappe.throw() — render it directly
			$alertBox
				.css({
					background: '#fff2f2',
					border: '1px solid #fca5a5',
					color: '#991b1b'
				})
				.html('<strong>❌ Not Eligible</strong><br>' + rawMessage)
				.slideDown(200);

		} else if (status === 'Incomplete') {
			$alertBox.slideUp(100);

		} else {
			$alertBox
				.css({
					background: '#fef9c3',
					border: '1px solid #fde047',
					color: '#854d0e'
				})
				.html('<strong>⚠️ </strong>' + rawMessage)
				.slideDown(200);
		}
	}

	function hideAlert() {
		if ($alertBox) $alertBox.slideUp(150);
	}

	// ── Get current doc field values from the web form inputs ────────────────
	function getDocName() {
		// Frappe web form stores the doc name in the URL or a hidden input
		var name = frappe.web_form && frappe.web_form.doc && frappe.web_form.doc.name;
		if (!name) {
			// Fallback: read from query param
			var params = new URLSearchParams(window.location.search);
			name = params.get('name') || params.get('doc');
		}
		return name || null;
	}

	function hasAllKeyFields() {
		var doc = frappe.web_form && frappe.web_form.doc;
		if (!doc) return false;
		return !!(doc.program && doc.campus && doc.admission_cycle && doc.academic_year);
	}

	// ── Run live eligibility check (debounced 800ms) ─────────────────────────
	function scheduleEligibilityCheck() {
		clearTimeout(eligibilityTimer);
		eligibilityTimer = setTimeout(runEligibilityCheck, 800);
	}

	function runEligibilityCheck() {
		var docName = getDocName();
		if (!docName) return;   // new unsaved record — skip (will run on after_save)
		if (!hasAllKeyFields()) {
			hideAlert();
			return;
		}

		// Show a neutral "checking…" state
		ensureAlertBox();
		$alertBox
			.css({ background: '#f1f5f9', border: '1px solid #cbd5e1', color: '#334155' })
			.html('<span class="spinner-border spinner-border-sm me-2"></span> Checking eligibility…')
			.slideDown(150);

		frappe.call({
			method: 'slcm.admission.web_form.applicant_form.applicant_form.check_eligibility',
			args: { applicant_name: docName },
			callback: function (r) {
				if (r && r.message) {
					showEligibilityAlert(r.message.status, r.message.message);
				}
			},
			error: function () {
				showEligibilityAlert('error', 'Could not complete eligibility check. Please save the form to re-run.');
			}
		});
	}

	// ── Bind change listeners to eligibility-relevant fields ─────────────────
	function bindFieldListeners() {
		ELIGIBILITY_FIELDS.forEach(function (fieldname) {
			// Frappe web forms render fields as input/select with data-fieldname
			$(document).on('change input', '[data-fieldname="' + fieldname + '"] input, [data-fieldname="' + fieldname + '"] select', function () {
				scheduleEligibilityCheck();
			});

			// Also listen via frappe.web_form events if available
			if (frappe.web_form) {
				frappe.web_form.on(fieldname, 'change', function () {
					scheduleEligibilityCheck();
				});
			}
		});

		// Also listen for changes in categories table (affects category-priority engine)
		$(document).on('change', '[data-fieldname="categories"] input, [data-fieldname="categories"] select', function () {
			scheduleEligibilityCheck();
		});
	}

	// ── After save callback — show result of server-side eligibility check ────
	if (frappe.web_form) {
		frappe.web_form.after_save = function (doc) {
			// The server's after_save already ran validate_eligibility.
			// Re-query to get the stored evaluation_status and show the alert.
			var status = doc.evaluation_status;
			if (status === 'Eligible') {
				showEligibilityAlert('Eligible', __('You meet the eligibility criteria for the selected program.'));
			} else if (status === 'Ineligible') {
				showEligibilityAlert('Ineligible', doc.rejected_reason || __('You do not meet the eligibility criteria for the selected program.'));
			}
		};
	}

	// ── Initialise ────────────────────────────────────────────────────────────
	bindFieldListeners();

	// Run once on page load if doc already exists (edit mode)
	if (getDocName() && hasAllKeyFields()) {
		runEligibilityCheck();
	}
});