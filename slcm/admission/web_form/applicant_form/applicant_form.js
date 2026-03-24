// ═══════════════════════════════════════════════════════════════════
//  SLCM — Applicant Web Form client script
//  Features:
//    • Silent fee recalculation on whether_scstobc_ncl change
//    • Save Draft button (always before the Next/Submit primary button)
//    • Application status badge near the applicant-ID heading
//    • Toast notifications — top-right
//    • Submit intercept: mandatory → eligibility (modal if ineligible) → fee/Razorpay → submit
//    • No live eligibility banner; query-string prefill for /applicant-form/new?...
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
		/* Application ID + status row (inside web-form title h1) */
		'.slcm-app-heading-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px 28px;' +
			'line-height:1.25;margin:0;}',
		'#slcm-app-heading-id{flex:0 1 auto;margin:0;min-width:0;}',
		'#slcm-app-heading-meta{display:inline-flex;align-items:center;flex-wrap:wrap;gap:6px 10px;' +
			'flex:0 1 auto;margin:0;}',
		'#slcm-app-status-label{font-size:13px;font-weight:500;color:#334155;line-height:1.2;' +
			'white-space:nowrap;margin:0;}',
		/* Application status badge */
		'.slcm-status-badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;' +
			'font-size:11px;font-weight:700;letter-spacing:.4px;line-height:1.2;text-transform:uppercase;}',
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
			'background:#1a73e8;color:#fff;border:none;font-weight:600;cursor:pointer;font-size:14px;' +
			'display:inline-flex;align-items:center;justify-content:center;gap:8px;}',
		'#slcm-fee-pay-btn:disabled{opacity:.6;cursor:not-allowed;}',
		'#slcm-fee-later-btn{flex:1;padding:10px 0;border-radius:8px;' +
			'background:#f1f5f9;color:#334155;border:1.5px solid #cbd5e1;font-weight:600;cursor:pointer;font-size:14px;}',
		/* Top-bar: Back (left) + Receipt icon-btn (right) */
		'#slcm-form-topbar{display:flex;align-items:center;justify-content:space-between;' +
			'padding:8px 4px 4px;margin-bottom:4px;}',
		'#slcm-back-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px 6px 10px;' +
			'border-radius:8px;font-size:13px;font-weight:600;border:1.5px solid #cbd5e1;' +
			'background:#f8fafc;color:#334155;cursor:pointer;text-decoration:none;' +
			'transition:background .15s,border-color .15s;}',
		'#slcm-back-btn:hover{background:#f1f5f9;border-color:#94a3b8;color:#1e293b;}',
		'#slcm-fee-receipt-wrap{display:flex;align-items:center;}',
		'#slcm-fee-receipt-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px 6px 10px;' +
			'border-radius:8px;font-size:13px;font-weight:600;border:1.5px solid #1a73e8;' +
			'background:#fff;color:#1a73e8;cursor:pointer;transition:background .15s;}',
		'#slcm-fee-receipt-btn:hover{background:#e8f0fe;border-color:#1558b0;}',
		/* Submit progress overlay */
		'#slcm-submit-overlay{position:fixed;inset:0;z-index:99997;background:rgba(255,255,255,.8);' +
			'display:none;align-items:center;justify-content:center;flex-direction:column;gap:14px;' +
			'font-size:1rem;color:#334155;font-weight:500;}',
		'#slcm-submit-overlay.open{display:flex;}',
		'#slcm-submit-spinner{width:36px;height:36px;border:4px solid #e2e8f0;' +
			'border-top-color:#1a73e8;border-radius:50%;animation:slcm-spin .8s linear infinite;}',
		/* Eligibility Evaluation Results (portal submit) */
		'#slcm-ee-modal{position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;padding:16px;}',
		'#slcm-ee-modal.open{display:flex;}',
		'#slcm-ee-backdrop{position:absolute;inset:0;background:rgba(15,23,42,.55);backdrop-filter:blur(2px);}',
		'#slcm-ee-panel{position:relative;background:#fff;border-radius:16px;width:100%;max-width:640px;max-height:90vh;' +
			'overflow:hidden;display:flex;flex-direction:column;box-shadow:0 25px 50px -12px rgba(0,0,0,.25);}',
		'#slcm-ee-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:20px 22px 16px;' +
			'border-bottom:1px solid #e2e8f0;flex-shrink:0;}',
		'#slcm-ee-title{margin:0;font-size:1.15rem;font-weight:700;color:#0f172a;line-height:1.35;}',
		'#slcm-ee-close{border:none;background:#f1f5f9;color:#64748b;width:36px;height:36px;border-radius:10px;' +
			'cursor:pointer;font-size:1.25rem;line-height:1;flex-shrink:0;}',
		'#slcm-ee-close:hover{background:#e2e8f0;color:#334155;}',
		'#slcm-ee-body{padding:18px 22px 22px;overflow-y:auto;flex:1;}',
		'.slcm-ee-alert{display:flex;gap:12px;padding:14px 16px;background:#fff1f2;border:1px solid #fecdd3;' +
			'border-left:4px solid #e11d48;border-radius:10px;margin-bottom:18px;}',
		'.slcm-ee-alert-dot{width:10px;height:10px;background:#e11d48;border-radius:50%;flex-shrink:0;margin-top:4px;}',
		'.slcm-ee-alert-text{font-size:14px;line-height:1.55;color:#334155;}',
		'.slcm-ee-subhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;margin-bottom:8px;}',
		'.slcm-ee-subhead strong{font-size:15px;color:#0f172a;}',
		'.slcm-ee-meta{font-size:12px;color:#64748b;}',
		'.slcm-ee-summary{display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:13px;color:#475569;}',
		'.slcm-ee-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;}',
		'#slcm-ee-table{width:100%;border-collapse:separate;border-spacing:0;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;font-size:13px;}',
		'#slcm-ee-table th{text-align:left;padding:11px 14px;background:#f8fafc;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0;}',
		'#slcm-ee-table th.slcm-ee-th-actions{text-align:center;width:140px;}',
		'#slcm-ee-table td{padding:11px 14px;border-bottom:1px solid #f1f5f9;vertical-align:middle;color:#1e293b;}',
		'#slcm-ee-table tr:last-child td{border-bottom:none;}',
		'.slcm-ee-status{display:inline-flex;align-items:center;gap:6px;font-weight:500;color:#15803d;}',
		'.slcm-ee-badge{font-size:10px;padding:2px 8px;border-radius:999px;background:#3b82f6;color:#fff;font-weight:700;}',
		'.slcm-ee-switch{padding:7px 14px;border-radius:8px;border:none;background:#1d4ed8;color:#fff;font-size:12px;font-weight:600;cursor:pointer;}',
		'.slcm-ee-switch:hover{background:#1e40af;}',
		'.slcm-ee-switch:disabled{opacity:.55;cursor:not-allowed;}',
		'#slcm-ee-foot{padding:14px 22px 18px;border-top:1px solid #e2e8f0;flex-shrink:0;}',
		'#slcm-ee-dismiss{width:100%;padding:11px;border-radius:10px;border:1px solid #cbd5e1;background:#fff;' +
			'color:#334155;font-weight:600;cursor:pointer;font-size:14px;}',
		'#slcm-ee-dismiss:hover{background:#f8fafc;}',
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

/** Absolute URL for /api/... paths — Web Form runs on website bundle (no frappe.urllib). */
function slcmPortalAbsUrl(path) {
	var p = path || '';
	if (p.charAt(0) !== '/') p = '/' + p;
	if (typeof frappe !== 'undefined' && frappe.urllib && typeof frappe.urllib.get_full_url === 'function') {
		return frappe.urllib.get_full_url(p);
	}
	var origin = (typeof window !== 'undefined' && window.location && window.location.origin) || '';
	return origin + p;
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

// ───────────────────────────────────────────────────────────────────
//  APPLICATION STATUS BADGE — injected near the applicant-ID heading
// ───────────────────────────────────────────────────────────────────
function _statusBadgeClass(status) {
	var baseClass = 'slcm-status-badge ';
	if (!status) return baseClass + 'slcm-status-other';
	var s = status.toLowerCase();
	if (s === 'draft')     return baseClass + 'slcm-status-draft';
	if (s === 'submitted') return baseClass + 'slcm-status-submitted';
	return baseClass + 'slcm-status-other';
}

function updateStatusBadge(status) {
	var badge = document.getElementById('slcm-app-status-badge');
	if (!badge) return;
	badge.className = _statusBadgeClass(status);
	badge.textContent = status || '';
	badge.style.display = status ? '' : 'none';

	// Make sure the label is present before the badge
	var label = document.getElementById('slcm-app-status-label');
	if (badge.parentNode && !label) {
		label = document.createElement('span');
		label.id = 'slcm-app-status-label';
		label.className = 'slcm-app-status-label';
		label.textContent = 'Application Status: ';
		badge.parentNode.insertBefore(label, badge);
	}
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

			var titleEl = $title[0];
			var idText = (titleEl.textContent || '').replace(/\s+/g, ' ').trim();
			titleEl.textContent = '';
			titleEl.classList.add('slcm-app-heading-row');

			var idSpan = document.createElement('span');
			idSpan.id = 'slcm-app-heading-id';
			idSpan.textContent = idText;

			var label = document.createElement('span');
			label.id = 'slcm-app-status-label';
			label.className = 'slcm-app-status-label';
			label.textContent = 'Application Status: ';

			var badge = document.createElement('span');
			badge.id = 'slcm-app-status-badge';
			var initStatus = resolveField('application_status');
			badge.className = _statusBadgeClass(initStatus);
			badge.textContent = initStatus || '';
			badge.style.display = initStatus ? '' : 'none';

			var meta = document.createElement('span');
			meta.id = 'slcm-app-heading-meta';
			meta.appendChild(label);
			meta.appendChild(badge);

			titleEl.appendChild(idSpan);
			titleEl.appendChild(meta);
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
				// Set directly on doc — avoids triggering a Frappe field-refresh
				// cascade that would call set_formatted_input on the phone control
				// before its async make_input() has finished.
				try { if (wf && wf.doc) wf.doc.application_status = 'Draft'; } catch (e) {}
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
			// Frappe order: Discard → Next (after discard) → Submit. Place Save Draft before Discard.
			var $discard = $('.web-form-footer .right-area .discard-btn').first();
			if ($discard.length) {
				$discard.before($btn);
			} else {
				$primary.before($btn);
			}
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
				try {
					if (wf && wf.doc) wf.doc.application_fee_amount = fee;
				} catch (e) {}
				if (doc && doc !== (wf && wf.doc)) {
					try { doc.application_fee_amount = fee; } catch (e) {}
				}
				// Update the visible Currency control (category change must reflect in UI).
				try {
					if (wf && typeof wf.set_value === 'function') {
						wf.set_value('application_fee_amount', fee);
					}
				} catch (e) {}
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

var _feeReceiptBtnInFlight = false;

/** SVG icons for the top-bar buttons */
var _SVG_BACK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>';
var _SVG_DOWNLOAD = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';

/** Ensure the top-bar strip (Back left, Receipt right) exists above the web-form head. */
function _ensureTopBar() {
	if (document.getElementById('slcm-form-topbar')) return null;

	// Find the web-form head to prepend before it
	var $head = $('.web-form-container .web-form-head, .web-form-head').first();
	if (!$head.length) return null;

	var bar = document.createElement('div');
	bar.id = 'slcm-form-topbar';

	// ── Back button (left) ──────────────────────────────────────────
	var backBtn = document.createElement('a');
	backBtn.id = 'slcm-back-btn';
	backBtn.href = '/admission';
	backBtn.title = 'Back to My Applications';
	backBtn.innerHTML = _SVG_BACK + '<span>Back</span>';

	// ── Receipt placeholder (right) — filled later when receipt is ready ──
	var receiptWrap = document.createElement('div');
	receiptWrap.id = 'slcm-fee-receipt-wrap';
	receiptWrap.style.display = 'none'; // hidden until receipt is confirmed

	bar.appendChild(backBtn);
	bar.appendChild(receiptWrap);
	$head.before(bar);
	return receiptWrap;
}

/** Paid + server has Applicant Payment Receipt → show download icon-btn (top-right). */
function syncApplicationFeeReceiptButton() {
	var wf = window.frappe && frappe.web_form;
	if (!wf) return;

	var applicant = getDocName();

	// Always ensure the top-bar (with Back button) is present
	_ensureTopBar();

	if (!applicant) return;

	// Do not block on empty fee status (hidden field may not hydrate); server checks DB.
	var st = (resolveField('application_fee_status') || '').trim();
	var receiptWrap = document.getElementById('slcm-fee-receipt-wrap');

	if (st === 'Pending' || st === 'Requested' || st === 'Waived') {
		if (receiptWrap) receiptWrap.style.display = 'none';
		return;
	}

	// If receipt button already rendered, nothing more to do
	if (document.getElementById('slcm-fee-receipt-btn')) return;
	if (_feeReceiptBtnInFlight) return;

	_feeReceiptBtnInFlight = true;
	frappe.call({
		method: 'slcm.admission.web_form.applicant_form.applicant_form.portal_application_fee_receipt_ready',
		args: { applicant_name: applicant },
		callback: function (r) {
			_feeReceiptBtnInFlight = false;
			var m = r && r.message;
			if (!m || !m.ready) return;

			// Ensure top-bar exists and get the receipt slot
			_ensureTopBar();
			var wrap = document.getElementById('slcm-fee-receipt-wrap');
			if (!wrap || document.getElementById('slcm-fee-receipt-btn')) return;

			// Build compact icon + label button
			var btn = document.createElement('button');
			btn.type = 'button';
			btn.id = 'slcm-fee-receipt-btn';
			btn.title = 'Download application fee receipt';
			btn.innerHTML = _SVG_DOWNLOAD + '<span>Receipt</span>';
			btn.onclick = function () {
				var url =
					slcmPortalAbsUrl(
						'/api/method/slcm.admission.web_form.applicant_form.applicant_form.download_portal_application_fee_receipt'
					) + '?applicant_name=' + encodeURIComponent(applicant);
				var a = document.createElement('a');
				a.href = url;
				a.download = '';
				a.style.display = 'none';
				document.body.appendChild(a);
				a.click();
				setTimeout(function () { document.body.removeChild(a); }, 1000);
			};

			wrap.appendChild(btn);
			wrap.style.display = 'flex';
		},
		error: function () {
			_feeReceiptBtnInFlight = false;
		},
	});
}

function setupApplicationFeeReceiptDownload() {
	// Inject Back button immediately on load (doesn't need receipt check)
	var t = setInterval(function () {
		if (_ensureTopBar() !== null || document.getElementById('slcm-form-topbar')) {
			clearInterval(t);
		}
	}, 400);
	setInterval(syncApplicationFeeReceiptButton, 1200);
}

/** Submitted applications: hide Submit / Save Draft (footer still shows Discard / nav). */
function setupSubmittedFormUX() {
	setInterval(function () {
		if ((resolveField('application_status') || '').trim() !== 'Submitted') return;
		try {
			$('#slcm-save-draft-btn').hide();
			$(
				'.web-form-footer .right-area .submit-btn, ' +
					'.web-form-footer .btn-submit-web-form, ' +
					'form.web-form .submit-btn'
			).hide();
		} catch (e) {}
	}, 700);
}

var _programDerivTimer = null;

/** When Program or Admission Cycle changes, refresh program_level / intake_type / campus (server). */
function scheduleProgramPortalDerivatives() {
	clearTimeout(_programDerivTimer);
	_programDerivTimer = setTimeout(function () {
		var wf = window.frappe && frappe.web_form;
		if (!wf || typeof wf.get_value !== 'function' || typeof wf.set_value !== 'function') {
			return;
		}
		var program = wf.get_value('program');
		if (!program) return;

		frappe.call({
			method: 'slcm.admission.web_form.applicant_form.applicant_form.get_program_portal_derivatives',
			args: {
				program: program,
				admission_cycle: wf.get_value('admission_cycle') || '',
			},
			callback: function (r) {
				var d = r && r.message;
				if (!d) return;
				try {
					if (d.program_level) wf.set_value('program_level', d.program_level);
					if (d.intake_type) wf.set_value('intake_type', d.intake_type);
					if (d.campus) wf.set_value('campus', d.campus);
				} catch (e) {}
				scheduleFeeUpdate();
			},
		});
	}, 320);
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

function _slcmEscapeHtml(s) {
	var d = document.createElement('div');
	d.textContent = s == null ? '' : String(s);
	return d.innerHTML;
}

/**
 * Rich "Eligibility Evaluation Results" dialog (data from check_eligibility API).
 * Includes suggested programmes with Switch — avoids duplicating Frappe server throw UI.
 */
function showEligibilityEvaluationModal(applicantName, res) {
	_injectCSS();
	var sug = (res && res.suggestions) || {};
	var programs = sug.programs || [];
	var reason =
		(res && res.failure_reason) ||
		(res && res.message) ||
		'You do not meet the eligibility criteria for the selected program.';

	var modal = document.getElementById('slcm-ee-modal');
	if (!modal) {
		modal = document.createElement('div');
		modal.id = 'slcm-ee-modal';
		modal.setAttribute('role', 'dialog');
		modal.setAttribute('aria-modal', 'true');
		modal.innerHTML =
			'<div id="slcm-ee-backdrop"></div>' +
			'<div id="slcm-ee-panel">' +
				'<div id="slcm-ee-head">' +
					'<h2 id="slcm-ee-title">Eligibility evaluation results</h2>' +
					'<button type="button" id="slcm-ee-close" aria-label="Close">\u00d7</button>' +
				'</div>' +
				'<div id="slcm-ee-body">' +
					'<div class="slcm-ee-alert">' +
						'<span class="slcm-ee-alert-dot"></span>' +
						'<div class="slcm-ee-alert-text" id="slcm-ee-reason"></div>' +
					'</div>' +
					'<div id="slcm-ee-programs-wrap"></div>' +
				'</div>' +
				'<div id="slcm-ee-foot">' +
					'<button type="button" id="slcm-ee-dismiss">Close</button>' +
				'</div>' +
			'</div>';
		document.body.appendChild(modal);

		function closeModal() {
			modal.classList.remove('open');
		}
		function onKey(ev) {
			if (ev.key !== 'Escape') return;
			var m = document.getElementById('slcm-ee-modal');
			if (m && m.classList.contains('open')) m._slcmClose && m._slcmClose();
		}

		document.getElementById('slcm-ee-backdrop').onclick = closeModal;
		document.getElementById('slcm-ee-close').onclick = closeModal;
		document.getElementById('slcm-ee-dismiss').onclick = closeModal;
		modal._slcmClose = closeModal;
		document.addEventListener('keydown', onKey);
	}

	var reasonEl = document.getElementById('slcm-ee-reason');
	if (reasonEl) reasonEl.textContent = reason;

	var wrap = document.getElementById('slcm-ee-programs-wrap');
	if (!wrap) return;

	if (!programs.length) {
		wrap.innerHTML =
			'<p style="margin:0;font-size:13px;color:#64748b;">No alternative programmes were found at the same level.</p>';
		modal.classList.add('open');
		return;
	}

	var metaParts = [];
	if (sug.campus) metaParts.push(sug.campus);
	if (sug.cycle) metaParts.push(sug.cycle);
	if (sug.level) metaParts.push(sug.level);
	var metaStr = metaParts.join(' \u00b7 ');

	var ec = sug.eligible_count != null ? sug.eligible_count : programs.length;
	var tc = sug.total_count != null ? sug.total_count : programs.length;

	var rows = programs
		.map(function (p) {
			var name = p.program_name || p.program || '';
			var pid = p.program || '';
			var sel = !!p.selected;
			var progCell =
				'<strong>' +
				_slcmEscapeHtml(name) +
				'</strong>' +
				(sel
					? ' <span class="slcm-ee-badge">Current</span>'
					: '');
			var statusCell =
				'<span class="slcm-ee-status"><span class="slcm-ee-dot"></span> Eligible</span>';
			var actionCell = sel
				? '<span style="color:#94a3b8;font-size:12px;">\u2014</span>'
				: '<button type="button" class="slcm-ee-switch" data-program="' +
					_slcmEscapeHtml(pid) +
					'">Switch</button>';
			return (
				'<tr>' +
				'<td>' +
				progCell +
				'</td>' +
				'<td style="text-align:center;">' +
				statusCell +
				'</td>' +
				'<td style="text-align:center;" class="slcm-ee-td-switch">' +
				actionCell +
				'</td>' +
				'</tr>'
			);
		})
		.join('');

	wrap.innerHTML =
		'<div class="slcm-ee-subhead">' +
		'<strong>Suggested eligible programmes</strong>' +
		(metaStr ? '<span class="slcm-ee-meta">\u2014 ' + _slcmEscapeHtml(metaStr) + '</span>' : '') +
		'</div>' +
		'<div class="slcm-ee-summary">' +
		'<span class="slcm-ee-dot"></span>' +
		'<span><strong>' +
		ec +
		'</strong> eligible programme' +
		(ec === 1 ? '' : 's') +
		' found</span>' +
		'<span style="color:#94a3b8;">(' +
		tc +
		' total at this level)</span>' +
		'</div>' +
		'<div style="overflow-x:auto;">' +
		'<table id="slcm-ee-table">' +
		'<thead><tr>' +
		'<th>Programme</th>' +
		'<th style="text-align:center;">Status</th>' +
		'<th class="slcm-ee-th-actions">Action</th>' +
		'</tr></thead>' +
		'<tbody>' +
		rows +
		'</tbody></table></div>';

	wrap.querySelectorAll('.slcm-ee-switch').forEach(function (btn) {
		btn.onclick = function () {
			var prog = btn.getAttribute('data-program');
			if (!prog || !applicantName) return;
			btn.disabled = true;
			frappe.call({
				method: 'slcm.admission.web_form.applicant_form.applicant_form.switch_applicant_program',
				args: { applicant_name: applicantName, program: prog },
				callback: function (r) {
					var m = r && r.message;
					if (m && m.status === 'success') {
						if (modal._slcmClose) modal._slcmClose();
						showToast(m.message || 'Programme updated.', 'success');
						window.location.reload();
					} else {
						btn.disabled = false;
						showToast((m && m.message) || 'Could not switch programme.', 'error');
					}
				},
				error: function () {
					btn.disabled = false;
					showToast('Could not switch programme.', 'error');
				},
			});
		};
	});

	modal.classList.add('open');
}

function _feePayBtnSetLoading(payBtn, loading, label) {
	if (!payBtn) return;
	if (loading) {
		payBtn.innerHTML =
			'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
			'style="animation:slcm-spin .8s linear infinite;flex-shrink:0" aria-hidden="true">' +
			'<path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>' +
			'<span>' + (label || 'Opening\u2026') + '</span>';
	} else {
		payBtn.textContent = 'Pay Now';
	}
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
	var payBtnEl = document.getElementById('slcm-fee-pay-btn');
	if (payBtnEl) {
		payBtnEl.disabled = false;
		_feePayBtnSetLoading(payBtnEl, false);
	}
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
		_feePayBtnSetLoading(payBtn, true, 'Creating order\u2026');

		frappe.call({
			method: 'slcm.api.service.fee_service.create_application_fee_razorpay_order',
			args: { applicant_name: feeDetails.applicant_name },
			callback: function (r) {
				var d = r && r.message;
				if (!d || !d.order_id) {
					payBtn.disabled = false;
					_feePayBtnSetLoading(payBtn, false);
					showToast('Could not create payment order. Please try again.', 'error');
					return;
				}

				if (typeof Razorpay === 'undefined') {
					_feePayBtnSetLoading(payBtn, true, 'Loading checkout\u2026');
					// Try loading dynamically
					var sc = document.createElement('script');
					sc.src = 'https://checkout.razorpay.com/v1/checkout.js';
					sc.onload = function () { _openRazorpay(d, feeDetails, onPaid, payBtn, closeModal); };
					sc.onerror = function () {
						payBtn.disabled = false;
						_feePayBtnSetLoading(payBtn, false);
						showToast('Payment gateway script failed to load. Please refresh.', 'error');
					};
					document.head.appendChild(sc);
				} else {
					_feePayBtnSetLoading(payBtn, true, 'Opening checkout\u2026');
					_openRazorpay(d, feeDetails, onPaid, payBtn, closeModal);
				}
			},
			error: function () {
				payBtn.disabled = false;
				_feePayBtnSetLoading(payBtn, false);
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
					_feePayBtnSetLoading(payBtn, false);
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
					_feePayBtnSetLoading(payBtn, false);
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
		_feePayBtnSetLoading(payBtn, false);
	});

	rzp.open();
	payBtn.disabled = false;
	_feePayBtnSetLoading(payBtn, false);
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
				try { if (frappe.web_form && frappe.web_form.doc) frappe.web_form.doc.application_status = 'Submitted'; } catch (e) {}
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
						showEligibilityEvaluationModal(applicantName, res || {});
						return;
					}
					if (res.status === 'Error') {
						_hideSubmitOverlay();
						showToast('\u26a0  ' + ((res && res.message) || 'Eligibility check failed.'), 'error');
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
	var wf = frappe.web_form;
	if (!wf || wf._slcm_save_patched) return;
	wf._slcm_save_patched = true;
	var _origSave = wf.save.bind(wf);

	/**
	 * Frappe wires: $(".web-form").on("submit", () => this.save());
	 * WebForm.save() must return false so jQuery cancels the native form submit;
	 * otherwise the browser reloads and any modal (e.g. ineligible) disappears.
	 */
	wf.save = function () {
		if ((resolveField('application_status') || '').trim() === 'Submitted') {
			var $sb = $(
				'.web-form-footer .right-area .btn-primary, ' +
					'.web-form-footer .btn-submit-web-form, ' +
					'form.web-form .submit-btn'
			).first();
			var bt = ($sb.text() || '').trim().toLowerCase();
			if (bt === 'submit' || bt.indexOf('submit') !== -1) {
				showToast('This application has already been submitted.', 'info');
				return false;
			}
		}

		var isLastPage = false;
		try {
			var me = frappe.web_form;
			if (me.is_new && me.is_new()) {
				isLastPage = false;
			} else if (typeof me.current_section !== 'undefined') {
				var sections = $('.web-form-page').length || (me.pages && me.pages.length) || 1;
				isLastPage = me.current_section >= sections - 1;
			} else {
				isLastPage = true;
			}
		} catch (e) {
			isLastPage = false;
		}

		var $btn = $(
			'.web-form-footer .right-area .btn-primary, ' +
				'.web-form-footer .btn-submit-web-form, ' +
				'form.web-form .submit-btn'
		).first();
		var btnText = ($btn.text() || '').trim().toLowerCase();
		var looksLikeSubmit =
			btnText === 'submit' ||
			btnText.indexOf('submit') !== -1 ||
			($('.submit-btn:visible').length > 0 && !$('.btn-next:visible').length);

		if (isLastPage || looksLikeSubmit) {
			runSubmitFlow();
			return false;
		}
		return _origSave();
	};
}

// ───────────────────────────────────────────────────────────────────
//  QUERY PREFILL — /applicant-form/new?program=...&admission_cycle=...
// ───────────────────────────────────────────────────────────────────
function isNewApplicantWebForm() {
	var path = (window.location.pathname || '').toLowerCase();
	if (path.indexOf('/new') !== -1) return true;
	return !getDocName();
}

function applyQueryStringPrefill() {
	var params = new URLSearchParams(window.location.search);
	if (!params.get('program') && !params.get('admission_cycle')) return;

	var tries = 0;
	var t = setInterval(function () {
		tries++;
		var wf = window.frappe && frappe.web_form;
		if (!wf || typeof wf.set_value !== 'function') {
			if (tries > 120) clearInterval(t);
			return;
		}
		clearInterval(t);
		if (!isNewApplicantWebForm()) return;

		var pairs = [
			['program', 'program'],
			['admission_cycle', 'admission_cycle'],
			['campus', 'campus'],
			['intake_type', 'intake_type'],
			['admission_year', 'admission_year'],
			['academic_year', 'academic_year'],
			['program_level', 'program_level'],
		];
		pairs.forEach(function (x) {
			var v = params.get(x[0]);
			if (v) {
				try {
					wf.set_value(x[1], v);
				} catch (e) {}
			}
		});
		scheduleFeeUpdate();
	}, 80);
}

// ───────────────────────────────────────────────────────────────────
//  BOOTSTRAP
// ───────────────────────────────────────────────────────────────────
frappe.ready(function () {
	_injectCSS();

	try {
		$('#eligibility-alert-box').remove();
	} catch (e) {}

	// Fee (silent)
	bindFeeListener();
	setTimeout(updateFeeForCategory, 600);

	// Program → program_level (and related) when user edits Program or Admission Cycle
	var _bindProgN = 0;
	var _bindProgTimer = setInterval(function () {
		_bindProgN++;
		var wf = window.frappe && frappe.web_form;
		if (wf && typeof wf.on === 'function') {
			clearInterval(_bindProgTimer);
			try {
				wf.on('program', scheduleProgramPortalDerivatives);
				wf.on('admission_cycle', scheduleProgramPortalDerivatives);
			} catch (e) {}
		} else if (_bindProgN > 120) {
			clearInterval(_bindProgTimer);
		}
	}, 80);

	applyQueryStringPrefill();

	// Status badge
	setupStatusBadge();

	// Save Draft button (re-polls on every step change)
	setupSaveDraftButton();

	setupApplicationFeeReceiptDownload();
	setupSubmittedFormUX();

	// Submit intercept (retry: web form may attach after this script's first frappe.ready)
	interceptSubmit();
	var _patchAttempts = 0;
	var _patchTimer = setInterval(function () {
		interceptSubmit();
		if ((frappe.web_form && frappe.web_form._slcm_save_patched) || ++_patchAttempts > 60) {
			clearInterval(_patchTimer);
		}
	}, 150);
});
