// ═══════════════════════════════════════════════════════════════════
//  SLCM — PACE Application Web Form client script
//  Features:
//    • Portal nav/footer shell with Applicant Portal Config theme
//    • Application status badge
//    • Save Draft button with server-side persistence
//    • Stage progress bar (stepper) with mandatory validation
//    • Upload Student Photo inline preview
//    • Attach / Attach Image file type + size validation
//    • Date of Birth: age ≥ 17 enforcement, datepicker capped
//    • Phone number with country-based digit-length validation
//    • Toast notifications — top-right
//    • Numeric field restrictions
// ═══════════════════════════════════════════════════════════════════

// ───────────────────────────────────────────────────────────────────
//  UTILITIES
// ───────────────────────────────────────────────────────────────────
function _paceEsc(s) {
	var d = document.createElement('div');
	d.textContent = s == null ? '' : String(s);
	return d.innerHTML;
}

// ───────────────────────────────────────────────────────────────────
//  CSS INJECTION
// ───────────────────────────────────────────────────────────────────
function _paceInjectCSS() {
	if (document.getElementById('pace-wf-css')) return;

	var s = document.createElement('style');
	s.id = 'pace-wf-css';
	s.textContent = [
		/* ── Toast ── */
		'#pace-toast{position:fixed;top:40px;right:24px;z-index:2500000;max-width:min(420px,calc(100vw - 32px));' +
			'min-width:260px;padding:13px 18px;border-radius:10px;font-size:13.5px;font-weight:500;line-height:1.5;' +
			'pointer-events:auto;box-shadow:0 8px 32px rgba(0,0,0,.18);display:none;cursor:default;transition:opacity .3s;}',
		'#pace-toast.pace-success{background:#f0fdf4;border:1.5px solid #86efac;color:#14532d;}',
		'#pace-toast.pace-error  {background:#fff2f2;border:1.5px solid #fca5a5;color:#991b1b;}',
		'#pace-toast.pace-info   {background:#eff6ff;border:1.5px solid #93c5fd;color:#1e3a5f;}',
		'#pace-toast.pace-warn   {background:#fffbeb;border:1.5px solid #fcd34d;color:#78350f;}',
		/* ── Spin ── */
		'@keyframes pace-spin{to{transform:rotate(360deg)}}',
		/* ── Hide default Frappe nav/footer ── */
		'header.navbar,nav.navbar,.web-header,.web-navbar,#navbar-main,' +
		'header[class*="navbar"],.website-header,.website-footer,footer.footer,#footer-main{display:none!important;}',
		'.page-content{margin-top:0!important;padding-top:0!important;}',
		'.main-section{padding-top:0!important;}',
		/* ── Portal nav ── */
		'.pace-nav{background:var(--pace-primary,#1a3c6e);padding:10px 24px;display:flex;align-items:center;' +
			'justify-content:space-between;height:60px;position:sticky;top:0;z-index:1020;box-shadow:0 2px 8px rgba(0,0,0,.15);}',
		'.pace-nav-brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:#fff;' +
			'font-weight:700;font-size:clamp(14px,4vw,18px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:65%;}',
		'.pace-nav-brand img{height:clamp(28px,6vw,36px);width:auto;flex-shrink:0;}',
		'.pace-nav-links{display:flex;gap:clamp(10px,2vw,20px);align-items:center;}',
		'.pace-nav-links a{color:rgba(255,255,255,.85);text-decoration:none;font-size:14px;font-weight:500;}',
		'.pace-nav-links a:hover{color:#fff;}',
		'#pace-avatar-btn{user-select:none;-webkit-user-select:none;transition:all .2s;overflow:hidden;padding:0;}',
		'#pace-avatar-btn:hover{border-color:rgba(255,255,255,.7)!important;box-shadow:0 0 0 3px rgba(255,255,255,.2)!important;}',
		/* ── Portal footer ── */
		'.pace-footer{background:#0f172a;color:#94a3b8;padding:40px 24px 20px;margin-top:48px;font-family:inherit;}',
		'.pace-footer-inner{max-width:1400px;margin:0 auto;display:flex;flex-wrap:wrap;gap:32px;justify-content:space-between;}',
		'.pace-footer-brand{flex:1 1 240px;}',
		'.pace-footer-brand h2{font-size:18px;font-weight:700;color:#fff;margin:0 0 10px;}',
		'.pace-footer-brand p{font-size:13px;line-height:1.6;margin:0;}',
		'.pace-footer-links{flex:1 1 200px;}',
		'.pace-footer-links h4{color:#fff;font-size:11px;font-weight:700;letter-spacing:.1em;margin:0 0 12px;}',
		'.pace-footer-links ul{list-style:none;padding:0;margin:0;}',
		'.pace-footer-links li{margin-bottom:7px;}',
		'.pace-footer-links a{color:#94a3b8;text-decoration:none;font-size:13px;transition:color .2s;}',
		'.pace-footer-links a:hover{color:#fff;}',
		'.pace-footer-bottom{border-top:1px solid rgba(255,255,255,.1);margin-top:28px;padding-top:16px;' +
			'display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;font-size:12px;}',
		/* ── Save Draft button ── */
		'#pace-save-draft-btn{display:inline-flex;align-items:center;gap:7px;padding:7px 18px;' +
			'border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;' +
			'border:1.5px solid var(--pace-primary,#1a3c6e);background:#fff;color:var(--pace-primary,#1a3c6e);' +
			'transition:background .15s,color .15s;white-space:nowrap;margin-right:10px;}',
		'#pace-save-draft-btn:hover:not(:disabled){background:color-mix(in srgb,var(--pace-primary,#1a3c6e) 8%,#fff);}',
		'#pace-save-draft-btn:disabled{opacity:.6;cursor:not-allowed;}',
		/* ── Application status badge ── */
		'.pace-app-heading-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px 28px;line-height:1.25;margin:0;}',
		'#pace-app-heading-id{flex:0 1 auto;margin:0;min-width:0;font-size:clamp(1.2rem,2.4vw,1.65rem);' +
			'font-weight:800;color:var(--pace-primary,#1a3c6e);letter-spacing:-.02em;line-height:1.2;}',
		'#pace-app-heading-meta{display:inline-flex;align-items:center;flex-wrap:wrap;gap:6px 10px;flex:0 1 auto;margin:0;}',
		'.pace-status-badge{display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;' +
			'font-size:11px;font-weight:700;letter-spacing:.4px;line-height:1.2;text-transform:uppercase;}',
		'.pace-status-draft    {background:#fef3c7;color:#92400e;border:1px solid #fcd34d;}',
		'.pace-status-submitted{background:#dcfce7;color:#14532d;border:1px solid #86efac;}',
		'.pace-status-other    {background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;}',
		/* ── Top bar ── */
		'#pace-form-topbar{display:flex;align-items:center;justify-content:space-between;padding:12px 4px;margin-bottom:8px;max-width:1400px;margin-left:auto;margin-right:auto;}',
		'#pace-form-topbar-left{display:flex;align-items:center;gap:20px;}',
		'#pace-back-btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;' +
			'font-size:13px;font-weight:600;border:1.5px solid #e2e8f0;background:#fff;color:#475569;' +
			'cursor:pointer;text-decoration:none!important;transition:all .2s;}',
		'#pace-back-btn:hover{background:#f8fafc;border-color:#cbd5e1;color:#1e293b;}',
		'#pace-applying-for-wrap{font-size:13px;color:#64748b;}',
		'#pace-applying-for-wrap strong{color:#1e293b;margin-left:4px;}',
		/* ── Stepper ── */
		'#pace-stepper-wrap{padding:15px 16px 28px;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none;width:100%;box-sizing:border-box;}',
		'#pace-stepper-wrap::-webkit-scrollbar{display:none;}',
		'.pace-stepper{box-sizing:border-box;width:100%;max-width:100%;min-width:0;padding:0 6px;}',
		'.pace-step{display:flex;flex-direction:row;align-items:center;gap:14px;cursor:pointer;position:relative;' +
			'min-width:104px;max-width:min(220px,32vw);width:max-content;transition:background .25s,border-color .25s;' +
			'padding:10px 10px 10px;border-radius:14px;border:1px solid transparent;background:#f3f4f6;}',
		'.pace-step-connector{align-self:center;width:100%;min-width:12px;height:2px;background:#e5e7eb;border-radius:1px;pointer-events:none;}',
		/* Completed */
		'.pace-step.completed:not(.active){background:#ecfdf5;border-color:#bbf7d0;}',
		'.pace-step.completed .pace-step-circle{border-color:#22c55e;background:#22c55e;color:#fff;}',
		'.pace-step.completed .pace-step-label{color:#166534;}',
		'.pace-step.completed + .pace-step-connector{background:#86efac;}',
		/* Active */
		'.pace-step.active{background:#e0ecfa;border-color:#2471f3;}',
		'.pace-step.active .pace-step-circle{border-color:#2471f3;background:#2471f3;color:#fff;box-shadow:0 0 0 4px rgba(36,113,243,0.13);}',
		'.pace-step.active .pace-step-label{color:#1e3a8a;}',
		/* Default */
		'.pace-step:not(.active):not(.completed){background:#f3f4f6;border-color:#e5e7eb;}',
		'.pace-step:not(.active):not(.completed) .pace-step-circle{border-color:#e5e7eb;background:#fff;color:#9ca3af;}',
		'.pace-step:not(.active):not(.completed) .pace-step-label{color:#9ca3af;}',
		/* Common */
		'.pace-step-circle{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;' +
			'font-size:14px;font-weight:800;border:2px solid #e9d5d8;background:#fff;z-index:2;transition:all 0.25s ease;}',
		'.pace-step-label{font-size:10px;font-weight:700;text-align:left;line-height:1.25;white-space:normal;max-width:13em;transition:color .25s;flex:1;}',
		'.pace-step.active:hover .pace-step-circle{border-color:#1e40af;}',
		'.pace-step.completed:hover .pace-step-circle{border-color:#16a34a;}',
		'.pace-step:hover .pace-step-circle{border-color:#1e40af;}',
		/* Stepper card integration */
		'.web-form-container:has(#pace-stepper-wrap) #pace-stepper-wrap{' +
			'background:#fff;border:1px solid #e2e8f0;border-bottom:none;border-radius:12px 12px 0 0;' +
			'margin:16px 0 0;padding:20px 16px 28px;position:relative;z-index:1;}',
		'.web-form-container:has(#pace-stepper-wrap) form.web-form{' +
			'border:1px solid #e2e8f0!important;border-top:1px solid #eef2f6!important;' +
			'border-radius:0 0 12px 12px!important;background:#fff!important;margin-top:0!important;' +
			'overflow-x:hidden;overflow-y:visible;}',
		'.web-form-container:has(#pace-stepper-wrap) form.web-form .web-form-body{border-top:none!important;}',
		/* Section heading colour driven by theme var */
		'.web-form-container .section-head,.web-form .section-head{color:var(--pace-primary,#1a3c6e)!important;}',
		'.btn-next,.submit-btn,.btn-submit-web-form{background:var(--pace-primary,#1a3c6e)!important;' +
			'border-color:var(--pace-primary,#1a3c6e)!important;color:#fff!important;}',
		/* Student photo */
		'.pace-photo-preview{margin:0 0 14px;display:flex;align-items:flex-start;}',
		'.pace-photo-preview img{display:block;width:140px;height:140px;object-fit:cover;' +
			'border-radius:0;border:2px solid #e2e8f0;box-shadow:0 1px 4px rgba(0,0,0,.06);background:#f8fafc;}',
		/* Field error */
		'.pace-field-error{border-color:#ef4444!important;box-shadow:0 0 0 3px rgba(239,68,68,0.15)!important;}',
		/* Overflow fix */
		'.web-form .form-grid-container,.web-form .form-grid{overflow:visible!important;}',
		/* Small Text field height adjustment */
		'.web-form [data-fieldtype="Small Text"] textarea { height: 86px!important; min-height: 86px!important; transition: border-color 0.2s, box-shadow 0.2s; }',
	].join('');
	document.head.appendChild(s);
}

// ───────────────────────────────────────────────────────────────────
//  DATA HELPERS
// ───────────────────────────────────────────────────────────────────
function _paceGetDocName() {
	var name = frappe.web_form && frappe.web_form.doc && frappe.web_form.doc.name;
	if (!name) {
		var p = new URLSearchParams(window.location.search);
		name = p.get('name') || p.get('doc');
	}
	if (!name && window.location && window.location.pathname) {
		var path = String(window.location.pathname).replace(/\/$/, '');
		var m = path.match(/\/pace-application-form\/([^/]+)(?:\/edit)?$/);
		if (m && m[1] && m[1] !== 'new' && m[1] !== 'list') {
			name = decodeURIComponent(m[1]);
		}
	}
	return name || null;
}

function _paceResolveField(fieldname) {
	var wf = frappe.web_form;
	var val = '';
	try { val = (wf && wf.get_value(fieldname)) || ''; } catch (e) {}
	if (!val && wf && wf.doc) val = wf.doc[fieldname] || '';
	if (!val && frappe.reference_doc) val = frappe.reference_doc[fieldname] || '';
	return val;
}

function _pacePortalLocked() {
	var s = (_paceResolveField('status') || '').trim();
	if (!s) return false;
	return s.toLowerCase() !== 'draft';
}

function _paceCollectDraftData() {
	var wf = frappe.web_form;
	var doc = (wf && wf.doc) || {};
	var data = {};
	try { data = wf.get_values(true) || {}; } catch (e) {}
	// Preserve key fields from doc
	var PRESERVE = ['name', 'programme', 'status'];
	var ref = frappe.reference_doc || {};
	PRESERVE.forEach(function (k) {
		if (!data[k] && doc[k]) data[k] = doc[k];
		if (!data[k] && ref[k])  data[k] = ref[k];
	});
	return data;
}

// ───────────────────────────────────────────────────────────────────
//  TOAST — top-right, auto-dismiss 4 s
// ───────────────────────────────────────────────────────────────────
var _paceToastTimer = null;
function paceShowToast(message, type, durationMs) {
	var el = document.getElementById('pace-toast');
	if (!el) {
		el = document.createElement('div');
		el.id = 'pace-toast';
		el.setAttribute('role', 'alert');
		document.body.appendChild(el);
		el.addEventListener('click', function () {
			el.style.display = 'none';
			if (_paceToastTimer) clearTimeout(_paceToastTimer);
		});
	}
	el.className = 'pace-' + (type || 'info');
	el.textContent = message;
	el.title = 'Click to dismiss';
	el.style.display = 'block';
	if (_paceToastTimer) clearTimeout(_paceToastTimer);
	var ms = typeof durationMs === 'number' && durationMs > 0 ? durationMs : 4000;
	_paceToastTimer = setTimeout(function () { el.style.display = 'none'; }, ms);
}

// ───────────────────────────────────────────────────────────────────
//  PORTAL SHELL — themed nav + footer (Applicant Portal Config)
// ───────────────────────────────────────────────────────────────────
// Module-level store for user data fetched from portal shell
/**
 * Dynamic Applicant Name Sync: concatenates Title + First + Middle + Last
 */
function _paceSetupNameSync() {
	var n = 0;
	var t = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		if (wf && typeof wf.on === 'function') {
			clearInterval(t);
			
			var runSync = function() {
				var t  = (wf.get_value('title') || '').trim();
				var f  = (wf.get_value('first_name') || '').trim();
				var m  = (wf.get_value('middle_name') || '').trim();
				var l  = (wf.get_value('last_name') || '').trim();
				
				var parts = [];
				if (t) parts.push(t);
				if (f) parts.push(f);
				if (m) parts.push(m);
				if (l) parts.push(l);
				
				var fullName = parts.join(' ');
				if (fullName !== (wf.get_value('applicant_name') || '').trim()) {
					wf.set_value('applicant_name', fullName);
				}
			};

			wf.on('title', runSync);
			wf.on('first_name', runSync);
			wf.on('middle_name', runSync);
			wf.on('last_name', runSync);
		}
		if (++n > 100) clearInterval(t);
	}, 200);
}

var _paceUserData = null;

function _paceInjectPortalShell() {
	if (document.getElementById('pace-adm-nav')) return;
	frappe.call({
		method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_pace_portal_shell_data',
		callback: function (r) {
			var d = (r && r.message) || {};
			_paceUserData = d;
			_paceBuildShell(d);
			_paceTriggerPrefill();
		},
		error: function () {
			_paceBuildShell({ primary_color: '#1a3c6e', secondary_color: '#c8a14b', portal_title: 'PACE', user: 'Guest' });
		},
	});
}

/** 
 * Co-ordinates between Portal Shell API and Web Form Lifecycle.
 * Runs prefill as soon as BOTH are ready.
 */
function _paceTriggerPrefill() {
	var n = 0;
	var t = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		// Wait for web_form AND fields_dict AND our shell user data
		if (wf && wf.fields_dict && Object.keys(wf.fields_dict).length > 0 && _paceUserData) {
			clearInterval(t);
			_paceRunPrefill();
		}
		if (++n > 200) clearInterval(t); 
	}, 100);
}

/** Actual prefill execution */
var _pacePrefillDone = false;
function _paceRunPrefill() {
	if (_pacePrefillDone) return;
	
	var wf = window.frappe && frappe.web_form;
	if (!wf || !wf.fields_dict || !_paceUserData) return;

	// Only prefill for NEW applications
	var isNew = false;
	try {
		isNew = wf.doc && (wf.doc['__islocal'] || wf.doc.name === 'new' || !wf.doc.name || wf.is_new);
	} catch (e) {}
	if (!isNew) isNew = (window.location.pathname.indexOf('/new') !== -1);
	
	if (!isNew) return;
	_pacePrefillDone = true;

	var d = _paceUserData;
	var searchParams = new URLSearchParams(window.location.search);
	var programme = searchParams.get('programme');
	var academicYear = searchParams.get('academic_year');

	function applyContextValues() {
		if (programme) try { wf.set_value('programme', programme); } catch (e) {}
		if (academicYear) try { wf.set_value('academic_year', academicYear); } catch (e) {}
	}

	function fillBase() {
		if (d.first_name) try { wf.set_value('first_name', d.first_name); } catch (e) {}
		if (d.middle_name) try { wf.set_value('middle_name', d.middle_name); } catch (e) {}
		if (d.last_name) try { wf.set_value('last_name', d.last_name); } catch (e) {}
		if (d.email) try { wf.set_value('email_address', d.email); } catch (e) {}
		if (d.full_name) try { wf.set_value('applicant_name', d.full_name); } catch (e) {}
	}

	// First pass
	applyContextValues();
	fillBase();
	try { wf.refresh(); } catch (e) {}

	// 2. Check for existing application for THIS programme
	frappe.call({
		method: 'slcm.pace.web_form.pace_application_form.pace_application_form.check_existing_pace_application',
		args: { programme: programme, academic_year: academicYear },
		callback: function (r) {
			var existing = r && r.message;
			if (existing && existing.name) {
				var p = (window.location.pathname || '').replace(/\/$/, '');
				var isNewRoute = p.indexOf('/new') !== -1;
				
				// If we are on /new but there is already an application
				if (isNewRoute) {
					if (existing.status === 'Draft') {
						// Redirect to the existing draft
						var rt = (wf && wf.route) || 'pace-application-form';
						window.location.href = '/' + rt + '/' + encodeURIComponent(existing.name) + '/edit';
						return; 
					} else {
						// It's submitted / verified / etc.
						frappe.msgprint({
							title: __('Already Applied'),
							message: __('You have already submitted an application for <b>{0}</b> (ID: {1}). You cannot start a new application for the same programme.').format(programme, existing.name),
							indicator: 'orange',
							primary_action: {
								label: __('Back to Programmes'),
								action: function() { window.location.href = '/pace'; }
							}
						});
						return;
					}
				}
			}

			// 3. Fallback: Fetch old application (from ANY program) for prefill
			_paceFetchOldPrefill(wf, fillBase, applyContextValues);
		},
		error: function() {
			_paceFetchOldPrefill(wf, fillBase, applyContextValues);
		}
	});

	// Aggressive retry for initial empty fields
	var nRetry = 0;
	var retryT = setInterval(function() {
		applyContextValues();
		fillBase();
		if (++nRetry > 10) clearInterval(retryT);
	}, 1000);
}

/** Wrapper for the historical prefill logic */
function _paceFetchOldPrefill(wf, fillBase, applyContextValues) {
	frappe.call({
		method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_old_pace_application',
		callback: function (r) {
			var oldData = r && r.message;
			var count = 0;
			if (oldData && Object.keys(oldData).length > 0) {
				for (var k in oldData) {
					if (!oldData.hasOwnProperty(k)) continue;
					if (k === 'programme' || k === 'academic_year') continue;
					var val = oldData[k];
					var fd = wf.fields_dict[k];
					
					// Skip attachments except photo
					if (fd && (fd.df.fieldtype === 'Attach' || fd.df.fieldtype === 'Attach Image') && k !== 'upload_student_photo') continue;
					
					try {
						var curr = wf.get_value(k);
						if ((curr === null || curr === undefined || curr === '') && val) {
							if (Array.isArray(val) && fd && fd.grid) {
								fd.grid.df.data = val;
								fd.grid.refresh();
								count++;
							} else if (!Array.isArray(val)) {
								wf.set_value(k, val);
								count++;
							}
						}
					} catch (e2) {}
				}
				if (count > 0) paceShowToast('Form auto-filled from your previous application.', 'success', 5000);
			}
			fillBase();
			applyContextValues();
			try { wf.refresh(); } catch (e) {}
		},
		error: function() {
			fillBase();
			applyContextValues();
			try { wf.refresh(); } catch (e) {}
		}
	});
}





function _paceBuildShell(cfg) {
	if (document.getElementById('pace-adm-nav')) return;

	var primary   = cfg.primary_color   || '#1a3c6e';
	var secondary = cfg.secondary_color || '#c8a14b';
	var title     = cfg.portal_title    || 'PACE';
	var logo      = cfg.banner_image    || '';
	var user      = cfg.user            || 'Guest';
	var isGuest   = (!user || user === 'Guest');
	var fullName  = cfg.full_name       || user || '';
	var userImg   = cfg.user_image      || '';
	var initLetter = fullName ? fullName[0].toUpperCase() : 'U';
	var yr        = new Date().getFullYear();

	// Apply CSS theme variables
	var varStyle = document.createElement('style');
	varStyle.id = 'pace-theme-vars';
	varStyle.textContent =
		':root{--pace-primary:' + primary + ';--pace-secondary:' + secondary + ';}';
	document.head.appendChild(varStyle);

	// ── NAV ──────────────────────────────────────────────────────────
	var nav = document.createElement('nav');
	nav.id        = 'pace-adm-nav';
	nav.className = 'pace-nav';
	nav.innerHTML =
		'<a href="/" class="pace-nav-brand">' +
			(logo ? '<img src="' + _paceEsc(logo) + '" alt="Logo">' : '') +
			_paceEsc(title) +
		'</a>' +
		'<div class="pace-nav-links">' +
			(isGuest
				? '<a href="/login" style="display:inline-flex;align-items:center;background:' + primary + ';color:#fff;padding:8px 20px;border-radius:8px;font-weight:700;font-size:14px;text-decoration:none;">Login / Apply</a>'
				: '<div style="position:relative;display:flex;align-items:center;gap:10px;">' +
					'<button id="pace-avatar-btn" onclick="_paceAvatarToggle(event)"' +
						' style="width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.15);color:#fff;' +
						'border:2px solid rgba(255,255,255,.3);font-weight:800;font-size:15px;cursor:pointer;' +
						'display:flex;align-items:center;justify-content:center;">' +
						(userImg ? '<img src="' + _paceEsc(userImg) + '" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">' : _paceEsc(initLetter)) +
					'</button>' +
					'<span style="color:#fff;font-size:13px;font-weight:600;opacity:.95;cursor:pointer;" onclick="_paceAvatarToggle(event)">' + _paceEsc(fullName) + '</span>' +
					'<div id="pace-avatar-menu" style="display:none;position:absolute;right:0;top:calc(100% + 8px);' +
						'min-width:180px;background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.14);' +
						'border:1px solid rgba(0,0,0,.07);overflow:hidden;z-index:9999;">' +
						'<div style="padding:12px 16px;border-bottom:1px solid #f1f5f9;">' +
							'<div style="font-size:11px;color:#94a3b8;font-weight:600;letter-spacing:.05em;">Signed in as</div>' +
							'<div style="font-size:13px;color:#1e293b;font-weight:700;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:160px;">' + _paceEsc(user) + '</div>' +
						'</div>' +
						'<a href="javascript:void(0)" id="pace-nav-logout" style="display:flex;align-items:center;gap:10px;padding:12px 16px;text-decoration:none;color:#ef4444;font-size:14px;font-weight:600;">Logout</a>' +
					'</div>' +
				'</div>') +
		'</div>';

	document.body.insertBefore(nav, document.body.firstChild);

	// Avatar toggle
	window._paceAvatarToggle = function (e) {
		e.stopPropagation();
		var m = document.getElementById('pace-avatar-menu');
		if (!m) return;
		m.style.display = m.style.display === 'block' ? 'none' : 'block';
	};
	document.addEventListener('click', function (e) {
		var m = document.getElementById('pace-avatar-menu');
		var b = document.getElementById('pace-avatar-btn');
		if (m && !m.contains(e.target) && e.target !== b) m.style.display = 'none';
	});
	var logoutLink = document.getElementById('pace-nav-logout');
	if (logoutLink) {
		logoutLink.addEventListener('click', function () {
			frappe.call({ method: 'logout', callback: function () { window.location.href = '/login'; } });
		});
	}

	// ── FOOTER ───────────────────────────────────────────────────────
	var footer = document.createElement('footer');
	footer.id        = 'pace-adm-footer';
	footer.className = 'pace-footer';
	footer.innerHTML =
		'<div class="pace-footer-inner">' +
			'<div class="pace-footer-brand">' +
				'<h2>' + _paceEsc(title) + '</h2>' +
				'<p>PACE Programme Application Portal — empowering the next generation of professionals.</p>' +
			'</div>' +
			'<div class="pace-footer-links">' +
				'<h4>QUICK LINKS</h4>' +
				'<ul>' +
					'<li><a href="/">Home</a></li>' +
					'<li><a href="/login">My Account</a></li>' +
				'</ul>' +
			'</div>' +
			(cfg.contact_email || cfg.footer_phone || cfg.footer_address
				? '<div class="pace-footer-links"><h4>CONTACT</h4><ul>' +
					(cfg.footer_address ? '<li>' + _paceEsc(cfg.footer_address) + '</li>' : '') +
					(cfg.footer_phone   ? '<li>' + _paceEsc(cfg.footer_phone)   + '</li>' : '') +
					(cfg.contact_email  ? '<li><a href="mailto:' + _paceEsc(cfg.contact_email) + '">' + _paceEsc(cfg.contact_email) + '</a></li>' : '') +
				  '</ul></div>'
				: '') +
		'</div>' +
		'<div class="pace-footer-bottom">' +
			'<span>&copy; ' + yr + ' ' + _paceEsc(title) + '. All rights reserved.</span>' +
			'<span>Powered by <strong style="color:#fff;">SLCM</strong></span>' +
		'</div>';
	document.body.appendChild(footer);
}

/** Legacy stub — actual prefill is now done by _paceRunPrefill via _paceTriggerPrefill */
function pacePrefillUserDetails(d) {
	_paceUserData = d || _paceUserData;
}


// ───────────────────────────────────────────────────────────────────
//  APPLICATION STATUS BADGE
// ───────────────────────────────────────────────────────────────────
function _paceStatusBadgeClass(status) {
	var base = 'pace-status-badge ';
	if (!status) return base + 'pace-status-other';
	var s = status.toLowerCase();
	if (s === 'draft')     return base + 'pace-status-draft';
	if (s === 'submitted') return base + 'pace-status-submitted';
	return base + 'pace-status-other';
}

function _paceUpdateStatusBadge(status) {
	var badge = document.getElementById('pace-app-status-badge');
	if (!badge) return;
	badge.className = _paceStatusBadgeClass(status);
	badge.textContent = status || '';
	badge.style.display = status ? '' : 'none';
}

function paceSetupStatusBadge() {
	if (window._pace_badge_done) return;
	var attempts = 0;
	var t = setInterval(function () {
		attempts++;
		var $title = $(
			'.web-form-wrapper .title-area h1, ' +
			'.web-form-head h1, ' +
			'.page-header h1, ' +
			'.web-form-container .page-title'
		).first();

		if ($title.length && !document.getElementById('pace-app-status-badge')) {
			clearInterval(t);
			window._pace_badge_done = true;

			var titleEl = $title[0];
			var docName = _paceGetDocName();
			var idText = (docName && docName !== 'new' && docName !== 'list') ? docName : (titleEl.textContent || '').replace(/\s+/g, ' ').trim();
			
			titleEl.textContent = '';
			titleEl.classList.add('pace-app-heading-row');

			var idSpan = document.createElement('span');
			idSpan.id = 'pace-app-heading-id';
			idSpan.textContent = idText;

			var label = document.createElement('span');
			label.style.cssText = 'font-size:13px;font-weight:500;color:#334155;white-space:nowrap;';
			label.textContent = 'Status: ';

			var badge = document.createElement('span');
			badge.id = 'pace-app-status-badge';
			var initStatus = _paceResolveField('status');
			badge.className = _paceStatusBadgeClass(initStatus);
			badge.textContent = initStatus || '';
			badge.style.display = initStatus ? '' : 'none';

			var meta = document.createElement('span');
			meta.id = 'pace-app-heading-meta';
			meta.appendChild(label);
			meta.appendChild(badge);

			titleEl.appendChild(idSpan);
			titleEl.appendChild(meta);
		}
		if (attempts > 80) clearInterval(t);
	}, 100);
}

// ───────────────────────────────────────────────────────────────────
//  TOP BAR (Back Button + Applying For)
// ───────────────────────────────────────────────────────────────────
var _SVG_BACK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M15 18l-6-6 6-6"/></svg>';

function paceSetupTopBar() {
	if (document.getElementById('pace-form-topbar')) return;

	var $head = $('.web-form-container .web-form-head, .web-form-head, .web-form-header').first();
	if (!$head.length) $head = $('form.web-form, .web-form-container').first();
	if (!$head.length) return;

	var bar = document.createElement('div');
	bar.id = 'pace-form-topbar';

	var left = document.createElement('div');
	left.id = 'pace-form-topbar-left';

	var back = document.createElement('a');
	back.id = 'pace-back-btn';
	back.href = '/pace';
	back.title = 'Back to PACE Programmes';
	back.innerHTML = _SVG_BACK + '<span>Back</span>';

	var apply = document.createElement('div');
	apply.id = 'pace-applying-for-wrap';
	var prog = _paceResolveField('programme') || '';
	apply.innerHTML = '<span>Applying for:</span> <strong id="pace-applying-for-prog">' + _paceEsc(prog) + '</strong>';

	left.appendChild(back);
	left.appendChild(apply);
	bar.appendChild(left);

	if ($head.is('form')) $head.prepend(bar);
	else $head.before(bar);

	// Sync programme name if it changes (e.g. from prefill)
	setInterval(function() {
		var p = _paceResolveField('programme');
		var el = document.getElementById('pace-applying-for-prog');
		if (p && el && el.textContent !== p) el.textContent = p;
	}, 1000);
}

// ───────────────────────────────────────────────────────────────────
//  SAVE DRAFT BUTTON
// ───────────────────────────────────────────────────────────────────
var _SVG_SAVE =
	'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">' +
	'<path stroke-linecap="round" stroke-linejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/>' +
	'</svg>';

function _paceDraftBtnHTML(loading) {
	if (loading) {
		return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
			'style="animation:pace-spin .8s linear infinite">' +
			'<path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>' +
			'</svg> Saving\u2026';
	}
	return _SVG_SAVE + ' Save Draft';
}

function paceHandleSaveDraft(opts) {
	var btn = document.getElementById('pace-save-draft-btn');
	if (btn) { btn.disabled = true; btn.innerHTML = _paceDraftBtnHTML(true); }

	var data = _paceCollectDraftData();

	return new Promise(function (resolve, reject) {
		frappe.call({
			method: 'slcm.pace.web_form.pace_application_form.pace_application_form.save_pace_draft',
			args: { data: data, ignore_mandatory: (opts && opts.ignore_mandatory === false) ? false : true },
			freeze: false,
			callback: function (r) {
				if (btn) { btn.disabled = false; btn.innerHTML = _paceDraftBtnHTML(false); }
				var msg = r && r.message;
				if (msg && msg.status === 'success') {
					var wf = frappe.web_form;
					// Update URL from /new to /DOCNAME/edit without full reload
					if (msg.name) {
						var p = (window.location.pathname || '').replace(/\/$/, '');
						if (p.endsWith('/new')) {
							var rt = (wf && wf.route) || 'pace-application-form';
							var newPath = '/' + rt + '/' + encodeURIComponent(msg.name) + '/edit';
							try {
								if (wf && wf.doc) wf.doc.name = msg.name;
								if (wf) { wf.is_new = false; wf.in_edit_mode = true; }
								window.history.replaceState({}, '', newPath);
							} catch (e2) {}
						} else if (wf && wf.doc && !wf.doc.name) {
							wf.doc.name = msg.name;
						}
					}
					try { if (wf && wf.doc) wf.doc.status = 'Draft'; } catch (e) {}
					frappe.form_dirty = false;
					_paceUpdateStatusBadge('Draft');
					if (!(opts && opts.silent)) {
						paceShowToast('\u2713  ' + (msg.message || 'Draft saved successfully.'), 'success');
					}
					resolve(msg);
				} else {
					var errMsg = (msg && msg.message) || 'Could not save draft.';
					if (!(opts && opts.silent)) paceShowToast('\u26a0  ' + errMsg, 'error');
					reject(new Error(errMsg));
				}
			},
			error: function () {
				if (btn) { btn.disabled = false; btn.innerHTML = _paceDraftBtnHTML(false); }
				var e = 'Network error. Could not save draft.';
				if (!(opts && opts.silent)) paceShowToast('\u26a0  ' + e, 'error');
				reject(new Error(e));
			},
		});
	});
}

/** Inject Save Draft button just before the primary Next/Submit button */
function paceSetupSaveDraftButton() {
	_paceInjectCSS();
	setInterval(function () {
		if (document.getElementById('pace-save-draft-btn')) return;
		if (_pacePortalLocked()) return; // don't show on submitted forms

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
			var $btn = $('<button type="button" id="pace-save-draft-btn"></button>');
			$btn.html(_paceDraftBtnHTML(false));
			$btn.on('click', function (e) {
				e.preventDefault();
				paceHandleSaveDraft();
			});
			var $discard = $('.web-form-footer .right-area .discard-btn').first();
			if ($discard.length) {
				$discard.before($btn);
			} else {
				$primary.before($btn);
			}
		}
	}, 500);
}

/** Hide Save Draft + Submit when form is locked (submitted / verified / etc.) */
function paceSetupSubmittedFormUX() {
	setInterval(function () {
		if (!_pacePortalLocked()) return;
		try {
			$('#pace-save-draft-btn').hide();
			$('.edit-button, a.edit-button, .btn-edit').hide();
			$(
				'.web-form-footer .right-area .submit-btn, ' +
				'.web-form-footer .btn-submit-web-form, ' +
				'form.web-form .submit-btn'
			).hide();
		} catch (e) {}
	}, 700);
}

// ───────────────────────────────────────────────────────────────────
//  STEPPER — VALIDATION HELPERS (mirrors applicant_form.js logic)
// ───────────────────────────────────────────────────────────────────

/** Layout-only fieldtypes do not hold a value; reqd on them is a config error. */
function _paceIsLayoutFieldtype(ft) {
	if (!ft) return false;
	var layout = { 'Section Break': 1, 'Column Break': 1, 'Page Break': 1,
		            'Tab Break': 1, HTML: 1, Fold: 1, Heading: 1, Button: 1 };
	return !!layout[ft];
}

/** Is an Attach / Attach Image field empty? */
function _paceAttachValueEmpty(val) {
	if (val === undefined || val === null) return true;
	if (typeof val === 'string' && !String(val).trim()) return true;
	return false;
}

/** Is a required Check field unchecked (Frappe is_null(0) is false so core misses it)? */
function _paceCheckUnchecked(val) {
	var n = typeof cint === 'function' ? cint(val) : (val ? 1 : 0);
	return !n;
}

/**
 * Skip forward validation when the form is locked / view-only / allows incomplete saves.
 * Mirrors _slcmStepperSkipForwardValidation from applicant_form.js.
 */
function _paceSkipForwardValidation(wf) {
	if (!wf) return true;
	if (wf.allow_incomplete) return true;
	if (wf.in_view_mode) return true;
	return false;
}

/**
 * Validate all required (and conditionally-required) fields on $page.
 * Returns { ok: boolean, missing: string[] }.
 * Mirrors _validateStage from applicant_form.js.
 */
function _paceValidateStage(wf, $page) {
	var missing = [];
	var seen = {};

	$page.find('[data-fieldname]').each(function () {
		var fieldname = $(this).attr('data-fieldname');
		if (!fieldname || seen[fieldname]) return;
		seen[fieldname] = true;

		var fw = wf.fields_dict[fieldname];
		if (!fw) return;

		var df = fw.df;
		if (_paceIsLayoutFieldtype(df.fieldtype)) return;

		var required = df.reqd;

		// Evaluate mandatory_depends_on expression
		if (!required && df.mandatory_depends_on) {
			try {
				var expr = df.mandatory_depends_on.replace(/^eval:/, '');
				// eslint-disable-next-line no-new-func
				required = !!(new Function('doc', 'return (' + expr + ')')(wf.doc));
			} catch (e) { /* ignore eval errors */ }
		}

		if (!required) return;
		if (fw.$wrapper && fw.$wrapper.is(':hidden')) return;

		var val = wf.get_value(fieldname);
		var errSel = '.form-control,.attached-file,.input-with-feedback,.btn-attach,.control-value,input[type="checkbox"],.checkbox';

		// DOB age check (≥ 17)
		if (fieldname === 'date_of_birth' && val && df.fieldtype === 'Date') {
			var age = _paceAgeYears(val);
			if (age === null || age < 17) {
				fw.$wrapper && fw.$wrapper.find(errSel).addClass('pace-field-error');
				missing.push((df.label || fieldname).trim() + ': must be at least 17 years old');
				return;
			}
		}

		var empty;
		if (df.fieldtype === 'Check') {
			empty = _paceCheckUnchecked(val);
		} else if (df.fieldtype === 'Attach' || df.fieldtype === 'Attach Image') {
			empty = _paceAttachValueEmpty(val);
		} else {
			empty = val === undefined || val === null || val === '' || (Array.isArray(val) && val.length === 0);
		}

		if (empty) {
			fw.$wrapper && fw.$wrapper.find(errSel).addClass('pace-field-error');
			missing.push((df.label || fieldname).trim() || fieldname);
		} else {
			fw.$wrapper && fw.$wrapper.find(errSel).removeClass('pace-field-error');
		}
	});

	return { ok: missing.length === 0, missing: missing };
}

// ───────────────────────────────────────────────────────────────────
//  STEPPER — Progress bar matching the applicant form style
// ───────────────────────────────────────────────────────────────────
function paceSetupStepper() {
	if ($('#pace-stepper-wrap').length) return;

	var _attempts = 0;
	var _timer = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		if (wf && wf.fields && wf.fields.length) {
			clearInterval(_timer);
			_paceRenderStepper(wf);
		} else if (++_attempts > 120) {
			clearInterval(_timer);
		}
	}, 100);
}

function _paceRenderStepper(wf) {
	// Build steps from Page Break fields — first page is always "Basic Details"
	var steps = [{ label: 'Basic Details', index: 0 }];
	(wf.fields || []).forEach(function (f) {
		if (f.fieldtype === 'Page Break' && f.label) {
			steps.push({ label: f.label, index: steps.length });
		}
	});

	// Build grid HTML
	var gridCols = [];
	for (var gi = 0; gi < steps.length; gi++) {
		gridCols.push('max-content');
		if (gi < steps.length - 1) gridCols.push('minmax(12px,1fr)');
	}
	var gridInline =
		'display:grid;width:100%;max-width:100%;box-sizing:border-box;' +
		'grid-template-columns:' + gridCols.join(' ') + ';align-items:center;column-gap:0;row-gap:10px;';

	var html = '<div id="pace-stepper-wrap"><div class="pace-stepper" style="' + gridInline + '">';
	steps.forEach(function (step, i) {
		var lbl = step.label || '';
		var safeTitle = lbl.replace(/"/g, '&quot;').replace(/</g, '&lt;');
		html +=
			'<div class="pace-step" data-index="' + i + '" title="' + safeTitle + '">' +
			'<div class="pace-step-circle">' + (i + 1) + '</div>' +
			'<div class="pace-step-label">' + _paceEsc(lbl) + '</div>' +
			'</div>';
		if (i < steps.length - 1) {
			html += '<div class="pace-step-connector" aria-hidden="true"></div>';
		}
	});
	html += '</div></div>';

	// Inject stepper into DOM
	if ($('.web-form-header').length) {
		$('.web-form-header').after(html);
	} else if ($('.web-form-body').length) {
		$('.web-form-body').before(html);
	} else {
		$('.web-form-container, .page-content').first().prepend(html);
	}

	// Get current page index
	function getCurrentPageIdx() {
		var w = window.frappe && frappe.web_form;
		if (w && typeof w.current_section === 'number' && !isNaN(w.current_section)) {
			return Math.max(0, w.current_section);
		}
		var $pages = $('.web-form .form-layout > .form-page');
		if (!$pages.length) return 0;
		var curr = 0;
		$pages.each(function (i) {
			if ($(this).is(':visible')) curr = i;
		});
		return curr;
	}

	function goToWebFormPage(targetIdx) {
		var w = window.frappe && frappe.web_form;
		if (!w || typeof w.toggle_section !== 'function') return;
		var max = (w.page_breaks && w.page_breaks.length) || 0;
		var idx = Math.max(0, Math.min(targetIdx, max));
		w.current_section = idx;
		w.toggle_section();
	}

	// Update stepper visual state
	function updateStepperUI() {
		var curr = getCurrentPageIdx();
		$('.pace-step').each(function () {
			var idx = parseInt($(this).attr('data-index'), 10);
			$(this).removeClass('active completed');
			if (idx === curr) $(this).addClass('active');
			else if (idx < curr) $(this).addClass('completed');
		});
	}

	// Initial and periodic sync
	updateStepperUI();
	var _stepperSync = setInterval(updateStepperUI, 280);
	$(window).on('beforeunload', function () { clearInterval(_stepperSync); });

	// Sync on Next/Previous clicks
	$(document).on('click', '.btn-next, .btn-previous', function () {
		setTimeout(updateStepperUI, 50);
		setTimeout(updateStepperUI, 200);
	});

	// INTERCEPT Next Click for Validation (Capture phase to run BEFORE Frappe)
	document.addEventListener('click', function(e) {
		var btn = e.target.closest && e.target.closest('.btn-next');
		if (!btn) return;

		var wf = window.frappe && frappe.web_form;
		if (!wf) return;
		
		var $pages = $('.web-form .form-layout > .form-page');
		var $currPage = $pages.filter(':visible').first();
		if (!$currPage.length) return;

		// Find index of current page to show in logs if needed, but we use $currPage for validation
		var skip = _paceSkipForwardValidation(wf);
		if (skip) return;

		var check = _paceValidateStage(wf, $currPage);
		if (!check.ok) {
			// Stop Frappe's internal navigation
			e.preventDefault();
			e.stopPropagation();
			e.stopImmediatePropagation();
			
			var base = __('Please fill all required fields before proceeding.');
			if (check.missing && check.missing.length && typeof frappe !== 'undefined' && frappe.msgprint) {
				frappe.msgprint({
					title: __('Required fields'),
					message: _paceEsc(base) + '<br><br><ul><li>' + check.missing.join('</li><li>') + '</li></ul>',
					indicator: 'red'
				});
			} else {
				paceShowToast(base, 'error');
			}
			return false;
		}
	}, true);

	// Click on stepper step: validate mandatory fields before forward navigation
	$('#pace-stepper-wrap').on('click', '.pace-step', function () {
		var targetIdx = parseInt($(this).attr('data-index'), 10);
		var currentIdx = getCurrentPageIdx();
		var $pages = $('.web-form .form-layout > .form-page');

		if (targetIdx === currentIdx) return;

		if (targetIdx > currentIdx) {
			// Forward navigation: validate current page unless form is locked/view-only
			var skip = _paceSkipForwardValidation(wf);
			var check = skip
				? { ok: true, missing: [] }
				: _paceValidateStage(wf, $($pages.get(currentIdx)));

			if (check.ok) {
				goToWebFormPage(targetIdx);
				setTimeout(updateStepperUI, 50);
			} else {
				var base = __('Please fill all required fields before proceeding.');
				if (check.missing && check.missing.length && typeof frappe !== 'undefined' && frappe.msgprint) {
					frappe.msgprint({
						title: __('Required fields'),
						message:
							_paceEsc(base) +
							'<br><br><ul><li>' +
							check.missing.map(function (lab) { return _paceEsc(lab); }).join('</li><li>') +
							'</li></ul>',
						indicator: 'red',
					});
				} else {
					paceShowToast(base, 'error', 6500);
				}
			}
		} else {
			// Backward navigation: always allowed
			goToWebFormPage(targetIdx);
			setTimeout(updateStepperUI, 50);
		}
	});
}

// ───────────────────────────────────────────────────────────────────
//  STUDENT PHOTO PREVIEW — inline preview for upload_student_photo
// ───────────────────────────────────────────────────────────────────
function _paceNormalizeAttachValue(raw) {
	if (!raw || typeof raw !== 'string') return '';
	var t = raw.trim();
	// Strip "FILENAME,data:..." prefix used by Frappe ControlAttach
	var m = t.match(/^([^:]+),(.+):(.+)$/);
	if (m) return (m[2] + ':' + m[3]).trim();
	return t;
}

function _paceResolvePhotoPath() {
	var wf = window.frappe && frappe.web_form;
	var v = '';
	try {
		v = (wf && wf.get_value && wf.get_value('upload_student_photo')) || '';
	} catch (e) {}
	if (v) return _paceNormalizeAttachValue(String(v));

	var $block = $('[data-fieldname="upload_student_photo"]').first();
	if (!$block.length) return '';

	v = $block.find('input[type="hidden"]').val() || '';
	if (v) return _paceNormalizeAttachValue(v);

	v = $block.find('.attached-file-link').attr('href') || '';
	if (v) return _paceNormalizeAttachValue(v);

	v = ($block.find('.control-value').text() || '').trim();
	if (v) return _paceNormalizeAttachValue(v);

	v = $block.find('a[target="_blank"]').attr('href') || '';
	if (v) return _paceNormalizeAttachValue(v);

	return '';
}

function _pacePhotoToImgSrc(path) {
	if (!path) return '';
	if (/^data:/i.test(path)) return path;
	if (/^https?:\/\//i.test(path)) return path;
	var rel = path.charAt(0) === '/' ? path : '/' + path;
	var parts = rel.split('/');
	var enc = parts.map(function (seg, i) {
		if (i === 0) return seg;
		return encodeURIComponent(seg).replace(/'/g, '%27');
	});
	var origin = (typeof window !== 'undefined' && window.location && window.location.origin) || '';
	return origin + enc.join('/');
}

function _paceSyncPhotoPreview() {
	var path = _paceResolvePhotoPath();
	var $block = $('[data-fieldname="upload_student_photo"]').first();
	if (!$block.length) return;

	var $ctrl = $block.closest('.frappe-control');
	var $wrap = $ctrl.length ? $ctrl : $block.parent();

	var $prev = $wrap.children('#pace-student-photo-preview').first();
	if (!path) {
		$prev.remove();
		return;
	}
	var src = _pacePhotoToImgSrc(path);
	if (!src) { $prev.remove(); return; }

	if (!$prev.length) {
		$prev = $('<div id="pace-student-photo-preview" class="pace-photo-preview"><img alt="Student photo preview" decoding="async" /></div>');
		$wrap.prepend($prev);
	}
	var $img = $prev.find('img');
	if ($img.attr('data-pace-src') !== src) {
		$img.attr('data-pace-src', src).attr('src', src);
	}
}

function paceSetupPhotoPreview() {
	_paceSyncPhotoPreview();
	setInterval(_paceSyncPhotoPreview, 450);

	$(document).on('click', '.btn-next, .btn-previous', function () {
		setTimeout(_paceSyncPhotoPreview, 120);
	});

	var bindN = 0;
	var bindTimer = setInterval(function () {
		bindN++;
		var wf = window.frappe && frappe.web_form;
		if (wf && wf.fields_dict && wf.fields_dict.upload_student_photo && !wf._pace_photo_on) {
			wf._pace_photo_on = true;
			try { wf.on('upload_student_photo', _paceSyncPhotoPreview); } catch (e) {}
		}
		if (bindN > 100) clearInterval(bindTimer);
	}, 100);
}

// ───────────────────────────────────────────────────────────────────
//  ATTACH FIELD VALIDATION — file type + size limits
//  • All Attachments: max 1 MB
//  • Student Photo: png, jpeg, jpg only
//  • All Other Docs: png, jpeg, jpg, pdf allowed
// ───────────────────────────────────────────────────────────────────
var _PACE_IMG_MAX = 1 * 1024 * 1024;       // 1 MB
var _PACE_DOC_MAX = 1 * 1024 * 1024;       // 1 MB
var _PACE_IMG_EXTS = ['png', 'jpeg', 'jpg'];
var _PACE_DOC_EXTS = ['png', 'jpeg', 'jpg', 'pdf'];
var _PACE_IMG_TYPES = ['.png', '.jpeg', '.jpg', '.jpe', 'image/png', 'image/jpeg', 'image/jpg'];
var _PACE_DOC_TYPES = ['.png', '.jpeg', '.jpg', '.jpe', '.pdf', 'image/png', 'image/jpeg', 'image/jpg', 'application/pdf'];

function _paceValidateFile(file, fieldtype) {
	if (!file) return true;
	var ext = (file.name || '').split('.').pop().toLowerCase();
	var isImg = (fieldtype === 'Attach Image' || (window._paceLastAttachCtx && _paceLastAttachCtx.fieldname === 'upload_student_photo'));
	var allowed = isImg ? _PACE_IMG_EXTS : _PACE_DOC_EXTS;
	var maxBytes = _PACE_IMG_MAX;
	var maxLabel = '1 MB';

	if (allowed.indexOf(ext) === -1) {
		paceShowToast(
			'\u26a0 Invalid file type ".' + ext + '". ' +
			(isImg ? 'Use png, jpeg, or jpg only (max 1 MB).' : 'Use png, jpeg, jpg, or pdf only (max 1 MB).'),
			'error'
		);
		return false;
	}
	if (file.size > maxBytes) {
		paceShowToast(
			'\u26a0 File "' + file.name + '" exceeds the ' + maxLabel + ' limit (' +
			(file.size / (1024 * 1024)).toFixed(1) + ' MB).',
			'error'
		);
		return false;
	}
	return true;
}

/** Track which Attach field was clicked (uploader modal is outside form DOM). */
function paceSetupAttachClickContext() {
	document.addEventListener('click', function (e) {
		var t = e.target && e.target.closest && e.target.closest('.btn-attach');
		if (!t || !window.frappe || !frappe.web_form) return;
		var ctrl = t.closest('.frappe-control[data-fieldtype]');
		if (!ctrl) return;
		var ft = ctrl.getAttribute('data-fieldtype');
		if (ft !== 'Attach' && ft !== 'Attach Image') return;
		window._paceLastAttachCtx = {
			fieldtype: ft,
			fieldname: ctrl.getAttribute('data-fieldname') || '',
			ts: Date.now(),
		};
	}, true);
}

/** Override Frappe FileUploader constructor to enforce allowed_file_types + max_file_size. */
function _paceWrapFileUploader() {
	if (!window.frappe || !frappe.ui || !frappe.ui.FileUploader) return;
	if (frappe.ui.FileUploader._paceWrapped) return;

	var Original = frappe.ui.FileUploader;

	function PaceFileUploader(opts) {
		opts = opts || {};
		// Always public uploads for PACE forms
		opts.is_private = 0;

		if (frappe.web_form && window._paceLastAttachCtx) {
			var ctx = window._paceLastAttachCtx;
			if (Date.now() - (ctx.ts || 0) < 120000) {
				var base = Object.assign({}, opts.restrictions || {});
				var isPhoto = ctx.fieldname === 'upload_student_photo';

				opts.restrictions = Object.assign(base, {
					max_file_size: _PACE_IMG_MAX,
					allowed_file_types: (isPhoto ? _PACE_IMG_TYPES : _PACE_DOC_TYPES).slice(),
				});
			}
		}
		return new Original(opts);
	}

	PaceFileUploader.UploadOptions = Original.UploadOptions;
	PaceFileUploader._paceWrapped = true;
	frappe.ui.FileUploader = PaceFileUploader;
}

function paceSetupAttachValidation() {
	paceSetupAttachClickContext();

	// Validate file on input change
	document.addEventListener('change', function (e) {
		var input = e.target;
		if (!input || input.type !== 'file' || !window.frappe || !frappe.web_form) return;

		var inForm = input.closest('.web-form-container, form.web-form, .web-form-wrapper');
		var inUploader = input.closest('.file-uploader');
		var ctx = window._paceLastAttachCtx;
		var ft = null;

		if (inForm) {
			var ctrl = input.closest('[data-fieldtype]');
			ft = ctrl ? ctrl.getAttribute('data-fieldtype') : null;
		} else if (inUploader && ctx && Date.now() - (ctx.ts || 0) < 120000) {
			ft = ctx.fieldtype;
		} else {
			return;
		}

		if (ft !== 'Attach' && ft !== 'Attach Image') return;
		var file = input.files && input.files[0];
		if (!file) return;

		if (!_paceValidateFile(file, ft)) {
			input.value = '';
			e.preventDefault();
			try { e.stopImmediatePropagation(); } catch (err) {}
		}
	}, true);

	// Wrap FileUploader (retry until available)
	var _upN = 0;
	var _upTimer = setInterval(function () {
		_paceWrapFileUploader();
		if (++_upN > 80 || (window.frappe && frappe.ui && frappe.ui.FileUploader && frappe.ui.FileUploader._paceWrapped)) {
			clearInterval(_upTimer);
		}
	}, 120);

	paceSetupAttachHighlight();
}

/** Rewrite descriptions to show the correct 1MB limits in the UI */
function paceSetupAttachHighlight() {
	var n = 0;
	var t = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		if (wf && wf.fields_dict) {
			for (var f in wf.fields_dict) {
				var fd = wf.fields_dict[f];
				if (fd && (fd.df.fieldtype === 'Attach' || fd.df.fieldtype === 'Attach Image')) {
					var isPhoto = f === 'upload_student_photo';
					var txt = isPhoto 
						? 'Max Limit 1 MB( Only jpeg, jpg, png allowed )'
						: 'Max Limit 1 MB( Only jpeg, jpg, png, pdf allowed )';
					
					// Update DocField description
					fd.df.description = txt;
					
					// Update UI if already rendered
					if (fd.$wrapper) {
						var $desc = fd.$wrapper.find('.help-box');
						if ($desc.length) {
							$desc.text(txt).show().css('color', '#64748b');
						} else {
							// For modern Frappe web form fields, description might be in .input-max-width or just after
							$('<div class="help-box small text-muted">' + txt + '</div>').appendTo(fd.$wrapper);
						}
					}
				}
			}
			// Only clear once a reasonable number of fields are loaded
			if (Object.keys(wf.fields_dict).length > 10) clearInterval(t);
		}
		if (++n > 100) clearInterval(t);
	}, 500);
}

// ───────────────────────────────────────────────────────────────────
//  FORCE PUBLIC UPLOADS — auto-uncheck Private in Frappe upload dialog
//  Two-layer: MutationObserver (instant) + polling (catches Vue async renders)
// ───────────────────────────────────────────────────────────────────
function _paceForcePublicInNode(root) {
	if (!root || !root.querySelectorAll) return;
	// 1. Click "Set all public" button (batch queue handler)
	root.querySelectorAll('button, .btn').forEach(function (btn) {
		if (!btn._pacePublicClicked && /set all public/i.test((btn.textContent || '').trim())) {
			btn._pacePublicClicked = true;
			setTimeout(function () { btn.click(); }, 30);
		}
	});
	// 2. Uncheck Private checkbox (triggers Vue reactivity via click)
	root.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
		if (cb._pacePublicDone) return;
		var lbl = cb.closest('label') || cb.parentElement || {};
		var txt = (lbl.textContent || cb.name || cb.id || '').toLowerCase();
		if (txt.indexOf('private') !== -1 && cb.checked) {
			cb._pacePublicDone = true;
			setTimeout(function () { if (cb.checked) cb.click(); }, 40);
		}
	});
}

function paceSetupForcePublicUploads() {
	// MutationObserver: fires as Frappe injects the upload modal
	var observer = new MutationObserver(function (mutations) {
		mutations.forEach(function (m) {
			m.addedNodes.forEach(function (node) {
				if (!node || node.nodeType !== 1) return;
				if (node.classList && (node.classList.contains('file-uploader') ||
						node.classList.contains('modal-dialog') ||
						node.classList.contains('modal'))) {
					_paceForcePublicInNode(node);
				}
				if (node.querySelectorAll) {
					node.querySelectorAll('.file-uploader').forEach(_paceForcePublicInNode);
				}
			});
		});
	});
	observer.observe(document.body, { childList: true, subtree: true });

	// Polling fallback: catches Vue async child renders
	setInterval(function () {
		var uploaders = document.querySelectorAll(
			'.modal.show .file-uploader, ' +
			'.modal[style*="display: block"] .file-uploader, ' +
			'.file-uploader'
		);
		uploaders.forEach(_paceForcePublicInNode);
		var modals = document.querySelectorAll('.modal.show, .modal[style*="display: block"]');
		modals.forEach(_paceForcePublicInNode);
	}, 300);
}

// ───────────────────────────────────────────────────────────────────
//  DATE OF BIRTH — age ≥ 17, max date capped, no future dates
// ───────────────────────────────────────────────────────────────────
function _paceMaxDob() {
	var d = new Date();
	d.setHours(0, 0, 0, 0);
	d.setFullYear(d.getFullYear() - 17);
	return d;
}

function _paceAgeYears(dobVal) {
	if (!dobVal) return null;
	var s = String(dobVal).trim();
	var parts = s.split('-');
	if (parts.length < 3) return null;
	var y = parseInt(parts[0], 10), mo = parseInt(parts[1], 10) - 1, day = parseInt(parts[2], 10);
	if (isNaN(y) || isNaN(mo) || isNaN(day)) return null;
	var birth = new Date(y, mo, day);
	if (isNaN(birth.getTime())) return null;
	var today = new Date(); today.setHours(0, 0, 0, 0); birth.setHours(0, 0, 0, 0);
	if (birth > today) return -1;
	var age = today.getFullYear() - birth.getFullYear();
	var md = today.getMonth() - birth.getMonth();
	if (md < 0 || (md === 0 && today.getDate() < birth.getDate())) age--;
	return age;
}

function _pacePatDob(wf) {
	if (!wf || !wf.fields_dict) return;
	var fd = wf.fields_dict.date_of_birth;
	if (!fd || fd.df.fieldtype !== 'Date') return;

	// Cap datepicker max date
	var maxD = _paceMaxDob();
	if (fd.datepicker && typeof fd.datepicker.update === 'function') {
		try { fd.datepicker.update({ maxDate: maxD }); } catch (e) {}
	}

	// Bind change listener
	if (!fd._paceDobBound && fd.$input && fd.$input.length) {
		fd._paceDobBound = true;
		fd.$input.on('change.pacedob', function () {
			var v = wf.get_value && wf.get_value('date_of_birth');
			var age = _paceAgeYears(v);
			if (v && (age === null || age < 17)) {
				frappe.msgprint({
					title: __('Invalid Date of Birth'),
					message: __('Applicant must be at least 17 years old. The date cannot be in the future.'),
					indicator: 'red',
				});
				try { wf.set_value('date_of_birth', ''); } catch (e2) {}
			}
		});
	}
}

function paceSetupDob() {
	// Block non-date characters in date inputs
	function isDateInput(el) {
		return el && el.tagName === 'INPUT' && el.closest &&
			el.closest('.frappe-control[data-fieldtype="Date"], [data-fieldtype="Date"]');
	}
	function stripBad(input) {
		var v = input.value || '';
		var cleaned = v.replace(/[^\d\-/.]/g, '');
		if (cleaned !== v) input.value = cleaned;
	}
	document.body.addEventListener('keydown', function (e) {
		if (!isDateInput(e.target)) return;
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		var key = e.key || '';
		if (key === 'Tab' || key === 'Enter' || e.keyCode === 8 || e.keyCode === 9 || e.keyCode === 27 || e.keyCode === 46) return;
		if (e.keyCode >= 35 && e.keyCode <= 40) return;
		if (key.length === 1 && /[\d\-/.]/.test(key)) return;
		if (key.length === 1) e.preventDefault();
	}, true);
	document.body.addEventListener('input', function (e) {
		if (isDateInput(e.target)) stripBad(e.target);
	}, true);
	document.body.addEventListener('paste', function (e) {
		if (!isDateInput(e.target)) return;
		setTimeout(function () { stripBad(e.target); }, 0);
	}, true);

	// Poll until web_form and DOB field are ready
	var n = 0;
	var t = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		_pacePatDob(wf);
		var fd = wf && wf.fields_dict && wf.fields_dict.date_of_birth;
		if (fd && fd._paceDobBound && fd.datepicker) {
			clearInterval(t);
		} else if (++n > 150) {
			clearInterval(t);
		}
	}, 100);
}

// ───────────────────────────────────────────────────────────────────
//  PHONE VALIDATION — country-based digit length
// ───────────────────────────────────────────────────────────────────
function paceSetupPhoneValidation() {
	// National number digit lengths per country code
	var ISD_LENGTHS = {
		'+91': [10], 91: [10],              // India
		'+1': [10], 1: [10],                // USA / Canada
		'+44': [10], 44: [10],              // UK
		'+971': [9], 971: [9],              // UAE
		'+65': [8], 65: [8],                // Singapore
		'+61': [9, 10], 61: [9, 10],        // Australia
		'+966': [9], 966: [9],              // Saudi Arabia
		'+81': [10, 11], 81: [10, 11],      // Japan
		'+49': [10, 11], 49: [10, 11],      // Germany
		'+33': [9], 33: [9],                // France
		'+39': [9, 10], 39: [9, 10],        // Italy
		'+34': [9], 34: [9],                // Spain
		'+86': [11], 86: [11],              // China
		'+82': [9, 10], 82: [9, 10],        // South Korea
		'+7': [10], 7: [10],                // Russia
		'+55': [10, 11], 55: [10, 11],      // Brazil
		'+27': [9], 27: [9],                // South Africa
		'+234': [10], 234: [10],            // Nigeria
		'+20': [10], 20: [10],              // Egypt
		'+92': [10], 92: [10],              // Pakistan
		'+880': [10], 880: [10],            // Bangladesh
		'+62': [10, 11, 12], 62: [10, 11, 12], // Indonesia
		'+63': [10], 63: [10],              // Philippines
		'+60': [9, 10], 60: [9, 10],        // Malaysia
		'+66': [9], 66: [9],                // Thailand
		'+84': [9, 10], 84: [9, 10],        // Vietnam
		'+64': [9, 10], 64: [9, 10],        // New Zealand
		'+94': [9], 94: [9],                // Sri Lanka
		'+977': [10], 977: [10],            // Nepal
	};

	function _phoneCtrl(input) {
		if (!input || !input.closest) return null;
		return input.closest('.frappe-control[data-fieldtype="Phone"]') ||
			input.closest('[data-fieldtype="Phone"]');
	}

	function _normalizeIsd(raw) {
		if (!raw) return '';
		var s = String(raw).trim().replace(/[^\d+]/g, '');
		if (!s) return '';
		return s.startsWith('+') ? s : ('+' + s);
	}

	function _isdInfo(ctrl) {
		if (!ctrl) return null;
		var isdNorm = '';
		var isdEl = ctrl.querySelector('.country') || ctrl.querySelector('.selected-phone .country');
		if (isdEl && isdEl.textContent.trim()) {
			isdNorm = _normalizeIsd(isdEl.textContent);
		}
		if (!isdNorm) {
			var fn = ctrl.getAttribute('data-fieldname');
			var wf = window.frappe && frappe.web_form;
			if (fn && wf && typeof wf.get_value === 'function') {
				var v = wf.get_value(fn);
				if (v && String(v).indexOf('-') >= 0) {
					var head = String(v).split('-')[0].trim();
					isdNorm = _normalizeIsd(head.replace(/[^\d+]/g, ''));
				}
			}
		}
		if (!isdNorm) return null;
		var bare = isdNorm.replace(/^\+/, '');
		var lengths = ISD_LENGTHS[isdNorm] || ISD_LENGTHS[bare];
		if (!lengths) return null;
		return { isd: isdNorm, lengths: lengths, limit: Math.max.apply(null, lengths) };
	}

	function _applyDigitCap(input) {
		var ctrl = _phoneCtrl(input);
		if (!ctrl) return;
		var info = _isdInfo(ctrl);
		var limit = info ? info.limit : 15;
		input.setAttribute('maxlength', limit);
		var digits = (input.value || '').replace(/\D/g, '');
		if (digits.length > limit) input.value = digits.slice(0, limit);
	}

	// Real-time cap
	document.body.addEventListener('input', function (e) {
		var input = e.target;
		if (!input || input.tagName !== 'INPUT' || !_phoneCtrl(input)) return;
		_applyDigitCap(input);
	}, true);

	// Block non-digits
	document.body.addEventListener('keydown', function (e) {
		var input = e.target;
		if (!input || input.tagName !== 'INPUT' || !_phoneCtrl(input)) return;
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		var k = e.keyCode;
		if (k === 8 || k === 9 || k === 13 || k === 27 || k === 46) return;
		if (k >= 35 && k <= 40) return;
		var isDigit = (k >= 48 && k <= 57) || (k >= 96 && k <= 105) || (e.key && e.key.length === 1 && /\d/.test(e.key));
		if (!isDigit) { e.preventDefault(); return; }
		var ctrl = _phoneCtrl(input);
		var info = _isdInfo(ctrl);
		var limit = info ? info.limit : 15;
		var digits = (input.value || '').replace(/\D/g, '');
		var start = typeof input.selectionStart === 'number' ? input.selectionStart : 0;
		var end = typeof input.selectionEnd === 'number' ? input.selectionEnd : 0;
		var selDigits = (input.value.substring(start, end) || '').replace(/\D/g, '').length;
		if (digits.length - selDigits + 1 > limit) e.preventDefault();
	}, true);

	// Sync on paste
	document.body.addEventListener('paste', function (e) {
		var input = e.target;
		if (!input || input.tagName !== 'INPUT' || !_phoneCtrl(input)) return;
		setTimeout(function () { _applyDigitCap(input); }, 0);
	}, true);

	// Sync when country picker selection changes
	var syncPhone = function (e) {
		var target = e.target;
		setTimeout(function () {
			var input = target.closest ? target.closest('.frappe-control[data-fieldtype="Phone"] input') : null;
			if (!input) input = target.closest ? target.closest('[data-fieldtype="Phone"] input') : null;
			if (!input) return;
			input.dispatchEvent(new Event('input', { bubbles: true }));
		}, 0);
	};
	['click', 'focusin', 'keyup', 'change'].forEach(function (ev) {
		document.body.addEventListener(ev, syncPhone, true);
	});

	// On blur: validate length
	document.body.addEventListener('focusout', function (e) {
		var input = e.target;
		if (!input || input.tagName !== 'INPUT' || !_phoneCtrl(input)) return;
		var ctrl = _phoneCtrl(input);
		var info = _isdInfo(ctrl);
		if (!info) return;
		var val = (input.value || '').replace(/\D/g, '');
		if (val && info.lengths.indexOf(val.length) === -1) {
			var expectedStr = info.lengths.join(' or ');
			paceShowToast('\u26a0 Invalid phone length for ' + info.isd + '. Must be ' + expectedStr + ' digits.', 'error');
			if (val.length > info.limit) input.value = val.slice(0, info.limit);
		}
	}, true);
}

// ───────────────────────────────────────────────────────────────────
//  NUMERIC FIELD RESTRICTIONS
// ───────────────────────────────────────────────────────────────────
function paceSetupNumericRestrictions() {
	var NUMERIC_TYPES = ['Int', 'Float', 'Currency', 'Percent'];

	function numCtrl(el) {
		if (!el || !el.closest) return null;
		return el.closest('.frappe-control[data-fieldtype], [data-fieldtype]');
	}

	document.body.addEventListener('keydown', function (e) {
		var input = e.target;
		if (!input || input.tagName !== 'INPUT') return;
		var ctrl = numCtrl(input);
		var ft = ctrl ? ctrl.getAttribute('data-fieldtype') : null;
		if (!ft || NUMERIC_TYPES.indexOf(ft) === -1) return;
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		var code = e.keyCode;
		if (code === 8 || code === 9 || code === 13 || code === 27 || code === 46) return;
		if (code >= 35 && code <= 40) return;
		var key = e.key || '';
		if (key.length === 1) {
			if (/\d/.test(key)) return;
			if ((ft === 'Float' || ft === 'Currency' || ft === 'Percent') && key === '.' && input.value.indexOf('.') === -1) return;
			e.preventDefault();
		}
	}, true);

	document.body.addEventListener('input', function (e) {
		var input = e.target;
		if (!input || input.tagName !== 'INPUT') return;
		var ctrl = numCtrl(input);
		var ft = ctrl ? ctrl.getAttribute('data-fieldtype') : null;
		if (!ft || NUMERIC_TYPES.indexOf(ft) === -1) return;
		var regex = (ft === 'Int') ? /[^0-9]/g : /[^0-9.]/g;
		var val = input.value;
		if (regex.test(val)) input.value = val.replace(regex, '');
	}, true);
}

// ───────────────────────────────────────────────────────────────────
function paceSetupFieldErrorClear() {
	$(document).on('input change', '.web-form input, .web-form textarea, .web-form select', function () {
		var $t = $(this);
		$t.removeClass('pace-field-error');
		$t.closest('.frappe-control').find('.pace-field-error').removeClass('pace-field-error');
	});
}

// ───────────────────────────────────────────────────────────────────
//  ADDRESS SYNC — Correspondence to Permanent
// ───────────────────────────────────────────────────────────────────
function paceSetupAddressSync() {
	var n = 0;
	var t = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		if (wf && wf.fields_dict && wf.fields_dict.is_permanent_address_same) {
			clearInterval(t);
			
			var sync = function() {
				if (!wf.get_value('is_permanent_address_same')) return;
				
				var mapping = {
					'address_line_1': 'p_address_line_1',
					'address_line_2': 'p_address_line_2',
					'city': 'p_city',
					'district': 'p_district',
					'state': 'p_state',
					'country': 'p_country',
					'pincode': 'p_pincode'
				};
				
				for (var src in mapping) {
					var val = wf.get_value(src);
					if (val !== undefined && val !== null) {
						wf.set_value(mapping[src], val);
					}
				}
			};

			// Bind to checkbox and all source fields
			wf.on('is_permanent_address_same', sync);
			['address_line_1', 'address_line_2', 'city', 'district', 'state', 'country', 'pincode'].forEach(function(f) {
				wf.on(f, sync);
			});
		}
		if (++n > 100) clearInterval(t);
	}, 200);
}

// ───────────────────────────────────────────────────────────────────
//  PINCODE VALIDATION — 6 digits only
// ───────────────────────────────────────────────────────────────────
function paceSetupPincodeValidation() {
	var validatePincode = function(fieldname) {
		var wf = window.frappe && frappe.web_form;
		if (!wf) return;
		var val = String(wf.get_value(fieldname) || '').trim();
		if (!val) return;

		var digits = val.replace(/\D/g, '');
		if (digits.length !== 6 || val.length !== 6) {
			paceShowToast('\u26a0 Pincode must be exactly 6 numeric digits.', 'error');
			// Optionally clear or trim
			if (digits.length > 6) wf.set_value(fieldname, digits.slice(0, 6));
		}
	};

	var n = 0;
	var t = setInterval(function () {
		var wf = window.frappe && frappe.web_form;
		if (wf && wf.fields_dict && wf.fields_dict.pincode) {
			clearInterval(t);
			wf.on('pincode', function() { validatePincode('pincode'); });
			if (wf.fields_dict.p_pincode) {
				wf.on('p_pincode', function() { validatePincode('p_pincode'); });
			}
		}
		if (++n > 100) clearInterval(t);
	}, 200);
}

// ───────────────────────────────────────────────────────────────────
//  BOOTSTRAP — frappe.ready
// ───────────────────────────────────────────────────────────────────
frappe.ready(function () {
	_paceInjectCSS();
	paceSetupFieldErrorClear();

	// Portal shell nav / footer (themed from Applicant Portal Config)
	_paceInjectPortalShell();

	// Trigger autofill immediately (also hooks web_form.on('load') independently of shell call)
	_paceTriggerPrefill();

	// Dynamic Applicant Name sync
	_paceSetupNameSync();

	// Address Sync
	paceSetupAddressSync();

	// Pincode Validation
	paceSetupPincodeValidation();

	// Top Bar (Back + Applying for)
	paceSetupTopBar();

	// Application status badge in page title
	paceSetupStatusBadge();

	// Save Draft button (injected beside Next/Submit)
	paceSetupSaveDraftButton();

	// Hide editable controls when form is submitted/locked
	paceSetupSubmittedFormUX();

	// Stepper with mandatory validation
	paceSetupStepper();

	// Student Photo Preview
	paceSetupPhotoPreview();

	// Attach field validation
	paceSetupAttachValidation();
	paceSetupForcePublicUploads();

	// Date of Birth validation
	paceSetupDob();

	// Phone validation
	paceSetupPhoneValidation();

	// Numeric restrictions
	paceSetupNumericRestrictions();

	// Auto-sync status badge every 2s (picks up changes from web_form events)
	setInterval(function () {
		var s = _paceResolveField('status');
		if (s) _paceUpdateStatusBadge(s);
	}, 2000);
});