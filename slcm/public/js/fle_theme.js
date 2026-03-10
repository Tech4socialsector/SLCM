/**
 * Global Javascript for Foundations for Legal Education UI
 * ─────────────────────────────────────────────────────────────────────────────
 * SECTION 0: AUTH GUARD — Must be the VERY FIRST thing that runs.
 * Blocks unauthenticated access to /foundations-for-a-legal-education/new
 * ─────────────────────────────────────────────────────────────────────────────
 */
(function () {
    'use strict';

    var path = window.location.pathname;
    var isProtected = path.indexOf('/foundations-for-a-legal-education') !== -1 &&
        path.indexOf('/new') !== -1;

    if (!isProtected) return;

    var style = document.createElement('style');
    style.id = 'fle-guard-veil';
    style.textContent =
        'html, body { visibility: hidden !important; opacity: 0 !important; }';
    document.documentElement.appendChild(style);

    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function goToLogin() {
        var next = encodeURIComponent(window.location.href);
        window.location.replace('/fle/login?next=' + next);
    }

    function revealPage() {
        var s = document.getElementById('fle-guard-veil');
        if (s && s.parentNode) s.parentNode.removeChild(s);
        document.documentElement.style.removeProperty('visibility');
        document.documentElement.style.removeProperty('opacity');
        if (document.body) {
            document.body.style.removeProperty('visibility');
            document.body.style.removeProperty('opacity');
        }
    }

    function checkFrappeSession() {
        try {
            if (typeof frappe !== 'undefined' &&
                frappe.session && frappe.session.user &&
                frappe.session.user !== 'Guest') {
                return frappe.session.user;
            }
        } catch (e) { }
        return null;
    }

    function checkFrappeCookie() {
        var uid = getCookie('user_id') || getCookie('frappe_userid');
        if (uid && uid !== 'Guest' && uid.length > 0) return uid;
        var sid = getCookie('sid');
        if (sid && sid !== 'Guest' && sid.length > 10) return sid;
        return null;
    }

    function checkViaXHR() {
        try {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/method/frappe.auth.get_logged_user', false);
            xhr.withCredentials = true;
            var csrf = getCookie('X-Frappe-CSRF-Token') || getCookie('frappe_csrf_token');
            if (!csrf && typeof frappe !== 'undefined') csrf = frappe.csrf_token || '';
            if (csrf) xhr.setRequestHeader('X-Frappe-CSRF-Token', csrf);
            xhr.send(null);
            if (xhr.status === 200) {
                var resp = JSON.parse(xhr.responseText);
                var user = resp && resp.message ? resp.message : null;
                return (user && user !== 'Guest') ? user : null;
            }
            return null;
        } catch (e) {
            return null;
        }
    }

    var user = checkFrappeSession() || checkFrappeCookie() || checkViaXHR();

    if (!user) {
        goToLogin();
        return;
    }

    revealPage();
    document.addEventListener('DOMContentLoaded', revealPage);

})();


// ─────────────────────────────────────────────────────────────────────────────
// SECTION 0B: POST-LOGIN REDIRECT
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    'use strict';

    var path = window.location.pathname;
    if (path.indexOf('login') === -1) return;

    function getNextParam() {
        try { return new URLSearchParams(window.location.search).get('next'); }
        catch (e) {
            var m = window.location.search.match(/[?&]next=([^&]*)/);
            return m ? decodeURIComponent(m[1]) : null;
        }
    }

    var nextUrl = getNextParam();
    if (!nextUrl) return;

    var poll = setInterval(function () {
        try {
            if (typeof frappe !== 'undefined' &&
                frappe.session && frappe.session.user &&
                frappe.session.user !== 'Guest') {
                clearInterval(poll);
                window.location.replace(nextUrl);
            }
        } catch (e) { }
    }, 250);

    document.addEventListener('frappe:login', function () {
        clearInterval(poll);
        window.location.replace(nextUrl);
    });

    setTimeout(function () { clearInterval(poll); }, 900000);
})();


// ─────────────────────────────────────────────────────────────────────────────
// SECTION 1: LOGIN PAGE — Hide Frappe's navbar
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    var path = window.location.pathname;
    if (path.indexOf('login') === -1) return;

    function patch_frappe_navbar() {
        if (typeof frappe === 'undefined') return;
        if (frappe.ui && frappe.ui.toolbar) {
            frappe.ui.toolbar.setup = function () { };
            frappe.ui.toolbar.update_notifications = function () { };
        }
        if (frappe.toolbar) { frappe.toolbar.setup = function () { }; }
        if (frappe.router) {
            var orig = frappe.router.on_change;
            frappe.router.on_change = function () {
                removeNavbars();
                if (orig) orig.apply(this, arguments);
            };
        }
    }

    function removeNavbars() {
        ['header.navbar', 'header.navbar.navbar-expand-lg', '.navbar.navbar-expand',
            '.navbar.navbar-expand-lg', '#navbar-main', '.web-header', '.top-bar', 'body > nav'
        ].forEach(function (sel) {
            document.querySelectorAll(sel).forEach(function (el) {
                if (el.classList.contains('sticky-header') || el.classList.contains('navbar-navy')) return;
                if (el.parentNode) el.parentNode.removeChild(el);
            });
        });
        if (document.body) document.body.style.setProperty('padding-top', '0', 'important');
    }

    var style = document.createElement('style');
    style.id = 'fle-nuke-navbar';
    style.textContent =
        'header.navbar, .navbar.navbar-expand-lg, .navbar.navbar-expand,' +
        '#navbar-main, .web-header, .top-bar, body > nav, .breadcrumb-container, .page-head,' +
        '.navbar-user-icon, .avatar-frame, .avatar, .navbar-light {' +
        'display:none!important; visibility:hidden!important; height:0!important;' +
        'max-height:0!important; overflow:hidden!important; pointer-events:none!important;' +
        'position:fixed!important; top:-9999px!important; opacity:0!important; }' +
        'body { padding-top:0!important; }';
    var head = document.head || document.getElementsByTagName('head')[0] || document.documentElement;
    head.firstChild ? head.insertBefore(style, head.firstChild) : head.appendChild(style);

    var observer = new MutationObserver(function (mutations) {
        var hit = false;
        mutations.forEach(function (m) {
            m.addedNodes.forEach(function (node) {
                if (node.nodeType !== 1) return;
                var cls = (node.className || '').toString();
                if (((node.tagName || '').toLowerCase() === 'header' && cls.indexOf('navbar') !== -1) ||
                    cls.indexOf('navbar-expand') !== -1 || node.id === 'navbar-main' ||
                    cls.indexOf('top-bar') !== -1 || cls.indexOf('web-header') !== -1) {
                    hit = true;
                }
            });
        });
        if (hit) removeNavbars();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });

    removeNavbars();
    document.addEventListener('DOMContentLoaded', function () { patch_frappe_navbar(); removeNavbars(); });
    window.addEventListener('load', function () {
        patch_frappe_navbar(); removeNavbars();
        setTimeout(function () { observer.disconnect(); }, 5000);
    });
    ['frappe:ready', 'page-change', 'page-load', 'after-ajax'].forEach(function (evt) {
        document.addEventListener(evt, removeNavbars);
    });
    [0, 50, 100, 200, 300, 500, 700, 1000, 1500, 2000, 3000].forEach(function (ms) {
        setTimeout(function () { patch_frappe_navbar(); removeNavbars(); }, ms);
    });
})();


// ─────────────────────────────────────────────────────────────────────────────
// SECTION 2: HEADER + FOOTER INJECTION (non-login pages)
// ─────────────────────────────────────────────────────────────────────────────
window.inject_fle_header_footer = function () {
    if ($('.sticky-header').length > 0) return;

    // ── 0. Global CSS refinement for FLE ──────────────────────────────────────
    if ($('#fle-global-refinements').length === 0) {
        $('head').append(`
        <style id="fle-global-refinements">
            /* Hide Home button in FLE status pages */
            body[data-path*="payment-failed"] a:contains("Home"),
            body[data-path*="payment-cancel"] a:contains("Home"),
            .fle-actions a.btn-outline-secondary:contains("Home"),
            .page-card a.btn-outline-secondary:contains("Home"),
            .fle-actions a:contains("Home"),
            .page-card a:contains("Home") {
                display: none !important;
            }
        </style>
        `);
    }

    // ── 1. Load Google Fonts ──────────────────────────────────────────────────
    $('head').append('<link rel="preconnect" href="https://fonts.googleapis.com">');
    $('head').append('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>');
    $('head').append('<link href="https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,300;0,400;0,700;1,300;1,400&display=swap" rel="stylesheet">');
    $('head').append('<link rel="stylesheet" href="/fle/css/login.css">');

    // ── 2. MASTER FONT FIX — Override ALL Frappe web form typography ─────────
    if ($('#fle-form-font-style').length === 0) {
        $('head').append(`
        <style id="fle-form-font-style">
            :root { --font-stack: 'Merriweather', Georgia, 'Times New Roman', serif; }

            body, .web-form-wrapper, .web-form-page, .form-layout, .page-container,
            .page-content, .container, .container-fluid, .row, .col,
            p, span, div, label, a, li, td, th {
                font-family: 'Merriweather', Georgia, 'Times New Roman', serif !important;
            }

            h1, h2, h3, h4, h5, h6, .page-title,
            .web-form-page h1, .web-form-page h2,
            .web-form-page h3, .web-form-page h4 {
                font-family: 'Merriweather', Georgia, serif !important;
                font-weight: 700 !important;
                color: #1a1a1a !important;
            }

            .web-form-page .section-head, .web-form-wrapper .section-head,
            .form-section .section-head, .section-head, h2.section-head {
                font-family: 'Merriweather', Georgia, serif !important;
                font-size: 18px !important;
                font-weight: 700 !important;
                color: #1a1a1a !important;
                letter-spacing: 0.2px !important;
                margin-bottom: 16px !important;
            }

            .control-label, .frappe-control .control-label, label.control-label,
            .web-form-page label, .web-form-wrapper label, .form-group label {
                font-family: 'Merriweather', Georgia, serif !important;
                font-size: 12px !important;
                font-weight: 400 !important;
                color: #444444 !important;
                letter-spacing: 0.3px !important;
            }

            .frappe-control, .frappe-control *, .form-group, .form-group * {
                font-family: 'Merriweather', Georgia, serif !important;
            }

            input[type="text"], input[type="email"], input[type="tel"],
            input[type="number"], input[type="date"], input[type="password"],
            input[type="search"], select, textarea, .form-control,
            .frappe-control input, .frappe-control select, .frappe-control textarea,
            .frappe-control .input-with-feedback, .frappe-control .like-disabled-input,
            .input-with-feedback, .like-disabled-input,
            .web-form-page input, .web-form-page select, .web-form-page textarea {
                font-family: 'Merriweather', Georgia, 'Times New Roman', serif !important;
                font-size: 13.5px !important;
                font-weight: 300 !important;
                color: #1a1a1a !important;
            }

            select option, .dropdown-menu, .dropdown-item, .select-items, .select-item {
                font-family: 'Merriweather', Georgia, serif !important;
                font-size: 13px !important;
            }

            .help-box, .frappe-control .help-box, .text-muted, small, .form-text {
                font-family: 'Merriweather', Georgia, serif !important;
                font-size: 11.5px !important;
                font-weight: 300 !important;
            }

            .breadcrumb-area, .form-meta, .indicator, .page-breadcrumbs,
            .breadcrumb, .breadcrumb-item, .breadcrumb-item a {
                font-family: 'Merriweather', Georgia, serif !important;
                font-size: 12px !important;
            }

            /* ── Generic font fallback for buttons (appearance only, no layout) ── */
            .btn, button, .btn-sm, .btn-lg,
            input[type="submit"], input[type="button"], input[type="reset"] {
                font-family: 'Merriweather', Georgia, serif !important;
                font-weight: 700 !important;
                letter-spacing: 0.5px !important;
                white-space: nowrap !important;
            }

            .attach-btn, .attach-label, .input-area, .attached-file,
            .attached-file-link, .file-uploader, .file-uploader * {
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .reqd, .required, .asterisk { color: #8B0000 !important; }

            .modal, .modal *, .alert, .alert * {
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .web-form-page .page-title, .web-form-page .title-area,
            .web-form-page .subtitle {
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .indicator-pill, .indicator, .badge {
                font-family: 'Merriweather', Georgia, serif !important;
                font-size: 11px !important;
            }

            table, thead, tbody, tr, td, th {
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .web-form-page a, .web-form-wrapper a { color: #8B0000 !important; }
            .web-form-page a:hover, .web-form-wrapper a:hover { color: #6a0000 !important; }

            /* ── FIELD LABEL CASE FIX ── */
            .control-label, .frappe-control .control-label, label.control-label,
            .web-form-page label, .web-form-wrapper label, .form-group label,
            .field-area label, .frappe-control label,
            .web-form-page .control-label, .web-form-wrapper .control-label,
            .section-body .control-label, .form-column .control-label {
                text-transform: capitalize !important;
                letter-spacing: 0.2px !important;
                font-size: 13px !important;
                font-weight: 400 !important;
                color: #444444 !important;
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .section-head, .web-form-page .section-head,
            .web-form-wrapper .section-head, .form-section .section-head {
                text-transform: none !important;
                font-size: 18px !important;
                font-weight: 700 !important;
                color: #1a1a1a !important;
            }

            .navbar-navy .nav-item { text-transform: uppercase !important; }
            button.fle-logout-btn  { text-transform: uppercase !important; }
        </style>`);
    }

    // ── 3. Header/footer/logout styles ───────────────────────────────────────
    if ($('#fle-logout-style').length === 0) {
        $('head').append(`
        <style id="fle-logout-style">
            .sticky-header { background-color:#ffffff!important; box-shadow:0 2px 6px rgba(0,0,0,0.1)!important; }
            .sticky-header .header-top {
                display:flex!important; flex-direction:row!important; align-items:center!important;
                justify-content:space-between!important; width:100%!important;
                box-sizing:border-box!important; padding:10px 24px!important; background-color:#ffffff!important;
            }
            .sticky-header .logo-container {
                display:flex!important; align-items:center!important;
                flex:0 0 auto!important; margin-right:16px!important;
            }
            .sticky-header .logo-container a { display:inline-block!important; line-height:0!important; }
            .sticky-header .logo-img {
                display:block!important; height:70px!important; width:auto!important;
                max-width:120px!important; object-fit:contain!important;
                visibility:visible!important; opacity:1!important;
            }
            .sticky-header .brand-text {
                flex:1 1 auto!important; text-align:center!important; padding:0 16px!important;
                font-family:'Merriweather', Georgia, serif !important;
            }
            .sticky-header .brand-text .university-name {
                font-family:'Merriweather', Georgia, serif !important;
                font-size:13px !important; font-weight:400 !important; color:#8B0000 !important;
                margin:0 0 4px !important; letter-spacing:0.5px !important; text-transform:uppercase !important;
            }
            .sticky-header .brand-text .department-name {
                font-family:'Merriweather', Georgia, serif !important;
                font-size:18px !important; font-weight:700 !important; color:#8B0000 !important;
                margin:0 !important; letter-spacing:0.2px !important;
            }
            .breadcrumb, .page-breadcrumbs, .breadcrumb-container, .page-head,
            .navbar-user-icon, .avatar { display:none!important; visibility:hidden!important; }
            .sticky-header .header-logout-area {
                flex:0 0 auto!important; display:flex!important; align-items:center!important;
                justify-content:flex-end!important; min-width:130px!important;
            }
            button.fle-logout-btn {
                all:unset!important; box-sizing:border-box!important; display:inline-flex!important;
                align-items:center!important; justify-content:center!important; gap:7px!important;
                background-color:#8B0000!important; color:#ffffff!important; border:none!important;
                border-radius:5px!important; padding:8px 18px!important; font-size:13px!important;
                font-family:'Merriweather',Georgia,serif!important; font-weight:700!important;
                cursor:pointer!important; letter-spacing:0.6px!important; text-transform:uppercase!important;
                white-space:nowrap!important; visibility:visible!important; opacity:1!important;
                pointer-events:auto!important; transition:background-color 0.2s ease,transform 0.1s ease!important;
                box-shadow:0 2px 5px rgba(139,0,0,0.35)!important; position:relative!important; z-index:9999!important;
            }
            button.fle-logout-btn:hover { background-color:#6a0000!important; transform:translateY(-1px)!important; color:#ffffff!important; }
            button.fle-logout-btn:active { transform:translateY(0px)!important; background-color:#5a0000!important; }
            button.fle-logout-btn svg { display:inline-block!important; flex-shrink:0!important; vertical-align:middle!important; }
            #fle-logout-modal-overlay {
                display:none; position:fixed; inset:0; background:rgba(0,0,0,0.55);
                z-index:99999; align-items:center; justify-content:center;
                backdrop-filter:blur(3px); -webkit-backdrop-filter:blur(3px);
            }
            #fle-logout-modal-overlay.active { display:flex!important; }
            @keyframes fle-slide-up {
                from { opacity:0; transform:translateY(18px) scale(0.97); }
                to   { opacity:1; transform:translateY(0) scale(1); }
            }
            #fle-logout-modal {
                background:#ffffff; border-radius:10px; box-shadow:0 20px 60px rgba(0,0,0,0.25);
                padding:36px 40px 32px; max-width:420px; width:90%; text-align:center;
                font-family:'Merriweather',Georgia,serif; animation:fle-slide-up 0.25s ease;
            }
            #fle-logout-modal .fle-modal-icon {
                width:52px; height:52px; margin:0 auto 18px; background:#fff4f4; border-radius:50%;
                display:flex; align-items:center; justify-content:center;
            }
            #fle-logout-modal h2 { font-size:18px; font-weight:700; color:#1a1a1a; margin:0 0 10px; font-family:'Merriweather',Georgia,serif; }
            #fle-logout-modal p { font-size:13.5px; color:#555; line-height:1.65; margin:0 0 28px; font-weight:300; font-family:'Merriweather',Georgia,serif; }
            #fle-logout-modal p strong { color:#1a1a1a; font-weight:700; }
            .fle-modal-actions { display:flex; gap:12px; justify-content:center; }
            .fle-modal-btn {
                all:unset; box-sizing:border-box; display:inline-flex; align-items:center;
                justify-content:center; gap:6px; padding:9px 22px; border-radius:5px;
                font-family:'Merriweather',Georgia,serif; font-size:12.5px; font-weight:700;
                letter-spacing:0.5px; text-transform:uppercase; cursor:pointer;
                transition:background-color 0.2s ease,transform 0.1s ease,box-shadow 0.2s ease;
            }
            .fle-modal-btn-cancel { background:#f0f0f0; color:#444; border:1px solid #ddd; }
            .fle-modal-btn-cancel:hover { background:#e2e2e2; transform:translateY(-1px); }
            .fle-modal-btn-confirm { background:#8B0000; color:#fff; box-shadow:0 2px 6px rgba(139,0,0,0.3); }
            .fle-modal-btn-confirm:hover { background:#6a0000; transform:translateY(-1px); box-shadow:0 4px 12px rgba(139,0,0,0.4); }
            .fle-modal-btn-confirm:active, .fle-modal-btn-cancel:active { transform:translateY(0); }
            .fle-btn-spinner {
                display:none; width:13px; height:13px; border:2px solid rgba(255,255,255,0.4);
                border-top-color:#ffffff; border-radius:50%; animation:fle-spin 0.6s linear infinite;
            }
            .fle-modal-btn-confirm.loading .fle-btn-spinner { display:inline-block!important; }
            .fle-modal-btn-confirm.loading .fle-btn-icon,
            .fle-modal-btn-confirm.loading .fle-btn-label { display:none!important; }
            .fle-modal-btn-confirm.loading { pointer-events:none; opacity:0.85; }
            @keyframes fle-spin { to { transform:rotate(360deg); } }

            .navbar-navy {
                background-color:#8B0000!important; display:flex!important; flex-wrap:wrap!important;
                justify-content:center!important; gap:0!important; padding:0!important;
                font-family:'Merriweather',Georgia,serif!important;
            }
            .navbar-navy .nav-item {
                color:#ffffff!important; text-decoration:none!important; padding:12px 20px!important;
                font-size:12px!important; font-weight:700!important; letter-spacing:0.8px!important;
                text-transform:uppercase!important; font-family:'Merriweather',Georgia,serif!important;
                transition:background-color 0.2s ease!important;
            }
            .navbar-navy .nav-item:hover {
                background-color:rgba(255,255,255,0.15)!important; color:#ffffff!important;
            }

            .sticky-footer {
                background-color:#8b0000 !important; color:#ffffff!important;
                text-align:center!important; padding:18px 24px!important;
                font-size:12px!important; font-family:'Merriweather',Georgia,serif!important;
                font-weight:300!important; letter-spacing:0.3px!important;
                margin-top:auto!important; width:100%!important;
            }
        </style>`);
    }

    // ── 4. Inject Header HTML ─────────────────────────────────────────────────
    var header_html = `
    <header class="sticky-header">
        <div class="header-top">
            <div class="logo-container">
                <a href="https://pace.nls.ac.in/" target="_blank" rel="noopener noreferrer">
                    <img src="/files/nlsiu-logo.jpeg" alt="NLSIU Logo" class="logo-img"
                         onerror="this.onerror=null; this.style.display='none';">
                </a>
            </div>
            <div class="brand-text">
                <h5 class="university-name">National Law School of India University, Bengaluru</h5>
                <h1 class="department-name">Foundations for a Legal Education Certificate Course</h1>
            </div>
            <div class="header-logout-area">
                <button class="fle-logout-btn" id="fle-logout-btn" type="button">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                         fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                    Logout
                </button>
            </div>
        </div>
        <nav class="navbar-navy">
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item" target="_blank">OVERVIEW</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">COURSES</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FACULTY</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FEE</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FAQs</a>
            <a href="https://pace.nls.ac.in/contact-us/" class="nav-item">Contact Us</a>
        </nav>
    </header>`;

    // ── 5. Inject Footer HTML ─────────────────────────────────────────────────
    var footer_html = `
    <footer class="sticky-footer">
        &copy; 2026 National Law School of India University. All Rights Reserved.
    </footer>`;

    if ($('body').length === 0) return;
    $('body').prepend(header_html);
    $('body').append(footer_html);

    // ── 6. Inject Logout Modal ────────────────────────────────────────────────
    if ($('#fle-logout-modal-overlay').length === 0) {
        $('body').append(`
        <div id="fle-logout-modal-overlay">
            <div id="fle-logout-modal" role="dialog" aria-modal="true" aria-labelledby="fle-modal-title">
                <div class="fle-modal-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
                         fill="none" stroke="#8B0000" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                </div>
                <h2 id="fle-modal-title">Confirm Logout</h2>
                <p>Are you sure you want to log out of the<br><strong>Foundations for a Legal Education</strong> portal?</p>
                <div class="fle-modal-actions">
                    <button class="fle-modal-btn fle-modal-btn-cancel" id="fle-modal-cancel" type="button">Cancel</button>
                    <button class="fle-modal-btn fle-modal-btn-confirm" id="fle-modal-confirm" type="button">
                        <svg class="fle-btn-icon" xmlns="http://www.w3.org/2000/svg" width="13" height="13"
                             viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"
                             stroke-linecap="round" stroke-linejoin="round">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                            <polyline points="16 17 21 12 16 7"></polyline>
                            <line x1="21" y1="12" x2="9" y2="12"></line>
                        </svg>
                        <span class="fle-btn-label">Yes, Logout</span>
                        <span class="fle-btn-spinner"></span>
                    </button>
                </div>
            </div>
        </div>`);
    }

    // ── 7. Event Listeners ────────────────────────────────────────────────────
    $(document).on('click', '#fle-logout-btn', function () {
        $('#fle-logout-modal-overlay').addClass('active');
    });
    $(document).on('click', '#fle-modal-cancel', function () {
        $('#fle-logout-modal-overlay').removeClass('active');
    });
    $(document).on('click', '#fle-logout-modal-overlay', function (e) {
        if ($(e.target).is('#fle-logout-modal-overlay')) {
            $('#fle-logout-modal-overlay').removeClass('active');
        }
    });
    $(document).on('keydown', function (e) {
        if (e.key === 'Escape') $('#fle-logout-modal-overlay').removeClass('active');
    });
    $(document).on('click', '#fle-modal-confirm', function () {
        $(this).addClass('loading');
        $.ajax({
            url: '/api/method/logout',
            type: 'GET',
            complete: function () { window.location.replace('/fle/login.html'); }
        });
    });

    // ── 8. Layout fix — sticky header + flex body ─────────────────────────────
    $('html, body').css({ 'overflow-x': 'hidden', 'height': '100%', 'position': 'relative' });
    $('body').css({ 'display': 'flex', 'flex-direction': 'column', 'min-height': '100vh', 'margin': '0' });
    $('.web-form-page, .page-container').css('flex', '1 0 auto');
    $('.sticky-header').css({ 'position': 'fixed', 'top': '0', 'left': '0', 'z-index': '1020', 'width': '100%' });
    $('body').css('padding-top', '150px');
    $('.sticky-footer').css({ 'margin-top': 'auto', 'width': '100%' });

    // ── 9. Force visibility + fonts after a short delay ───────────────────────
    setTimeout(function () {
        var btn = document.getElementById('fle-logout-btn');
        if (btn) {
            btn.style.setProperty('display', 'inline-flex', 'important');
            btn.style.setProperty('visibility', 'visible', 'important');
            btn.style.setProperty('opacity', '1', 'important');
            btn.style.setProperty('background-color', '#8B0000', 'important');
            btn.style.setProperty('color', '#ffffff', 'important');
            btn.style.setProperty('padding', '8px 18px', 'important');
            btn.style.setProperty('border-radius', '5px', 'important');
            btn.style.setProperty('font-weight', '700', 'important');
            btn.style.setProperty('cursor', 'pointer', 'important');
            btn.style.setProperty('z-index', '9999', 'important');
        }
        var area = document.querySelector('.header-logout-area');
        if (area) {
            area.style.setProperty('display', 'flex', 'important');
            area.style.setProperty('align-items', 'center', 'important');
            area.style.setProperty('visibility', 'visible', 'important');
        }
        var logoImg = document.querySelector('.sticky-header .logo-img');
        if (logoImg) {
            logoImg.style.setProperty('display', 'block', 'important');
            logoImg.style.setProperty('visibility', 'visible', 'important');
            logoImg.style.setProperty('opacity', '1', 'important');
            logoImg.style.setProperty('height', '70px', 'important');
            logoImg.style.setProperty('width', 'auto', 'important');
        }
        var logoCont = document.querySelector('.sticky-header .logo-container');
        if (logoCont) {
            logoCont.style.setProperty('display', 'flex', 'important');
            logoCont.style.setProperty('visibility', 'visible', 'important');
        }

        // Font + case fix
        document.querySelectorAll(
            'input, select, textarea, label, .control-label, .section-head, ' +
            '.frappe-control, .form-control, .help-box, ' +
            '.web-form-page *, .web-form-wrapper *'
        ).forEach(function (el) {
            el.style.setProperty('font-family', "'Merriweather', Georgia, serif", 'important');
        });

        document.querySelectorAll(
            '.control-label, label.control-label, .web-form-page label, ' +
            '.web-form-wrapper label, .frappe-control label, .form-group label'
        ).forEach(function (el) {
            el.style.setProperty('text-transform', 'capitalize', 'important');
            el.style.setProperty('letter-spacing', '0.2px', 'important');
        });

        document.querySelectorAll('.section-head').forEach(function (el) {
            el.style.setProperty('text-transform', 'none', 'important');
        });

    }, 200);

    // ── 10. Re-apply fonts after Frappe re-renders ────────────────────────────
    setTimeout(function () {
        document.querySelectorAll(
            'input, select, textarea, label, .control-label, .section-head, ' +
            '.frappe-control, .form-control, .help-box, ' +
            '.web-form-page *, .web-form-wrapper *'
        ).forEach(function (el) {
            el.style.setProperty('font-family', "'Merriweather', Georgia, serif", 'important');
        });

        document.querySelectorAll(
            '.control-label, label.control-label, .web-form-page label, ' +
            '.web-form-wrapper label, .frappe-control label, .form-group label'
        ).forEach(function (el) {
            el.style.setProperty('text-transform', 'capitalize', 'important');
            el.style.setProperty('letter-spacing', '0.2px', 'important');
        });

        document.querySelectorAll('.section-head').forEach(function (el) {
            el.style.setProperty('text-transform', 'none', 'important');
        });
    }, 1000);

    // NOTE: applyButtonStyles() has been REMOVED from global.js.
    // All web form footer button styling is now owned exclusively by
    // applyFooterButtonStyles() inside webform.js.
};


/**
 * ── Special Handler: Payment Cancel/Failed Pages ──────────────────────────────
 */
window.handle_payment_status_pages = function () {
    function patchStatusPage() {
        var allButtons = $('.page-card a, .fle-actions a, .page-card button');

        allButtons.each(function () {
            var $el = $(this);
            var text = $el.text().trim().toLowerCase();

            if (text.indexOf('try again') !== -1 || text.indexOf('continue') !== -1) {
                $el.text('Try again');
                $el.attr('href', '/foundations-for-a-legal-education/new');

                $el.off('click.autoedit').on('click.autoedit', function () {
                    sessionStorage.setItem('fle_auto_edit', '1');
                });

                $el.css({
                    'background-color': '#8B0000',
                    'border-color': '#8B0000',
                    'color': '#ffffff',
                    'font-family': "'Merriweather', Georgia, serif",
                    'font-weight': '700',
                    'padding': '10px 22px',
                    'border-radius': '5px',
                    'text-transform': 'none',
                    'letter-spacing': '0.5px',
                    'display': 'inline-flex',
                    'align-items': 'center',
                    'justify-content': 'center',
                    'text-decoration': 'none'
                });
            }

            if (text === 'home') {
                $el.attr('style', 'display: none !important');
                $el.hide();
            }
        });

        $('.page-card').css({
            'font-family': "'Merriweather', Georgia, serif",
            'border-radius': '10px',
            'box-shadow': '0 4px 20px rgba(0,0,0,0.08)'
        });
        $('.page-card p').css('font-weight', '300');
        $('.indicator.red').css('font-weight', '700');
    }

    patchStatusPage();
    setTimeout(patchStatusPage, 100);
    setTimeout(patchStatusPage, 500);
    setTimeout(patchStatusPage, 1500);
    setTimeout(patchStatusPage, 3000);
};


/**
 * ── Auto-Edit Mode Trigger ──────────────────────────────────────────────────
 */
window.check_auto_edit_mode = function () {
    var path = window.location.pathname;
    if (path.indexOf('/foundations-for-a-legal-education') === -1) return;

    if (sessionStorage.getItem('fle_auto_edit') === '1') {
        function triggerEdit() {
            var editBtn = $('.edit-button');
            if (editBtn.length > 0) {
                sessionStorage.removeItem('fle_auto_edit');
                editBtn[0].click();
            }
        }
        triggerEdit();
        setTimeout(triggerEdit, 500);
        setTimeout(triggerEdit, 1500);
    }
};


// ─────────────────────────────────────────────────────────────────────────────
// SECTION 3: ROUTE-BASED INJECTION
// ─────────────────────────────────────────────────────────────────────────────
function try_inject_fle_theme() {
    var path = window.location.pathname;
    if (path.indexOf('login') !== -1) return;

    var valid_routes = [
        '/payment-success', '/payment-failed', '/payment-cancel',
        '/fle-success-page', '/integration-request', '/foundations-for-a-legal-education'
    ];

    var isStatusPage = path.indexOf('/payment-cancel') !== -1 ||
        path.indexOf('/payment-failed') !== -1 ||
        path.indexOf('/payment-success') !== -1;
    var isFoundationsPage = path.indexOf('/foundations-for-a-legal-education') !== -1;

    for (var i = 0; i < valid_routes.length; i++) {
        if (path.indexOf(valid_routes[i]) !== -1) {
            if (typeof inject_fle_header_footer === 'function') inject_fle_header_footer();
            if (isFoundationsPage) {
                if (typeof check_auto_edit_mode === 'function') check_auto_edit_mode();
            }
            break;
        }
    }

    if (isStatusPage) {
        if (typeof handle_payment_status_pages === 'function') handle_payment_status_pages();
    }
}

$(document).ready(try_inject_fle_theme);
$(window).on('load', try_inject_fle_theme);
document.addEventListener('DOMContentLoaded', try_inject_fle_theme);
if (typeof frappe !== 'undefined' && frappe.ready) { frappe.ready(try_inject_fle_theme); }
setTimeout(try_inject_fle_theme, 500);
setTimeout(try_inject_fle_theme, 1000);