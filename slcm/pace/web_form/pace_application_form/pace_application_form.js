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

	if (!document.getElementById('pace-material-icons')) {
		var iconLink = document.createElement('link');
		iconLink.id = 'pace-material-icons';
		iconLink.rel = 'stylesheet';
		iconLink.href =
			'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=block';
		document.head.appendChild(iconLink);
	}

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
		/* PACE Admission “Open” badge (same idea as admission_base.html) */
		'@keyframes pace-partylight-bg{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}',
		'@keyframes pace-partylight-pulse-text{0%{transform:scale(1);filter:brightness(1)}100%{transform:scale(1.08);filter:brightness(1.2)}}',
		'.pace-badge-partylight-text{display:inline-block;font-weight:900;text-transform:uppercase;' +
			'background:linear-gradient(-45deg,#ff0055,#ffcc00,#00ff66,#0099ff,#cc00ff,#ff0055);background-size:400% 400%;' +
			'-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;' +
			'animation:pace-partylight-bg 2s linear infinite,pace-partylight-pulse-text .8s ease-in-out infinite alternate;' +
			'vertical-align:middle;line-height:1;}',
		/* ── Admission shell nav/footer (parity with applicant_form.js / admission_base.html) ── */
		'.adm-nav{background:var(--pace-primary,#1a3c6e);padding:10px 24px;display:flex;align-items:center;' +
			'justify-content:space-between;height:60px;position:sticky;top:0;z-index:1020;' +
			'box-shadow:0 2px 8px rgba(0,0,0,.15);}',
		'.adm-nav-brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:#fff;' +
			'font-weight:700;font-size:clamp(14px,4vw,18px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:65%;}',
		'.adm-nav-brand img{height:clamp(28px,6vw,36px);width:auto;flex-shrink:0;}',
		'.adm-nav-links{display:flex;gap:clamp(10px,2vw,20px);align-items:center;}',
		'.adm-nav-links a{color:rgba(255,255,255,.85);text-decoration:none;font-size:14px;font-weight:500;}',
		'.adm-nav-links a:hover{color:#fff;}',
		'#adm-avatar-btn{user-select:none;-webkit-user-select:none;transition:all .2s;overflow:hidden;padding:0;flex-shrink:0;}',
		'#adm-avatar-btn:hover{border-color:rgba(255,255,255,.7)!important;box-shadow:0 0 0 3px rgba(255,255,255,.2)!important;}',
		'#adm-avatar-menu a:hover{background:#f8fafc!important;}',
		/* Mobile slide-down menu (opened via .pace-nav-drawer-open) */
		'#pace-mobile-nav-overlay{position:fixed;inset:0;z-index:2000010;background:rgba(15,23,42,.45);' +
			'opacity:0;visibility:hidden;transition:opacity .22s ease,visibility .22s;pointer-events:none;}' +
		'#pace-mobile-nav-overlay.is-open{opacity:1;visibility:visible;pointer-events:auto;}' +
		'.pace-mobile-nav-panel{position:absolute;left:0;right:0;top:0;background:#fff;' +
			'border-radius:0 0 18px 18px;box-shadow:0 18px 50px rgba(0,0,0,.2);max-height:min(92vh,760px);' +
			'overflow-y:auto;transform:translateY(-10px);opacity:0;transition:transform .24s ease,opacity .24s ease;}' +
		'#pace-mobile-nav-overlay.is-open .pace-mobile-nav-panel{transform:translateY(0);opacity:1;}' +
		'.pace-mobile-nav-panel__head{display:flex;align-items:center;justify-content:space-between;' +
			'gap:12px;padding:12px 16px;background:var(--pace-primary,#1a3c6e);color:#fff;min-height:52px;box-sizing:border-box;}' +
		'.pace-mobile-nav-panel__title{font-size:16px;font-weight:800;letter-spacing:.02em;flex:1;min-width:0;' +
			'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' +
		'.pace-mobile-nav-panel__close{width:40px;height:40px;border-radius:10px;border:none;cursor:pointer;' +
			'flex-shrink:0;display:flex;align-items:center;justify-content:center;' +
			'background:color-mix(in srgb,var(--pace-primary,#1a3c6e) 72%,#fff);color:#fff;font-size:26px;' +
			'font-weight:300;line-height:1;padding:0;}' +
		'.pace-mobile-nav-panel__profile{display:flex;align-items:flex-start;gap:14px;padding:18px 18px 14px;' +
			'border-bottom:1px solid #e5e7eb;}' +
		'.pace-mobile-nav-panel__avatar{width:48px;height:48px;border-radius:50%;overflow:hidden;flex-shrink:0;' +
			'display:flex;align-items:center;justify-content:center;background:#f1f5f9;font-weight:800;font-size:18px;' +
			'color:var(--pace-primary,#1a3c6e);}' +
		'.pace-mobile-nav-panel__avatar img{width:100%;height:100%;object-fit:cover;}' +
		'.pace-mobile-nav-panel__user{flex:1;min-width:0;padding-right:4px;}' +
		'.pace-mobile-nav-panel__name{font-size:15px;font-weight:800;color:#0f172a;line-height:1.25;word-break:break-word;}' +
		'.pace-mobile-nav-panel__email{font-size:12px;color:#64748b;margin-top:4px;word-break:break-word;}' +
		'.pace-mobile-nav-panel__bell{margin-left:auto;background:none;border:none;color:#334155;cursor:pointer;' +
			'padding:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}' +
		'.pace-mobile-nav-panel__profile--guest{justify-content:center;padding:16px 18px;}' +
		'.pace-drawer-nav-link{display:flex;align-items:center;gap:14px;padding:14px 18px;text-decoration:none;' +
			'color:#0f172a;font-size:15px;font-weight:700;border:none;background:#fff;width:100%;box-sizing:border-box;' +
			'text-align:left;cursor:pointer;font-family:inherit;}' +
		'.pace-drawer-nav-link:hover,.pace-drawer-nav-link:focus{background:#f8fafc;outline:none;}' +
		'.pace-drawer-nav-link__icon{font-family:Material Symbols Outlined;font-size:22px;width:28px;text-align:center;' +
			"font-variation-settings:'FILL' 0,'wght' 500,'GRAD' 0,'opsz' 24;color:var(--pace-primary,#1a3c6e);}" +
		'.pace-drawer-nav-link .pace-badge-partylight-text{margin-left:auto;font-size:9px;}' +
		'.pace-drawer-nav-link--logout{color:#dc2626!important;}' +
		'.pace-drawer-nav-link--logout .pace-drawer-nav-link__icon{color:#dc2626!important;}' +
		'.pace-mobile-nav-panel__hr{height:1px;background:#e5e7eb;margin:6px 0;}' +
		'.pace-nav-drawer-open{display:none;align-items:center;justify-content:center;width:44px;height:44px;' +
			'margin-left:auto;flex-shrink:0;border:none;border-radius:10px;background:rgba(255,255,255,.2);' +
			'color:#fff;cursor:pointer;padding:0;}' +
		'.pace-nav-drawer-open svg{display:block;}' +
		'@media (min-width:992px) { #pace-mobile-nav-overlay{display:none!important;} .pace-nav-drawer-open{display:none!important;} }' +
		/* ≤992px: top bar = brand + menu; links live in drawer */
		'@media (max-width:991.98px){' +
			'.pace-nav-drawer-open{display:flex!important;}' +
			'.adm-nav-links--desktop{display:none!important;}' +
			'.adm-nav{flex-wrap:nowrap;height:56px;min-height:52px;padding:8px 12px;gap:10px;overflow:hidden;' +
			'box-sizing:border-box;align-items:center;justify-content:flex-start;}' +
			'.adm-nav-brand{flex:1 1 auto;min-width:0;max-width:none;margin-right:0;font-size:clamp(13px,3.6vw,17px);}' +
			'.adm-nav-brand img{height:28px;}' +
			'.adm-nav-login{font-size:12px!important;padding:6px 12px!important;white-space:nowrap;}' +
			'#pace-form-topbar{flex-direction:column;align-items:stretch!important;gap:10px;padding:10px 8px;}' +
			'#pace-form-topbar-left,#pace-form-topbar-right{width:100%;flex-wrap:wrap;justify-content:space-between;}' +
			'.web-form-container,.page-content,.main-section .container,.main-section{max-width:100%!important;' +
			'box-sizing:border-box;padding-left:max(10px,env(safe-area-inset-left))!important;' +
			'padding-right:max(10px,env(safe-area-inset-right))!important;}' +
			'.web-form,.web-form .form-page,.web-form .web-form-body,.web-form .form-layout{max-width:100%;overflow-x:hidden;}' +
			'.web-form .form-column,.web-form .form-grid .form-column{min-width:0!important;}' +
		'}',
		'.adm-wf-footer{background:#0f172a;color:#94a3b8;padding:40px 24px 20px;margin-top:48px;font-family:inherit;}',
		'.adm-wf-footer-inner{max-width:1400px;margin:0 auto;display:flex;flex-wrap:wrap;gap:32px;' +
			'justify-content:space-between;}',
		'.adm-wf-footer-brand{flex:1 1 240px;}',
		'.adm-wf-footer-brand h2{font-size:18px;font-weight:700;color:#fff;margin:0 0 10px;}',
		'.adm-wf-footer-brand p{font-size:13px;line-height:1.6;margin:0;}',
		'.adm-wf-footer-links{flex:1 1 200px;}',
		'.adm-wf-footer-links h4{color:#fff;font-size:11px;font-weight:700;letter-spacing:.1em;margin:0 0 12px;}',
		'.adm-wf-footer-links ul{list-style:none;padding:0;margin:0;}',
		'.adm-wf-footer-links li{margin-bottom:7px;}',
		'.adm-wf-footer-links a{color:#94a3b8;text-decoration:none;font-size:13px;transition:color .2s;}',
		'.adm-wf-footer-links a:hover{color:#fff;}',
		'.adm-wf-footer-bottom{border-top:1px solid rgba(255,255,255,.1);margin-top:28px;padding-top:16px;' +
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
		/* Hide Frappe Web Form “Not Saved” / dirty-state pill (always) */
		'.web-form-container .indicator-pill.orange,.web-form .indicator-pill.orange,' +
			'.web-form-head .indicator-pill.orange,.page-content .web-form .indicator-pill.orange{display:none!important;}',
		/* Attach / read-only: show field labels (Frappe often omits them when control is read-only) — parity with applicant_form.js */
		'.web-form .control-label,.web-form .frappe-control > label.control-label,' +
			'.frappe-control .control-label{font-weight:600;color:#0f172a;font-size:13px;margin-bottom:6px;display:block;}',
		/* ── Top bar ── */
		'#pace-form-topbar{display:flex;align-items:center;justify-content:space-between;padding:12px 4px;margin-bottom:8px;max-width:1400px;margin-left:auto;margin-right:auto;}',
		'#pace-form-topbar-left{display:flex;align-items:center;gap:20px;}',
		'#pace-form-topbar-right{display:flex;align-items:center;gap:12px;}',
		'#pace-receipt-btn{display:inline-flex;align-items:center;gap:8px;padding:8px 18px;border-radius:8px;' +
			'font-size:13.5px;font-weight:700;border:none;background:var(--pace-primary,#1a3c6e);color:#fff!important;' +
			'cursor:pointer;transition:all .2s;box-shadow:0 2px 5px rgba(0,0,0,0.1);}',
		'#pace-receipt-btn:hover{background:#132d54;transform:translateY(-1px);box-shadow:0 4px 8px rgba(0,0,0,0.15);}',
		'#pace-back-btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;' +
			'font-size:13px;font-weight:600;border:1.5px solid #e2e8f0;background:#fff;color:#475569;' +
			'cursor:pointer;text-decoration:none!important;transition:all .2s;}',
		'#pace-back-btn:hover{background:#f8fafc;border-color:#cbd5e1;color:#1e293b;}',
		'#pace-applying-for-wrap{font-size:13px;color:#64748b;}',
		'#pace-applying-for-wrap strong{color:#1e293b;margin-left:4px;}',
		/* ── Stepper ── */
		'#pace-stepper-wrap{padding:15px 16px 28px;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none;width:100%;box-sizing:border-box;}',
		'#pace-stepper-wrap::-webkit-scrollbar{display:none;}',
		/* Stepper: flex + centered so ultrawide screens do not stretch 1fr gaps between stages */
		'.pace-stepper.pace-stepper-flex{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;' +
			'box-sizing:border-box;width:100%;max-width:100%;min-width:0;padding:0 6px;gap:0;row-gap:10px;}',
		'.pace-stepper.pace-stepper-flex .pace-step{flex:0 0 auto;}',
		'.pace-step{display:flex;flex-direction:row;align-items:center;gap:14px;cursor:pointer;position:relative;' +
			'min-width:104px;max-width:min(220px,32vw);width:max-content;transition:background .25s,border-color .25s;' +
			'padding:10px 10px 10px;border-radius:14px;border:1px solid transparent;background:#f3f4f6;}',
		'.pace-step-connector{flex:0 0 auto;align-self:center;width:clamp(10px,2.2vw,52px);min-width:10px;max-width:52px;' +
			'height:2px;background:#e5e7eb;border-radius:1px;pointer-events:none;}',
		/* Narrow viewports: one row + horizontal scroll (avoid flex-wrap zig-zag on phones) */
		'@media (max-width:991.98px){' +
			'#pace-stepper-wrap,.web-form-container:has(#pace-stepper-wrap) #pace-stepper-wrap{' +
			'padding:12px 10px 18px!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch;' +
			'scroll-snap-type:x proximity;touch-action:pan-x;}' +
			'.pace-stepper.pace-stepper-flex{flex-wrap:nowrap;justify-content:flex-start;width:max-content;max-width:none;' +
			'padding:0 4px;row-gap:0;}' +
			'.pace-stepper.pace-stepper-flex .pace-step{scroll-snap-align:start;min-width:0;max-width:min(168px,46vw);' +
			'padding:8px 8px;gap:8px;}' +
			'.pace-step-connector{width:12px;min-width:8px;max-width:16px;}' +
			'.pace-step-circle{width:20px;height:20px;font-size:12px;}' +
			'.pace-step-label{font-size:9px;max-width:10em;line-height:1.2;}' +
		'}',
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
		'.pace-field-error{border-color:#ef4444!important;box-shadow:0 0 0 3px rgba(239,68,68,0.15)!important;}',
		'.pace-loading-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(255,255,255,0.85);' +
			'display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:999999;transition:opacity .3s;}',
		'.pace-spinner{width:48px;height:48px;border:4.5px solid #e2e8f0;border-top:4.5px solid var(--pace-primary,#1a3c6e);' +
			'border-radius:50%;animation:pace-spin .8s linear infinite;margin-bottom:16px;}',
		'.pace-loading-text{font-size:15px;font-weight:600;color:var(--pace-primary,#1a3c6e);letter-spacing:.01em;}',
		/* Custom Modal */
		'.pace-modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(15,23,42,0.6);' +
			'backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:1000000;}',
		'.pace-modal{background:#fff;border-radius:18px;width:min(440px,90vw);padding:32px;box-shadow:0 20px 25px -5px rgba(0,0,0,0.1);' +
			'animation:pace-modal-in .3s cubic-bezier(0.34, 1.56, 0.64, 1);}',
		'@keyframes pace-modal-in{from{transform:scale(0.92);opacity:0;}to{transform:scale(1);opacity:1;}}',
		'.pace-modal-icon{width:54px;height:54px;background:#f0f7ff;border-radius:50%;display:flex;align-items:center;' +
			'justify-content:center;margin:0 auto 18px;color:var(--pace-primary,#1a3c6e);}',
		'.pace-modal-title{font-size:1.25rem;font-weight:800;color:#1e293b;text-align:center;margin-bottom:8px;letter-spacing:-.01em;}',
		'.pace-modal-text{font-size:14px;color:#64748b;text-align:center;line-height:1.6;margin-bottom:24px;}',
		'.pace-fee-card{background:#f8fafc;border:1.5px solid #eef2f6;border-radius:14px;padding:20px 16px;margin-bottom:28px;text-align:center;}',
		'.pace-fee-label{font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;}',
		'.pace-fee-amount{font-size:32px;font-weight:850;color:var(--pace-primary,#1a3c6e);letter-spacing:-.02em;}',
		'.pace-modal-actions{display:flex;flex-direction:column;gap:10px;}',
		'.pace-btn-pay{background:var(--pace-primary,#1a3c6e);color:#fff;border:none;padding:13px;border-radius:10px;' +
			'font-weight:700;font-size:15px;cursor:pointer;transition:transform .1s,filter .2s;display:flex;align-items:center;justify-content:center;gap:8px;}',
		'.pace-btn-pay:active{transform:scale(.98);}',
		'.pace-btn-cancel{background:transparent;color:#94a3b8;border:none;padding:8px;font-weight:600;cursor:pointer;font-size:13px;transition:color .2s;}',
		'.pace-btn-cancel:hover{color:#64748b;}',
		/* Overflow fix */
		'.web-form .form-grid-container,.web-form .form-grid{overflow:visible!important;}',
		/* Small Text / Text / Long Text — auto height (Web Form custom_css forces .form-control 42px) */
		'.web-form textarea.form-control,.web-form .frappe-control textarea.form-control{' +
			'height:auto!important;min-height:104px!important;line-height:1.5!important;padding:10px 12px!important;' +
			'resize:vertical!important;overflow-y:auto!important;}',
		'.web-form .frappe-control[data-fieldtype="Small Text"] textarea.form-control,' +
			'.web-form .frappe-control[data-fieldtype="Text"] textarea.form-control,' +
			'.web-form .frappe-control[data-fieldtype="Long Text"] textarea.form-control{' +
			'min-height:120px!important;}',
		'.web-form .frappe-control[data-fieldtype="Small Text"] textarea.form-control:disabled,' +
			'.web-form .frappe-control[data-fieldtype="Small Text"] textarea.form-control[disabled],' +
			'.web-form .frappe-control[data-fieldtype="Text"] textarea.form-control:disabled,' +
			'.web-form .frappe-control[data-fieldtype="Long Text"] textarea.form-control:disabled{' +
			'min-height:120px!important;height:auto!important;}',
		'.web-form .frappe-control[data-fieldtype="Small Text"] .control-value,' +
			'.web-form .frappe-control[data-fieldtype="Text"] .control-value,' +
			'.web-form .frappe-control[data-fieldtype="Long Text"] .control-value{' +
			'height:auto!important;min-height:72px!important;white-space:pre-wrap!important;' +
			'overflow:visible!important;line-height:1.5!important;padding:10px 12px!important;}',
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
	var s = (_paceResolveField('status') || '').trim().toLowerCase();
	if (!s) return false;
	// Allow only Draft and Returned for Correction to be editable
	return s !== 'draft' && s !== 'returned for correction';
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
	if (document.getElementById('slcm-adm-nav')) return;
	frappe.call({
		method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_pace_portal_shell_data',
		callback: function (r) {
			var d = (r && r.message) || {};
			_paceBuildAdmissionShell(
				{ banner_image: d.banner_image, title: d.site_title },
				{
					portal_title: d.portal_title,
					primary_color: d.primary_color,
					secondary_color: d.secondary_color,
					footer_address: d.footer_address,
					footer_phone: d.footer_phone,
					contact_email: d.contact_email,
					programmes: d.programmes || [],
					pace_enabled: d.pace_enabled || 0,
					powerd_by: d.powerd_by || 'boscosoft',
				},
				d.user || 'Guest',
				{ full_name: d.full_name, user_image: d.user_image, email: d.email || '' }
			);
			_paceUserData = d;
			_paceTriggerPrefill();
		},
		error: function () {
			_paceBuildAdmissionShell(
				{ banner_image: '', title: 'SLCM' },
				{
					portal_title: 'Admissions',
					primary_color: '#1a3c6e',
					secondary_color: '#c8a14b',
					footer_address: '',
					footer_phone: '',
					contact_email: '',
					programmes: [],
					pace_enabled: 0,
					powerd_by: 'boscosoft',
				},
				'Guest',
				{}
			);
			_paceUserData = { user: 'Guest' };
			_paceTriggerPrefill();
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
				// if (count > 0) paceShowToast('Form auto-filled from your previous application.', 'success', 5000);
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





/**
 * Mobile slide-down menu: open/close overlay, bell + logout in drawer, Escape + backdrop close.
 */
function _paceSetupMobileNavDrawer() {
	var overlay = document.getElementById('pace-mobile-nav-overlay');
	var openBtn = document.getElementById('pace-nav-drawer-open');
	var closeBtn = document.getElementById('pace-nav-drawer-close');
	if (!overlay || !openBtn) return;

	function closeDrawer() {
		overlay.classList.remove('is-open');
		overlay.setAttribute('aria-hidden', 'true');
		openBtn.setAttribute('aria-expanded', 'false');
		document.body.style.overflow = '';
		try {
			var m = document.getElementById('adm-avatar-menu');
			if (m) m.style.display = 'none';
		} catch (e) {}
	}

	function openDrawer() {
		overlay.classList.add('is-open');
		overlay.setAttribute('aria-hidden', 'false');
		openBtn.setAttribute('aria-expanded', 'true');
		document.body.style.overflow = 'hidden';
	}

	openBtn.addEventListener('click', function (e) {
		e.stopPropagation();
		openDrawer();
	});
	if (closeBtn) {
		closeBtn.addEventListener('click', function (e) {
			e.stopPropagation();
			closeDrawer();
		});
	}
	overlay.addEventListener('click', function (e) {
		if (e.target === overlay) closeDrawer();
	});
	if (!window._paceMobileDrawerKeybound) {
		window._paceMobileDrawerKeybound = true;
		document.addEventListener('keydown', function (e) {
			var ov = document.getElementById('pace-mobile-nav-overlay');
			if (e.key === 'Escape' && ov && ov.classList.contains('is-open')) {
				var ob = document.getElementById('pace-nav-drawer-open');
				ov.classList.remove('is-open');
				ov.setAttribute('aria-hidden', 'true');
				if (ob) ob.setAttribute('aria-expanded', 'false');
				document.body.style.overflow = '';
			}
		});
	}

	var bellD = document.getElementById('slcm-bell-btn-drawer');
	if (bellD) {
		bellD.addEventListener('click', function () {
			closeDrawer();
			window.location.href = '/merit-and-scholarship/admission_dashboard';
		});
	}
	var loD = document.getElementById('slcm-nav-logout-drawer');
	if (loD) {
		loD.addEventListener('click', function (e) {
			e.preventDefault();
			closeDrawer();
			frappe.call({
				method: 'logout',
				callback: function () {
					window.location.href = '/login';
				},
			});
		});
	}

	overlay.querySelectorAll('a.pace-drawer-nav-link[href^="/"]').forEach(function (a) {
		a.addEventListener('click', function () {
			closeDrawer();
		});
	});
}

/**
 * Nav + footer matching slcm/admission/web_form/applicant_form.js _buildShell
 * and slcm/www/admission_base.html (Admission, optional PACE Admission, bell, profile, programme grid footer).
 */
function _paceBuildAdmissionShell(ws, cfg, user, uinfo) {
	if (document.getElementById('slcm-adm-nav')) return;

	var primary = cfg.primary_color || '#1a3c6e';
	var secondary = cfg.secondary_color || '#c8a14b';
	var title = cfg.portal_title || (ws && ws.title) || 'Admissions';
	var logo = (ws && ws.banner_image) || '';
	var isGuest = !user || user === 'Guest';
	var fullName = (uinfo && uinfo.full_name) || user || '';
	var userImg = (uinfo && uinfo.user_image) || '';
	var userEmail = (uinfo && uinfo.email) || '';
	var initLetter = fullName ? fullName[0].toUpperCase() : 'U';
	var programmes = cfg.programmes || [];
	var powerd = cfg.powerd_by || 'boscosoft';
	var paceOn = cfg.pace_enabled ? 1 : 0;

	var varStyle = document.createElement('style');
	varStyle.id = 'pace-theme-vars';
	varStyle.textContent =
		':root{--pace-primary:' +
		primary +
		';--pace-secondary:' +
		secondary +
		';--slcm-primary:' +
		primary +
		';--slcm-secondary:' +
		secondary +
		';}' +
		'.btn-next,.submit-btn,.btn-submit-web-form{background:' +
		primary +
		'!important;border-color:' +
		primary +
		'!important;color:#fff!important;}' +
		'.btn-next:hover,.submit-btn:hover{filter:brightness(1.08)!important;}' +
		'.section-head{color:' +
		primary +
		'!important;}' +
		'.web-form-container .section-head,.web-form .section-head{color:' +
		primary +
		'!important;}';
	document.head.appendChild(varStyle);

	var paceNavLink = paceOn
		? '<a href="/pace/admission" class="nav-hide-mobile" style="text-decoration:none;display:inline-flex;align-items:center;padding:0 12px;height:100%;">' +
			'<span style="color:#fff;font-size:14px;font-weight:500;opacity:0.95;display:flex;align-items:center;">PACE Admission' +
			'<span class="pace-badge-partylight-text" style="font-size:10px;margin-left:8px;">Open</span></span></a>'
		: '';

	var drawerPaceBlock = paceOn
		? '<a href="/pace/admission" class="pace-drawer-nav-link">' +
			'<span class="pace-drawer-nav-link__icon" aria-hidden="true">widgets</span>' +
			'<span>PACE Admission</span>' +
			'<span class="pace-badge-partylight-text" style="font-size:10px;margin-left:6px;">OPEN</span></a>'
		: '';

	var drawerProfileBlock = isGuest
		? '<div class="pace-mobile-nav-panel__profile pace-mobile-nav-panel__profile--guest">' +
			'<a href="/login" class="adm-nav-login" style="display:inline-flex;align-items:center;background:' +
			primary +
			';color:#fff;padding:10px 22px;border-radius:10px;font-weight:700;font-size:14px;text-decoration:none;">Login / Apply</a></div>'
		: '<div class="pace-mobile-nav-panel__profile">' +
			'<div class="pace-mobile-nav-panel__avatar">' +
			(userImg
				? '<img src="' + _paceEsc(userImg) + '" alt="">'
				: _paceEsc(initLetter)) +
			'</div>' +
			'<div class="pace-mobile-nav-panel__user">' +
			'<div class="pace-mobile-nav-panel__name">' +
			_paceEsc(fullName) +
			'</div>' +
			'<div class="pace-mobile-nav-panel__email">' +
			_paceEsc(userEmail || user) +
			'</div></div>' +
			'<button type="button" id="slcm-bell-btn-drawer" class="pace-mobile-nav-panel__bell" aria-label="Notifications">' +
			'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
			'<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg></button></div>';

	var drawerNavBlock =
		'<a href="/admission" class="pace-drawer-nav-link">' +
		'<span class="pace-drawer-nav-link__icon" aria-hidden="true">home</span><span>Admission</span></a>' +
		drawerPaceBlock +
		'<div class="pace-mobile-nav-panel__hr"></div>' +
		(isGuest
			? ''
			: '<a href="javascript:void(0)" id="slcm-nav-logout-drawer" class="pace-drawer-nav-link pace-drawer-nav-link--logout">' +
				'<span class="pace-drawer-nav-link__icon" aria-hidden="true">logout</span><span>Logout</span></a>');

	var drawerHtml =
		'<div class="pace-mobile-nav-panel" role="dialog" aria-modal="true" aria-labelledby="pace-drawer-nav-title">' +
		'<div class="pace-mobile-nav-panel__head">' +
		'<span id="pace-drawer-nav-title" class="pace-mobile-nav-panel__title">' +
		_paceEsc(title) +
		'</span>' +
		'<button type="button" id="pace-nav-drawer-close" class="pace-mobile-nav-panel__close" aria-label="Close menu">×</button>' +
		'</div>' +
		drawerProfileBlock +
		'<nav class="pace-mobile-nav-panel__links" aria-label="Portal">' +
		drawerNavBlock +
		'</nav></div>';

	var nav = document.createElement('nav');
	nav.id = 'slcm-adm-nav';
	nav.className = 'adm-nav';
	nav.innerHTML =
		'<a href="/admission" class="adm-nav-brand">' +
		(logo ? '<img src="' + _paceEsc(logo) + '" alt="Logo">' : '') +
		_paceEsc(title) +
		'</a>' +
		'<button type="button" id="pace-nav-drawer-open" class="pace-nav-drawer-open" aria-label="Open menu" aria-expanded="false">' +
		'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">' +
		'<path d="M4 6h16M4 12h16M4 18h16"/></svg></button>' +
		'<div class="adm-nav-links adm-nav-links--desktop">' +
		'<a href="/admission" class="nav-hide-mobile">Admission</a>' +
		paceNavLink +
		'<button type="button" id="slcm-bell-btn" class="nav-hide-mobile" style="background:none;border:none;color:#fff;cursor:pointer;padding:4px 8px;display:flex;align-items:center;" aria-label="Notifications">' +
		'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
		'<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>' +
		'</svg></button>' +
		(isGuest
			? '<a href="/login" class="adm-nav-login" style="display:inline-flex;align-items:center;background:' +
				primary +
				';color:#fff;padding:8px 20px;border-radius:8px;font-weight:700;font-size:14px;text-decoration:none;">Login / Apply</a>'
			: '<div style="position:relative;display:flex;align-items:center;gap:10px;">' +
				'<button type="button" id="adm-avatar-btn" onclick="_paceAvatarToggle(event)"' +
				' style="width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.15);color:#fff;' +
				'border:2px solid rgba(255,255,255,.3);font-weight:800;font-size:15px;cursor:pointer;' +
				'display:flex;align-items:center;justify-content:center;">' +
				(userImg
					? '<img src="' +
						_paceEsc(userImg) +
						'" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">'
					: _paceEsc(initLetter)) +
				'</button>' +
				'<span style="color:#fff;font-size:13px;font-weight:600;opacity:.95;cursor:pointer;" class="nav-hide-mobile" onclick="_paceAvatarToggle(event)">' +
				_paceEsc(fullName) +
				'</span>' +
				'<div id="adm-avatar-menu" style="display:none;position:absolute;right:0;top:calc(100% + 8px);' +
				'min-width:180px;background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,.14);' +
				'border:1px solid rgba(0,0,0,.07);overflow:hidden;z-index:9999;">' +
				'<div style="padding:12px 16px;border-bottom:1px solid #f1f5f9;">' +
				'<div style="font-size:11px;color:#94a3b8;font-weight:600;letter-spacing:.05em;">Signed in as</div>' +
				'<div style="font-size:13px;color:#1e293b;font-weight:700;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:160px;">' +
				_paceEsc(user) +
				'</div></div>' +
				'<a href="/merit-and-scholarship/admission_dashboard?panel=profile" style="display:flex;align-items:center;gap:10px;padding:12px 16px;text-decoration:none;color:#334155;font-size:14px;font-weight:600;">' +
				'<span style="font-family:Material Symbols Outlined;font-size:18px;color:' +
				primary +
				'">account_circle</span>Profile</a>' +
				'<div style="height:1px;background:#f1f5f9;margin:4px 0;"></div>' +
				'<a href="javascript:void(0)" id="slcm-nav-logout" style="display:flex;align-items:center;gap:10px;padding:12px 16px;text-decoration:none;color:#ef4444;font-size:14px;font-weight:600;">' +
				'<span style="font-family:Material Symbols Outlined;font-size:18px;color:#ef4444">logout</span>Logout</a>' +
				'</div></div>') +
		'</div>';

	document.body.insertBefore(nav, document.body.firstChild);

	var overlayEl = document.createElement('div');
	overlayEl.id = 'pace-mobile-nav-overlay';
	overlayEl.setAttribute('aria-hidden', 'true');
	overlayEl.innerHTML = drawerHtml;
	document.body.appendChild(overlayEl);
	_paceSetupMobileNavDrawer();

	window._paceAvatarToggle = function (e) {
		e.stopPropagation();
		var m = document.getElementById('adm-avatar-menu');
		if (!m) return;
		m.style.display = m.style.display === 'block' ? 'none' : 'block';
	};
	document.addEventListener('click', function (e) {
		var m = document.getElementById('adm-avatar-menu');
		var b = document.getElementById('adm-avatar-btn');
		if (m && !m.contains(e.target) && e.target !== b) m.style.display = 'none';
	});
	var logoutLink = document.getElementById('slcm-nav-logout');
	if (logoutLink) {
		logoutLink.addEventListener('click', function () {
			frappe.call({
				method: 'logout',
				callback: function () {
					window.location.href = '/login';
				},
			});
		});
	}

	var bellBtn = document.getElementById('slcm-bell-btn');
	if (bellBtn) {
		bellBtn.addEventListener('click', function () {
			window.location.href = '/merit-and-scholarship/admission_dashboard';
		});
	}

	var yr = new Date().getFullYear();
	var progRows = programmes
		.map(function (p) {
			return (
				'<li><a href="/admission/' +
				_paceEsc(p.slug || p.name || '') +
				'">' +
				_paceEsc(p.name || '') +
				'</a></li>'
			);
		})
		.join('');
	progRows += '<li><a href="/admission">Browse all</a></li>';

	var hasContact = cfg.footer_address || cfg.footer_phone || cfg.contact_email;
	var contactCol =
		'<div class="adm-wf-footer-links">' +
		'<h4 class="footer-title">CONTACT</h4>' +
		'<div style="display:flex;flex-direction:column;gap:4px;">' +
		(cfg.footer_address
			? '<div class="footer-contact-item"><span style="font-family:Material Symbols Outlined;font-size:18px;color:' +
				secondary +
				'">location_on</span><span>' +
				_paceEsc(cfg.footer_address) +
				'</span></div>'
			: '') +
		(cfg.footer_phone
			? '<div class="footer-contact-item"><span style="font-family:Material Symbols Outlined;font-size:18px;color:' +
				secondary +
				'">call</span><span>' +
				_paceEsc(cfg.footer_phone) +
				'</span></div>'
			: '') +
		(cfg.contact_email
			? '<div class="footer-contact-item"><span style="font-family:Material Symbols Outlined;font-size:18px;color:' +
				secondary +
				'">mail</span><a href="mailto:' +
				_paceEsc(cfg.contact_email) +
				'">' +
				_paceEsc(cfg.contact_email) +
				'</a></div>'
			: '') +
		(!hasContact
			? '<p style="font-size:12px;font-style:italic;color:#64748b;">Contact details not configured.<br>Set them in Admission Portal Config.</p>'
			: '') +
		'</div></div>';

	var footer = document.createElement('footer');
	footer.id = 'slcm-adm-footer';
	footer.className = 'adm-wf-footer';
	footer.innerHTML =
		'<div class="adm-wf-footer-inner">' +
		'<div class="adm-wf-footer-brand">' +
		'<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">' +
		'<div style="width:32px;height:32px;background:' +
		primary +
		';border-radius:6px;display:flex;align-items:center;justify-content:center;color:#fff;">' +
		'<span style="font-family:Material Symbols Outlined;font-size:20px;">school</span>' +
		'</div>' +
		'<h2 style="font-size:20px;font-weight:700;color:#fff;margin:0;">' +
		_paceEsc(title) +
		'</h2></div>' +
		'<p style="font-size:13px;line-height:1.5;max-width:400px;margin:0;">Admissions Portal — empowering the next generation of students.</p>' +
		'</div>' +
		'<div class="adm-wf-footer-links">' +
		'<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;">' +
		'<div>' +
		'<h4 class="footer-title" style="color:#fff;font-size:11px;font-weight:700;letter-spacing:.1em;margin:0 0 14px;">PROGRAMME</h4>' +
		'<ul style="list-style:none;padding:0;margin:0;">' +
		progRows +
		'</ul></div>' +
		'<div>' +
		'<h4 class="footer-title" style="color:#fff;font-size:11px;font-weight:700;letter-spacing:.1em;margin:0 0 14px;">ADMISSIONS</h4>' +
		'<ul style="list-style:none;padding:0;margin:0;">' +
		'<li><a href="/admission">Apply now</a></li>' +
		'<li><a href="/merit-and-scholarship/scholarships">Scholarships</a></li>' +
		'<li><a href="/offer_letter/offer-letter-list">Offer Letter</a></li>' +
		'</ul></div></div></div>' +
		contactCol +
		'</div>' +
		'<div class="adm-wf-footer-bottom">' +
		'<span>© ' +
		yr +
		' ' +
		_paceEsc(title) +
		'. All rights reserved.</span>' +
		'<span>Powered by <strong style="color:#fff;font-weight:700;">' +
		_paceEsc(powerd) +
		'</strong></span>' +
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

	var right = document.createElement('div');
	right.id = 'pace-form-topbar-right';

	left.appendChild(back);
	left.appendChild(apply);
	bar.appendChild(left);
	bar.appendChild(right);

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

// ───────────────────────────────────────────────────────────────────
//  SUBMISSION & PAYMENT
// ───────────────────────────────────────────────────────────────────

function _paceShowLoading(msg) {
    if (document.getElementById('pace-loading')) return;
    var div = document.createElement('div');
    div.id = 'pace-loading';
    div.className = 'pace-loading-overlay';
    div.innerHTML = '<div class="pace-spinner"></div><div class="pace-loading-text">' + _paceEsc(msg || 'Please wait...') + '</div>';
    document.body.appendChild(div);
}

function _paceHideLoading() {
    var el = document.getElementById('pace-loading');
    if (el) el.remove();
}

function _paceLoadRazorpay(callback) {
    if (typeof Razorpay !== 'undefined') {
        callback();
        return;
    }
    var sc = document.createElement('script');
    sc.src = 'https://checkout.razorpay.com/v1/checkout.js';
    sc.onload = callback;
    sc.onerror = function() {
        _paceHideLoading();
        paceShowToast('Payment gateway script failed to load. Please refresh.', 'error');
    };
    document.head.appendChild(sc);
}

function _paceShowSubmissionDialog() {
    var status = (_paceResolveField('status') || '').trim();
    var wf = window.frappe && frappe.web_form;
    if (!wf) return;

    // Only show payment/fee dialog for initial Draft submissions.
    // For all other statuses (Submitted, Returned for Correction, etc.), skip straight to final submit.
    if (status !== 'Draft' && status !== 'Returned for Correction') {
        _paceFinalSubmit();
        return;
    }

    function _paceShowConfirmModal(fee, currency, programme, onConfirm) {
        if (document.getElementById('pace-confirm-modal')) return;
        
        var overlay = document.createElement('div');
        overlay.id = 'pace-confirm-modal';
        overlay.className = 'pace-modal-overlay';
        
        var amtStr = format_currency(fee, currency || 'INR', 0);
        
        overlay.innerHTML = 
            '<div class="pace-modal">' +
                '<div class="pace-modal-icon">' +
                    '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v20m7-18H9.5a4.5 4.5 0 000 9h5a4.5 4.5 0 010 9H5"/></svg>' +
                '</div>' +
                '<div class="pace-modal-title">Confirm Submission</div>' +
                '<div class="pace-modal-text">You are about to submit your application for <strong>' + _paceEsc(programme) + '</strong>. Please review the fee details below.</div>' +
                '<div class="pace-fee-card">' +
                    '<div class="pace-fee-label">Application Fee</div>' +
                    '<div class="pace-fee-amount">' + amtStr + '</div>' +
                '</div>' +
                '<div class="pace-modal-actions">' +
                    '<button class="pace-btn-pay" id="pace-modal-confirm-btn">' +
                        '<span>Proceed to Payment</span>' +
                        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>' +
                    '</button>' +
                    '<button class="pace-btn-cancel" id="pace-modal-close-btn">Cancel</button>' +
                '</div>' +
            '</div>';
            
        document.body.appendChild(overlay);
        
        overlay.querySelector('#pace-modal-confirm-btn').onclick = function() {
            overlay.remove();
            onConfirm();
        };
        overlay.querySelector('#pace-modal-close-btn').onclick = function() {
            overlay.remove();
        };
    }

    var prog = wf.get_value('programme');
    _paceShowLoading(__('Calculating Fee...'));
    
    frappe.call({
        method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_pace_admission_fee',
        args: { application: {
            programme: prog,
            academic_year: wf.get_value('academic_year'),
            nationality: wf.get_value('nationality')
        } },
        callback: function(r) {
            _paceHideLoading();
            var fee = (r.message && r.message.fee) || 0;
            
            _paceShowConfirmModal(fee, 'INR', prog, function() {
                _paceShowLoading(__('Processing Application...'));
                
                paceHandleSaveDraft({ ignore_mandatory: false, silent: true }).then(function(msg) {
                    var docname = msg.name;
                    frappe.call({
                        method: 'slcm.pace.web_form.pace_application_form.pace_application_form.initiate_pace_razorpay_order',
                        args: { application_name: docname },
                        callback: function(r) {
                            var res = r.message;
                            if (res && (res.status === 'free' || res.status === 'already_paid')) {
                                _paceHideLoading();
                                paceShowToast(res.message || __('Application submitted.'), 'success');
                                setTimeout(function() { window.location.reload(); }, 1500);
                                return;
                            }
                            _paceShowLoading(__('Gateway Opening...'));
                            if (res && res.order_id) {
                                _paceLoadRazorpay(function() {
                                    _paceHideLoading();
                                    var options = {
                                        key: res.key_id,
                                        amount: res.amount,
                                        currency: res.currency || 'INR',
                                        order_id: res.order_id,
                                        name: 'PACE Application Fee',
                                        description: 'Application Registration Fee',
                                        prefill: {
                                            name: (wf.get_value('first_name') || '') + ' ' + (wf.get_value('last_name') || ''),
                                            email: wf.get_value('email_address') || '',
                                            contact: wf.get_value('mobile_number') || ''
                                        },
                                        theme: { color: '#7B1D1D' },
                                        handler: function(resp) {
                                            _paceShowLoading(__('Verifying Payment\u2026'));
                                            frappe.call({
                                                method: 'slcm.pace.web_form.pace_application_form.pace_application_form.verify_pace_payment_signature',
                                                args: {
                                                    razorpay_payment_id: resp.razorpay_payment_id,
                                                    razorpay_order_id: resp.razorpay_order_id,
                                                    razorpay_signature: resp.razorpay_signature,
                                                    assignment_name: res.assignment
                                                },
                                                callback: function(vr) {
                                                    _paceHideLoading();
                                                    if (vr.message && vr.message.status === 'success') {
                                                        paceRenderSuccessPage();
                                                    } else {
                                                        var err = (vr.message && vr.message.message) || __('Verification failed.');
                                                        paceShowToast(String(err), 'error', 8000);
                                                    }
                                                },
                                                error: function() {
                                                    _paceHideLoading();
                                                    paceShowToast(__('Verification request failed. Please reload or contact support.'), 'error', 8000);
                                                }
                                            });
                                        }
                                    };
                                    var rzp = new Razorpay(options);
                                    rzp.open();
                                });
                            }
                        }
                    });
                }).catch(function() { _paceHideLoading(); });
            });
        }
    });
}

function _paceFinalSubmit() {
    // Hidden submit for non-payment cases
    _paceShowLoading(__('Submitting Application...'));
    paceHandleSaveDraft({ ignore_mandatory: false }).then(function() {
        _paceHideLoading();
        window.location.reload();
    }).catch(function() { _paceHideLoading(); });
}

function paceSetupSubmission() {
    var wf = window.frappe && frappe.web_form;
    if (!wf) return;

    $(document).off('click.paceSubmit').on('click.paceSubmit', '.btn-submit-web-form, .submit-btn', function(e) {
        if (_pacePortalLocked()) return;
        e.preventDefault();
        e.stopImmediatePropagation();

        if (!wf.get_value('i_agree')) {
            paceShowToast(__('You must agree to the declaration.'), 'error');
            return false;
        }
        _paceShowSubmissionDialog();
    });
}

function paceSetupReadonlyLogic() {
    var wf = window.frappe && frappe.web_form;
    if (!wf) return;

    var runLogic = function() {
        paceInjectAttachFieldLabels();
        var raw_status = _paceResolveField('status') || '';
        var status = raw_status.trim().toLowerCase();
        if (!status) return;

        if (_pacePortalLocked()) {
            var path = window.location.pathname;
            if (path.indexOf('/edit') !== -1) {
                window.location.href = path.replace(/\/edit\/?$/, '');
                return;
            }
            if (wf.fields) {
                wf.fields.forEach(f => { if(f.fieldname && !f.read_only) wf.set_df_property(f.fieldname, 'read_only', 1); });
            }
            $('#pace-save-draft-btn, .submit-btn, .btn-submit-web-form, .btn-primary[type="submit"], .discard-btn, .btn-edit, .edit-button, [data-label="Edit"]').hide();
            $('.grid-footer, .grid-add-row, .grid-remove-row, .btn-remove').hide();
            $('.web-form input, .web-form select, .web-form textarea').attr('disabled', 'disabled').css('cursor', 'not-allowed');
            
        } else if (status === 'returned for correction') {
            var DOC_FIELDS = ['student_signature', 'ug_degree_certificate', 'self_declaration', 'passport_oci', 'govt_id', 'upload_student_photo'];
            
            $('.submit-btn, .btn-submit-web-form, .btn-primary[type="submit"]').hide();
            $('#pace-save-draft-btn').text('Save Changes').show();

            // 1. ALWAYS lock everything first to counter Frappe re-renders
            (wf.fields || []).forEach(f => { if(f.fieldname) wf.set_df_property(f.fieldname, 'read_only', 1); });
            $('.web-form input, .web-form select, .web-form textarea').attr('disabled', 'disabled').css('cursor', 'not-allowed');

            if (window._pace_restricted_done && window._pace_allowed_fields) {
                // 2. ALWAYS Re-apply selective unlock from cached list every interval tick
                window._pace_allowed_fields.forEach(f => {
                    wf.set_df_property(f, 'read_only', 0);
                    var $ctrl = $('[data-fieldname="' + f + '"]');
                    $ctrl.find('input, select, textarea').removeAttr('disabled').css('cursor', '');
                    $ctrl.find('.btn-attach, .btn-remove, .reload-file, .btn-file-reload').show();
                });
                return;
            }

            if (window._pace_fetching_restricted) return;
            window._pace_fetching_restricted = true;

            frappe.call({
                method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_restricted_fields',
                args: { application_name: _paceGetDocName() },
                callback: function(r) {
                    window._pace_allowed_fields = (r.message || []).filter(f => DOC_FIELDS.indexOf(f) !== -1);
                    window._pace_restricted_done = true;
                    window._pace_fetching_restricted = false;
                }
            });
        }
    };
    setTimeout(runLogic, 600);
    setInterval(runLogic, 1000); 
}

// ───────────────────────────────────────────────────────────────────
//  RECEIPT BUTTON
// ───────────────────────────────────────────────────────────────────
function paceSetupReceiptButton() {
    setInterval(function() {
        if (document.getElementById('pace-receipt-btn')) return;
        var status = _paceResolveField('status');
        if (status !== 'Submitted' && status !== 'Verified') return;

        var $actions = $('#pace-form-topbar-right');
        if ($actions.length) {
            var btn = $('<button id="pace-receipt-btn"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:2px;"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> Download Receipt</button>');
            btn.on('click', function() {
                var docname = _paceGetDocName();
                paceShowToast(__('Generating receipt\u2026'), 'info');
                frappe.call({
                    method: 'slcm.pace.web_form.pace_application_form.pace_application_form.generate_pace_receipt',
                    args: { application_name: docname },
                    callback: function(r) {
                        var receipt_name = r.message;
                        if (receipt_name) {
                            frappe.call({
                                method: 'slcm.pace.web_form.pace_application_form.pace_application_form.get_pace_admission_fee',
                                args: { application: docname },
                                callback: function(r2) {
                                    var template = r2.message.template || 'Standard';
                                    var url = '/api/method/frappe.utils.print_format.download_pdf?' +
                                        'doctype=PACE%20Receipt&name=' + encodeURIComponent(receipt_name) +
                                        '&format=' + encodeURIComponent(template) + '&no_letterhead=0';
                                    window.open(url, '_blank');
                                }
                            });
                        } else {
                            paceShowToast(__('Receipt not found. If you just paid, please wait or reload.'), 'error');
                        }
                    }
                });
            });
            $actions.append(btn);
        }
    }, 2000);
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

	// Flex row (see .pace-stepper-flex): connectors use capped width so ultrawide does not add huge gaps
	var html = '<div id="pace-stepper-wrap"><div class="pace-stepper pace-stepper-flex">';
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
		var $lab = $wrap.children('.control-label').first();
		if ($lab.length) {
			$lab.after($prev);
		} else {
			$wrap.prepend($prev);
		}
	} else {
		var $lab2 = $wrap.children('.control-label').first();
		if ($lab2.length && $prev.prev()[0] !== $lab2[0]) {
			$lab2.after($prev);
		}
	}
	var $img = $prev.find('img');
	if ($img.attr('data-pace-src') !== src) {
		$img.attr('data-pace-src', src).attr('src', src);
	}
}

/**
 * Frappe Web Form often drops visible labels on Attach / Attach Image when read-only (submitted) mode.
 * Same approach as slcm/admission/web_form/applicant_form.js — prepend .control-label from DocField metadata.
 */
function paceInjectAttachFieldLabels() {
	var wf = window.frappe && frappe.web_form;
	if (!wf || !wf.fields_dict) return;

	document.querySelectorAll('.frappe-control[data-fieldname][data-fieldtype]').forEach(function (field) {
		var fieldname = field.getAttribute('data-fieldname');
		var fieldtype = field.getAttribute('data-fieldtype');
		if (!fieldname || !fieldtype) return;
		if (fieldtype !== 'Attach' && fieldtype !== 'Attach Image') return;
		if (field.querySelector('.control-label')) return;

		var fd = wf.fields_dict[fieldname] && wf.fields_dict[fieldname].df;
		var labelText = (fd && fd.label) || fieldname;
		var lbl = document.createElement('label');
		lbl.className = 'control-label';
		lbl.textContent = labelText;
		field.insertBefore(lbl, field.firstChild);
	});

	document.querySelectorAll('.frappe-control .btn-attach').forEach(function (btn) {
		var misplaced = btn.querySelectorAll('.control-label');
		if (!misplaced.length) return;
		misplaced.forEach(function (n) { n.remove(); });
		if (!(btn.textContent || '').trim()) btn.textContent = __('Attach');
	});
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

	// Read-only logic based on status
	paceSetupReadonlyLogic();

	// Submission and Payment handling
	paceSetupSubmission();

	// Receipt download button
	paceSetupReceiptButton();

	// Stepper with mandatory validation
	paceSetupStepper();

	// Student Photo Preview
	paceSetupPhotoPreview();

	// Attach field validation
	paceSetupAttachValidation();
	paceSetupForcePublicUploads();

	// Attach labels in read-only / after Frappe re-render (applicant_form parity)
	setTimeout(function () { paceInjectAttachFieldLabels(); }, 500);
	setTimeout(function () { paceInjectAttachFieldLabels(); }, 2000);
	var _paceAttachLblN = 0;
	var _paceAttachLblTimer = setInterval(function () {
		paceInjectAttachFieldLabels();
		if (++_paceAttachLblN > 100) clearInterval(_paceAttachLblTimer);
	}, 400);

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
/**
 * Renders the After Submission success page.
 */
function paceRenderSuccessPage() {
	var wf = frappe.web_form;
	var title = wf.success_title || __('Application Submitted Successfully');
	var message = wf.success_message || __('Thank you! Your application has been submitted successfully.');
	var success_url = wf.success_url || '/pace_application_card';

	var html = `
		<style>
			.pace-success-container {
				max-width: 600px;
				margin: 100px auto;
				text-align: center;
				padding: 40px 20px;
				background: #fff;
				border-radius: 12px;
				box-shadow: 0 10px 25px rgba(0,0,0,0.05);
			}
			.pace-success-icon {
				width: 80px;
				height: 80px;
				background: #10b981;
				color: #fff;
				border-radius: 50%;
				display: flex;
				align-items: center;
				justify-content: center;
				margin: 0 auto 30px;
				font-size: 40px;
				box-shadow: 0 8px 16px rgba(16, 185, 129, 0.2);
			}
			.pace-success-title {
				font-size: 28px;
				font-weight: 700;
				margin-bottom: 20px;
				color: #1f2937;
			}
			.pace-success-message {
				font-size: 16px;
				line-height: 1.6;
				margin-bottom: 40px;
				color: #4b5563;
			}
			.pace-success-btn {
				display: inline-block;
				background: #1a3c6e;
				color: #fff !important;
				padding: 14px 32px;
				border-radius: 8px;
				text-decoration: none !important;
				font-weight: 600;
				transition: all 0.2s;
			}
			.pace-success-btn:hover {
				background: #132d54;
				transform: translateY(-2px);
			}
		</style>
		<div class="pace-success-container">
			<div class="pace-success-icon">
				<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="20 6 9 17 4 12"></polyline>
				</svg>
			</div>
			<h1 class="pace-success-title">${title}</h1>
			<div class="pace-success-message">${message}</div>
			<a href="${success_url}" class="pace-success-btn">${__('Go to Dashboard')}</a>
		</div>
	`;

	var $shell = $('.pace-portal-shell');
	if ($shell.length) {
		$shell.find('.pace-portal-content').html(html);
		window.scrollTo(0, 0);
	} else {
		$('.web-form-container').html(html);
	}
}

