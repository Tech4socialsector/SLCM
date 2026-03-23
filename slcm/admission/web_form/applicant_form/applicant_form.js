// ═══════════════════════════════════════════════════════════════════
//  SLCM — Applicant Web Form client script
//  Features:
//    • Silent fee recalculation on whether_scstobc_ncl change
//    • Save Draft button (always before the Next/Submit primary button)
//    • Application status badge near the applicant-ID heading
//    • Toast notifications — top-right
//    • Submit intercept: mandatory → eligibility → fee/Razorpay → submit
// ═══════════════════════════════════════════════════════════════════

// ───────────────────────────────────────────────────────────────────
//  CSS
// ───────────────────────────────────────────────────────────────────
function _injectCSS() {
	if (document.getElementById('slcm-wf-css')) return;
	var s = document.createElement('style');
	s.id = 'slcm-wf-css';
	s.textContent = [
		/* Save Draft button */
		'#slcm-save-draft-btn{display:inline-flex;align-items:center;gap:7px;' +
			'padding:7px 18px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;' +
			'border:1.5px solid #1a73e8;background:#fff;color:#1a73e8;' +
			'transition:background .15s,color .15s;white-space:nowrap;margin-right:10px;}',
		'#slcm-save-draft-btn:hover:not(:disabled){background:#e8f0fe;border-color:#1558b0;}',
		'#slcm-save-draft-btn:disabled{opacity:.6;cursor:not-allowed;}',
		/* spinner keyframes */
		'@keyframes slcm-spin{to{transform:rotate(360deg)}}',
		/* Toast — top-right */
		'#slcm-toast{position:fixed;top:24px;right:24px;z-index:99999;' +
			'min-width:260px;max-width:400px;padding:13px 18px;border-radius:10px;' +
			'font-size:13.5px;font-weight:500;line-height:1.5;pointer-events:none;' +
			'box-shadow:0 8px 32px rgba(0,0,0,.18);display:none;' +
			'transition:opacity .3s;}',
		'#slcm-toast.slcm-success{background:#f0fdf4;border:1.5px solid #86efac;color:#14532d;}',
		'#slcm-toast.slcm-error  {background:#fff2f2;border:1.5px solid #fca5a5;color:#991b1b;}',
		'#slcm-toast.slcm-info   {background:#eff6ff;border:1.5px solid #93c5fd;color:#1e3a5f;}',
		'#slcm-toast.slcm-warn   {background:#fffbeb;border:1.5px solid #fcd34d;color:#78350f;}',
		/* Application status badge */
		'.slcm-status-badge{display:inline-block;padding:2px 10px;border-radius:20px;' +
			'font-size:11px;font-weight:700;letter-spacing:.4px;vertical-align:middle;' +
			'margin-left:10px;text-transform:uppercase;}',
		'.slcm-status-draft    {background:#fef3c7;color:#92400e;border:1px solid #fcd34d;}',
		'.slcm-status-submitted{background:#dcfce7;color:#14532d;border:1px solid #86efac;}',
		'.slcm-status-other    {background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;}',
		/* Fee-payment overlay modal */
		'#slcm-fee-modal{position:fixed;inset:0;z-index:99998;display:none;align-items:center;justify-content:center;}',
		'#slcm-fee-modal.open{display:flex;}',
		'#slcm-fee-backdrop{position:absolute;inset:0;background:rgba(0,0,0,.45);}',
		'#slcm-fee-box{position:relative;background:#fff;border-radius:14px;' +
			'padding:32px 28px;width:100%;max-width:420px;box-shadow:0 16px 48px rgba(0,0,0,.2);}',
		'#slcm-fee-box h3{margin:0 0 6px;font-size:1.15rem;color:#1e293b;}',
		'#slcm-fee-amount{font-size:2rem;font-weight:700;color:#1a73e8;margin:10px 0 6px;}',
		'#slcm-fee-box p{font-size:.85rem;color:#64748b;margin:0 0 22px;}',
		'.slcm-fee-actions{display:flex;gap:10px;flex-wrap:wrap;}',
		'#slcm-fee-pay-btn{flex:1;padding:10px 0;border-radius:8px;' +
			'background:#1a73e8;color:#fff;border:none;font-weight:600;cursor:pointer;font-size:14px;}',
		'#slcm-fee-pay-btn:disabled{opacity:.6;cursor:not-allowed;}',
		'#slcm-fee-later-btn{flex:1;padding:10px 0;border-radius:8px;' +
			'background:#f1f5f9;color:#334155;border:1.5px solid #cbd5e1;font-weight:600;cursor:pointer;font-size:14px;}',
		/* Submit progress overlay */
		'#slcm-submit-overlay{position:fixed;inset:0;z-index:99997;background:rgba(255,255,255,.8);' +
			'display:none;align-items:center;justify-content:center;flex-direction:column;gap:14px;' +
			'font-size:1rem;color:#334155;font-weight:500;}',
		'#slcm-submit-overlay.open{display:flex;}',
		'#slcm-submit-spinner{width:36px;height:36px;border:4px solid #e2e8f0;' +
			'border-top-color:#1a73e8;border-radius:50%;animation:slcm-spin .8s linear infinite;}',
	].join('');
	document.head.appendChild(s);
}

// ───────────────────────────────────────────────────────────────────
//  TOAST — top-right, auto-dismiss 4 s
// ───────────────────────────────────────────────────────────────────
var _toastTimer = null;
function showToast(message, type /* success|error|info|warn */) {
	var el = document.getElementById('slcm-toast');
	if (!el) {
		el = document.createElement('div');
		el.id = 'slcm-toast';
		document.body.appendChild(el);
	}
	el.className = 'slcm-' + (type || 'info');
	el.textContent = message;
	el.style.display = 'block';
	if (_toastTimer) clearTimeout(_toastTimer);
	_toastTimer = setTimeout(function () { el.style.display = 'none'; }, 4000);
}

// ───────────────────────────────────────────────────────────────────
//  DATA HELPERS
// ───────────────────────────────────────────────────────────────────
function getDocName() {
	var name = frappe.web_form && frappe.web_form.doc && frappe.web_form.doc.name;
	if (!name) {
		var p = new URLSearchParams(window.location.search);
		name = p.get('name') || p.get('doc');
	}
	return name || null;
}

/** Read a field value from wf.get_value → wf.doc → frappe.reference_doc */
function resolveField(fieldname) {
	var wf = frappe.web_form;
	var val = '';
	try { val = (wf && wf.get_value(fieldname)) || ''; } catch (e) {}
	if (!val && wf && wf.doc) val = wf.doc[fieldname] || '';
	if (!val && frappe.reference_doc) val = frappe.reference_doc[fieldname] || '';
	return val;
}

function collectDraftData() {
	var wf  = frappe.web_form;
	var doc = (wf && wf.doc) || {};
	var data = {};
	try { data = wf.get_values(true) || {}; } catch (e) {}

	var PRESERVE = [
		'name', 'program', 'admission_cycle', 'academic_year', 'admission_year',
		'campus', 'application_status', 'application_fee_status',
		'application_fee_amount', 'program_level', 'applicant_id',
	];
	var ref = frappe.reference_doc || {};
	PRESERVE.forEach(function (k) {
		if (!data[k] && doc[k]) data[k] = doc[k];
		if (!data[k] && ref[k])  data[k] = ref[k];
	});

	['ug_degree_details', 'pg_degree_details', 'categories'].forEach(function (ct) {
		if ((!data[ct] || !data[ct].length) && doc[ct] && doc[ct].length) {
			data[ct] = doc[ct];
		}
	});
	return data;
}

function hasAllKeyFields() {
	var doc = frappe.web_form && frappe.web_form.doc;
	if (!doc) return false;
	return !!(doc.program && doc.campus && doc.admission_cycle && doc.academic_year);
}

// ───────────────────────────────────────────────────────────────────
//  APPLICATION STATUS BADGE — injected near the applicant-ID heading
// ───────────────────────────────────────────────────────────────────
function _statusBadgeClass(status) {
	if (!status) return 'slcm-status-other';
	var s = status.toLowerCase();
	if (s === 'draft')     return 'slcm-status-draft';
	if (s === 'submitted') return 'slcm-status-submitted';
	return 'slcm-status-other';
}

function updateStatusBadge(status) {
	var badge = document.getElementById('slcm-app-status-badge');
	if (!badge) return;
	badge.className = 'slcm-status-badge ' + _statusBadgeClass(status);
	badge.textContent = status || '';
	badge.style.display = status ? '' : 'none';
}

function setupStatusBadge() {
	if (window._slcm_badge_done) return;
	var attempts = 0;
	var t = setInterval(function () {
		attempts++;
		// Frappe 16 web-form title selectors (try most specific first)
		var $title = $(
			'.web-form-wrapper .title-area h1, ' +
			'.web-form-head h1, ' +
			'.page-header h1, ' +
			'.web-form-container .page-title'
		).first();

		if (!$title.length) {
			// Fallback: find any heading containing the doc-name pattern
			var docName = getDocName() || '';
			if (docName) {
				$('h1, h2, h3, h4').each(function () {
					if ($(this).text().indexOf(docName.substring(0, 6)) !== -1) {
						$title = $(this);
						return false;
					}
				});
			}
		}

		if ($title.length && !document.getElementById('slcm-app-status-badge')) {
			clearInterval(t);
			window._slcm_badge_done = true;

			var badge = document.createElement('span');
			badge.id = 'slcm-app-status-badge';
			var initStatus = resolveField('application_status');
			badge.className = 'slcm-status-badge ' + _statusBadgeClass(initStatus);
			badge.textContent = initStatus || '';
			badge.style.display = initStatus ? '' : 'none';
			$title[0].appendChild(badge);
		}
		if (attempts > 80) clearInterval(t);
	}, 100);
}

// ───────────────────────────────────────────────────────────────────
//  SAVE DRAFT — button + handler
// ───────────────────────────────────────────────────────────────────
function _draftBtnHTML(loading) {
	if (loading) {
		return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
			'style="animation:slcm-spin .8s linear infinite">' +
			'<path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>' +
			' Saving\u2026';
	}
	return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">' +
		'<path stroke-linecap="round" stroke-linejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/></svg>' +
		' Save Draft';
}

function handleSaveDraft(opts) {
	var btn = document.getElementById('slcm-save-draft-btn');
	if (btn) { btn.disabled = true; btn.innerHTML = _draftBtnHTML(true); }

	var data = collectDraftData();

	return new Promise(function (resolve, reject) {
		frappe.call({
			method: 'slcm.admission.web_form.applicant_form.applicant_form.save_applicant_draft',
			args: { data: data, ignore_mandatory: (opts && opts.ignore_mandatory === false) ? false : true },
			freeze: false,
			callback: function (r) {
				if (btn) { btn.disabled = false; btn.innerHTML = _draftBtnHTML(false); }
				var msg = r && r.message;
				if (msg && msg.status === 'success') {
					var wf = frappe.web_form;
					if (wf && wf.doc && !wf.doc.name && msg.name) {
						wf.doc.name = msg.name;
						try {
							var url = new URL(window.location.href);
							url.searchParams.set('name', msg.name);
							window.history.replaceState({}, '', url.toString());
						} catch (e) {}
					}
					try { frappe.web_form.set_value('application_status', 'Draft'); } catch (e) {}
					frappe.form_dirty = false;
					updateStatusBadge('Draft');
					if (!(opts && opts.silent)) {
						showToast('\u2713  ' + (msg.message || 'Draft saved successfully.'), 'success');
					}
					resolve(msg);
				} else {
					var errMsg = (msg && msg.message) || 'Could not save draft.';
					if (!(opts && opts.silent)) showToast('\u26a0  ' + errMsg, 'error');
					reject(new Error(errMsg));
				}
			},
			error: function () {
				if (btn) { btn.disabled = false; btn.innerHTML = _draftBtnHTML(false); }
				var e = 'Network error. Could not save draft.';
				if (!(opts && opts.silent)) showToast('\u26a0  ' + e, 'error');
				reject(new Error(e));
			},
		});
	});
}

/**
 * Find Frappe's primary action button and inject Save Draft just before it.
 * Uses setInterval so it re-injects on every page/step change.
 */
function setupSaveDraftButton() {
	_injectCSS();

	// Re-check every 500 ms to handle multi-step page changes
	setInterval(function () {
		if (document.getElementById('slcm-save-draft-btn')) return;

		var $primary = $(
			'.web-form-footer .right-area .btn-submit-web-form, ' +
			'.web-form-footer .right-area .btn[type="submit"], ' +
			'.web-form-footer .right-area .btn-primary, ' +
			'.web-form-actions .btn-primary, ' +
			'.page-actions .btn-primary'
		).first();

		if (!$primary.length) {
			$primary = $('form.web-form .btn-primary, .web-form-container .btn-primary').first();
		}

		if ($primary.length) {
			var $btn = $('<button type="button" id="slcm-save-draft-btn"></button>');
			$btn.html(_draftBtnHTML(false));
			$btn.on('click', function (e) {
				e.preventDefault();
				handleSaveDraft();
			});
			$primary.before($btn);
		}
	}, 500);
}

// ───────────────────────────────────────────────────────────────────
//  FEE CALCULATION — silent (no banner)
// ───────────────────────────────────────────────────────────────────
var _feeTimer = null;

function updateFeeForCategory() {
	var wf  = frappe.web_form;
	var doc = (wf && wf.doc) || {};

	var program = resolveField('program');
	if (!program) return;

	var feeStatus = (resolveField('application_fee_status') || '').trim();
	if (feeStatus === 'Paid' || feeStatus === 'Waived') return;

	var category      = resolveField('whether_scstobc_ncl');
	var admissionCycle = resolveField('admission_cycle');

	frappe.call({
		method: 'slcm.admission.web_form.applicant_form.applicant_form.get_application_fee_amount',
		args: {
			program: program,
			category: category || '',
			admission_cycle: admissionCycle || '',
		},
		callback: function (r) {
			if (r && r.message !== undefined && r.message !== null) {
				var fee = parseFloat(r.message) || 0;
				// Silently update the form field and in-memory doc
				try { wf.set_value('application_fee_amount', fee); } catch (e) {}
				try { if (doc) doc.application_fee_amount = fee; } catch (e) {}
			}
		},
	});
}

function scheduleFeeUpdate() {
	clearTimeout(_feeTimer);
	_feeTimer = setTimeout(updateFeeForCategory, 350);
}

function bindFeeListener() {
	$(document).on(
		'change',
		'[data-fieldname="whether_scstobc_ncl"] select, [data-fieldname="whether_scstobc_ncl"] input',
		scheduleFeeUpdate
	);
	if (frappe.web_form && typeof frappe.web_form.on === 'function') {
		frappe.web_form.on('whether_scstobc_ncl', scheduleFeeUpdate);
	}
}

// ───────────────────────────────────────────────────────────────────
//  SUBMIT INTERCEPT + FULL FLOW
// ───────────────────────────────────────────────────────────────────

/** Show / hide the full-page progress overlay */
function _showSubmitOverlay(msg) {
	var el = document.getElementById('slcm-submit-overlay');
	if (!el) {
		el = document.createElement('div');
		el.id = 'slcm-submit-overlay';
		el.innerHTML = '<div id="slcm-submit-spinner"></div><span id="slcm-submit-msg"></span>';
		document.body.appendChild(el);
	}
	document.getElementById('slcm-submit-msg').textContent = msg || 'Please wait\u2026';
	el.classList.add('open');
}
function _hideSubmitOverlay() {
	var el = document.getElementById('slcm-submit-overlay');
	if (el) el.classList.remove('open');
}

/** Fee payment modal */
function _showFeeModal(feeDetails, onPaid) {
	var modal = document.getElementById('slcm-fee-modal');
	if (!modal) {
		modal = document.createElement('div');
		modal.id = 'slcm-fee-modal';
		modal.innerHTML =
			'<div id="slcm-fee-backdrop"></div>' +
			'<div id="slcm-fee-box">' +
				'<h3>Application Fee Payment</h3>' +
				'<div id="slcm-fee-amount"></div>' +
				'<p>Your application fee as per the Programme Reservation Policy.<br>' +
				'Please complete payment to submit your application.</p>' +
				'<div class="slcm-fee-actions">' +
					'<button id="slcm-fee-pay-btn">Pay Now</button>' +
					'<button id="slcm-fee-later-btn">Save &amp; Pay Later</button>' +
				'</div>' +
			'</div>';
		document.body.appendChild(modal);
	}

	var amountFormatted = '\u20B9 ' + (feeDetails.fee_amount || 0).toFixed(2);
	document.getElementById('slcm-fee-amount').textContent = amountFormatted;
	modal.classList.add('open');

	function closeModal() { modal.classList.remove('open'); }

	document.getElementById('slcm-fee-backdrop').onclick = closeModal;

	document.getElementById('slcm-fee-later-btn').onclick = function () {
		closeModal();
		showToast('Draft saved. Please complete payment to submit your application.', 'info');
	};

	document.getElementById('slcm-fee-pay-btn').onclick = function () {
		var payBtn = document.getElementById('slcm-fee-pay-btn');
		payBtn.disabled = true;
		payBtn.textContent = 'Opening\u2026';

		frappe.call({
			method: 'slcm.api.service.fee_service.create_application_fee_razorpay_order',
			args: { applicant_name: feeDetails.applicant_name },
			callback: function (r) {
				var d = r && r.message;
				if (!d || !d.order_id) {
					payBtn.disabled = false;
					payBtn.textContent = 'Pay Now';
					showToast('Could not create payment order. Please try again.', 'error');
					return;
				}

				if (typeof Razorpay === 'undefined') {
					// Try loading dynamically
					var sc = document.createElement('script');
					sc.src = 'https://checkout.razorpay.com/v1/checkout.js';
					sc.onload = function () { _openRazorpay(d, feeDetails, onPaid, payBtn, closeModal); };
					sc.onerror = function () {
						payBtn.disabled = false;
						payBtn.textContent = 'Pay Now';
						showToast('Payment gateway script failed to load. Please refresh.', 'error');
					};
					document.head.appendChild(sc);
				} else {
					_openRazorpay(d, feeDetails, onPaid, payBtn, closeModal);
				}
			},
			error: function () {
				payBtn.disabled = false;
				payBtn.textContent = 'Pay Now';
				showToast('Network error while creating payment order.', 'error');
			},
		});
	};
}

function _openRazorpay(orderData, feeDetails, onPaid, payBtn, closeModal) {
	var options = {
		key: orderData.key_id,
		amount: orderData.amount,
		currency: orderData.currency || 'INR',
		order_id: orderData.order_id,
		name: 'Application Fee',
		description: 'Application Fee',
		handler: function (res) {
			_showSubmitOverlay('Verifying payment\u2026');
			frappe.call({
				method: 'slcm.api.service.fee_service.verify_application_fee_payment',
				args: {
					razorpay_payment_id: res.razorpay_payment_id,
					razorpay_order_id: res.razorpay_order_id,
					razorpay_signature: res.razorpay_signature,
					applicant_name: feeDetails.applicant_name,
				},
				callback: function (vr) {
					payBtn.disabled = false;
					payBtn.textContent = 'Pay Now';
					if (vr && vr.message && vr.message.status === 'success') {
						showToast('Payment successful!', 'success');
						closeModal();
						onPaid();
					} else {
						_hideSubmitOverlay();
						showToast((vr && vr.message && vr.message.message) || 'Verification failed.', 'error');
					}
				},
				error: function () {
					_hideSubmitOverlay();
					payBtn.disabled = false;
					payBtn.textContent = 'Pay Now';
					showToast('Verification failed. Please contact support.', 'error');
				},
			});
		},
	};

	var rzp = new Razorpay(options);
	rzp.on('payment.failed', function (err) {
		frappe.call({
			method: 'slcm.api.service.fee_service.log_application_fee_payment_failure',
			args: {
				applicant_name: feeDetails.applicant_name,
				order_id: orderData.order_id,
				error_data: JSON.stringify(err && err.error ? err.error : err),
			},
		});
		showToast((err && err.error && err.error.description) || 'Payment failed.', 'error');
		payBtn.disabled = false;
		payBtn.textContent = 'Pay Now';
	});

	rzp.open();
	payBtn.disabled = false;
	payBtn.textContent = 'Pay Now';
}

/** Call backend submit_applicant and update UI */
function _doFinalSubmit(applicantName) {
	_showSubmitOverlay('Submitting application\u2026');
	frappe.call({
		method: 'slcm.admission.web_form.applicant_form.applicant_form.submit_applicant',
		args: { applicant_name: applicantName },
		callback: function (r) {
			_hideSubmitOverlay();
			var msg = r && r.message;
			if (msg && msg.status === 'success') {
				updateStatusBadge('Submitted');
				try { frappe.web_form.set_value('application_status', 'Submitted'); } catch (e) {}
				showToast('\u2705  Application submitted successfully!', 'success');
				// Reload after short delay so the form shows submitted state
				setTimeout(function () { window.location.reload(); }, 1500);
			} else {
				showToast('\u26a0  ' + ((msg && msg.message) || 'Submission failed.'), 'error');
			}
		},
		error: function () {
			_hideSubmitOverlay();
			showToast('\u26a0  Network error during submission.', 'error');
		},
	});
}

/**
 * Full submit flow:
 *  1. Save draft with mandatory enforcement  (ignore_mandatory=false)
 *  2. Check eligibility
 *  3. Get fee details
 *  4a. Fee > 0 and not paid → show Razorpay modal → on payment → submit
 *  4b. Fee = 0 or paid/waived → submit directly
 */
function runSubmitFlow() {
	var wf = frappe.web_form;

	// ── 1. Save with mandatory validation ──────────────────────────
	_showSubmitOverlay('Saving and validating\u2026');
	handleSaveDraft({ ignore_mandatory: false, silent: true })
		.then(function (saveResult) {
			var applicantName = (saveResult && saveResult.name) || getDocName();
			if (!applicantName) {
				_hideSubmitOverlay();
				showToast('Could not determine applicant. Please save first.', 'error');
				return;
			}

			// ── 2. Eligibility check ────────────────────────────────
			_showSubmitOverlay('Checking eligibility\u2026');
			frappe.call({
				method: 'slcm.admission.web_form.applicant_form.applicant_form.check_eligibility',
				args: { applicant_name: applicantName },
				callback: function (r) {
					var res = r && r.message;
					if (!res || res.status === 'Ineligible') {
						_hideSubmitOverlay();
						showToast('\u274c Not eligible: ' + ((res && res.message) || 'Unknown reason.'), 'error');
						// Also show inline eligibility alert
						showEligibilityAlert('Ineligible', (res && res.message) || '');
						return;
					}
					if (res.status === 'Error') {
						_hideSubmitOverlay();
						showToast('\u26a0  Eligibility check failed. Please try again.', 'error');
						return;
					}

					// ── 3. Fee check ────────────────────────────────
					_showSubmitOverlay('Checking application fee\u2026');
					frappe.call({
						method: 'slcm.api.service.application_fee_service.get_application_fee_details',
						args: { applicant_name: applicantName },
						callback: function (fr) {
							_hideSubmitOverlay();
							var fd = fr && fr.message;
							var feeAmount = fd && (fd.fee_amount || 0);
							var canSubmit = fd && fd.can_submit;

							if (feeAmount > 0 && !canSubmit) {
								// ── 4a. Fee required and unpaid ────────────────
								_showFeeModal(fd, function () {
									// Called after successful payment
									_doFinalSubmit(applicantName);
								});
							} else {
								// ── 4b. No fee / already paid → submit ────────
								_doFinalSubmit(applicantName);
							}
						},
						error: function () {
							_hideSubmitOverlay();
							showToast('Could not verify fee status. Please try again.', 'error');
						},
					});
				},
				error: function () {
					_hideSubmitOverlay();
					showToast('Eligibility check failed. Please try again.', 'error');
				},
			});
		})
		.catch(function (err) {
			_hideSubmitOverlay();
			showToast('\u26a0  ' + (err.message || 'Validation failed. Please fill all required fields.'), 'error');
		});
}

/** Override Frappe's web_form.save so our flow runs when Submit is clicked. */
function interceptSubmit() {
	if (!frappe.web_form) return;
	var _origSave = frappe.web_form.save.bind(frappe.web_form);

	frappe.web_form.save = function () {
		// Frappe calls save() for both intermediate "Save" and final "Submit".
		// Detect submit: form is on the last page OR the web form is not multi-step.
		var isLastPage = false;
		try {
			var wf = frappe.web_form;
			if (wf.is_new && wf.is_new()) {
				// New record — let Frappe handle initial save normally
				isLastPage = false;
			} else if (typeof wf.current_section !== 'undefined') {
				var sections = $('.web-form-page').length || (wf.pages && wf.pages.length) || 1;
				isLastPage = (wf.current_section >= sections - 1);
			} else {
				// Single-page form or unknown — treat as submit
				isLastPage = true;
			}
		} catch (e) {
			isLastPage = false;
		}

		// Check if the visible primary button says "Submit"
		var $btn = $('.web-form-footer .right-area .btn-primary, .web-form-footer .btn-submit-web-form').first();
		var btnText = ($btn.text() || '').trim().toLowerCase();
		var looksLikeSubmit = (btnText === 'submit' || btnText.indexOf('submit') !== -1);

		if (isLastPage || looksLikeSubmit) {
			runSubmitFlow();
		} else {
			_origSave();
		}
	};
}

// ───────────────────────────────────────────────────────────────────
//  ELIGIBILITY — live check
// ───────────────────────────────────────────────────────────────────
var ELIGIBILITY_FIELDS = ['program', 'campus', 'admission_cycle', 'academic_year'];
var _eligTimer = null;
var $alertBox = null;

function ensureAlertBox() {
	if ($alertBox && $alertBox.length) return;
	$alertBox = $('<div id="eligibility-alert-box" style="display:none;margin:16px 0;border-radius:8px;padding:14px 18px;font-size:14px;line-height:1.6;"></div>');
	var $form = $('form.web-form, .web-form-container').first();
	if ($form.length) $form.prepend($alertBox);
	else $('body').prepend($alertBox);
}

function showEligibilityAlert(status, rawMessage) {
	ensureAlertBox();
	if (status === 'Eligible') {
		$alertBox.css({ background: '#f0fdf4', border: '1px solid #86efac', color: '#166534' })
			.html('<strong>\u2705 Eligible</strong> \u2014 ' + rawMessage).slideDown(200);
	} else if (status === 'Ineligible') {
		$alertBox.css({ background: '#fff2f2', border: '1px solid #fca5a5', color: '#991b1b' })
			.html('<strong>\u274c Not Eligible</strong><br>' + rawMessage).slideDown(200);
	} else if (status === 'Incomplete') {
		$alertBox.slideUp(100);
	} else {
		$alertBox.css({ background: '#fef9c3', border: '1px solid #fde047', color: '#854d0e' })
			.html('<strong>\u26a0\ufe0f </strong>' + rawMessage).slideDown(200);
	}
}

function hideAlert() { if ($alertBox) $alertBox.slideUp(150); }

function scheduleEligibilityCheck() {
	clearTimeout(_eligTimer);
	_eligTimer = setTimeout(runEligibilityCheck, 800);
}

function runEligibilityCheck() {
	var docName = getDocName();
	if (!docName || !hasAllKeyFields()) { hideAlert(); return; }

	ensureAlertBox();
	$alertBox.css({ background: '#f1f5f9', border: '1px solid #cbd5e1', color: '#334155' })
		.html('<span class="spinner-border spinner-border-sm me-2"></span> Checking eligibility\u2026')
		.slideDown(150);

	frappe.call({
		method: 'slcm.admission.web_form.applicant_form.applicant_form.check_eligibility',
		args: { applicant_name: docName },
		callback: function (r) {
			if (r && r.message) showEligibilityAlert(r.message.status, r.message.message);
		},
		error: function () {
			showEligibilityAlert('error', 'Could not complete eligibility check.');
		},
	});
}

function bindFieldListeners() {
	ELIGIBILITY_FIELDS.forEach(function (fieldname) {
		$(document).on('change input',
			'[data-fieldname="' + fieldname + '"] input, [data-fieldname="' + fieldname + '"] select',
			scheduleEligibilityCheck
		);
		if (frappe.web_form && typeof frappe.web_form.on === 'function') {
			frappe.web_form.on(fieldname, 'change', scheduleEligibilityCheck);
		}
	});
	$(document).on('change',
		'[data-fieldname="categories"] input, [data-fieldname="categories"] select',
		scheduleEligibilityCheck
	);
}

// ───────────────────────────────────────────────────────────────────
//  BOOTSTRAP
// ───────────────────────────────────────────────────────────────────
frappe.ready(function () {
	_injectCSS();

	// Fee (silent)
	bindFeeListener();
	setTimeout(updateFeeForCategory, 600);

	// Eligibility
	bindFieldListeners();

	// Status badge
	setupStatusBadge();

	// Save Draft button (re-polls on every step change)
	setupSaveDraftButton();

	// Submit intercept
	interceptSubmit();

	// After web form save hook — show eligibility result
	if (frappe.web_form) {
		frappe.web_form.after_save = function (doc) {
			var status = doc.evaluation_status;
			if (status === 'Eligible') {
				showEligibilityAlert('Eligible', __('You meet the eligibility criteria for the selected program.'));
			} else if (status === 'Ineligible') {
				showEligibilityAlert('Ineligible', doc.rejected_reason || __('You do not meet the eligibility criteria.'));
			}
		};
	}

	// Initial eligibility check if doc already exists
	if (getDocName() && hasAllKeyFields()) {
		runEligibilityCheck();
	}
});
