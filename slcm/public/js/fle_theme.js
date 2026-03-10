/**
 * Global Javascript for Foundations for Legal Education UI
 * ─────────────────────────────────────────────────────────────────────────────
 * SECTION 0: AUTH GUARD — Must be the VERY FIRST thing that runs.
 * Blocks unauthenticated access to /foundations-for-a-legal-education/new
 * ─────────────────────────────────────────────────────────────────────────────
 */
(function () {
    'use strict';

    // ── 1. Are we on the protected /new route? ────────────────────────────────
    var path = window.location.pathname;
    var isProtected = path.indexOf('/foundations-for-a-legal-education') !== -1 &&
        path.indexOf('/new') !== -1;

    if (!isProtected) return;

    // ── 2. Freeze the page instantly — zero flash ─────────────────────────────
    var style = document.createElement('style');
    style.id = 'fle-guard-veil';
    style.textContent =
        'html, body { visibility: hidden !important; opacity: 0 !important; }';
    document.documentElement.appendChild(style);

    // ── 3. Helpers ────────────────────────────────────────────────────────────
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

    // ── 4. Three-layer auth detection ─────────────────────────────────────────

    // LAYER A: frappe.session.user (if Frappe already bootstrapped)
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

    // LAYER B: Frappe cookies (set server-side for logged-in users)
    // Frappe sets `user_id` cookie to the logged-in user's email.
    // For guests it is absent or set to 'Guest'.
    function checkFrappeCookie() {
        var uid = getCookie('user_id') || getCookie('frappe_userid');
        if (uid && uid !== 'Guest' && uid.length > 0) return uid;
        // Also check `sid` — Frappe sets a non-Guest session ID when logged in
        var sid = getCookie('sid');
        if (sid && sid !== 'Guest' && sid.length > 10) return sid;
        return null;
    }

    // LAYER C: Synchronous XHR — ground truth, always accurate
    function checkViaXHR() {
        try {
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/method/frappe.auth.get_logged_user', false); // sync
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
            return null; // 403/401 = Guest
        } catch (e) {
            return null; // Deny on error
        }
    }

    // ── 5. Execute checks in order ────────────────────────────────────────────
    var user = checkFrappeSession() || checkFrappeCookie() || checkViaXHR();

    if (!user) {
        goToLogin();
        return; // Page stays frozen — redirect in flight
    }

    // Authenticated — reveal the page
    revealPage();
    document.addEventListener('DOMContentLoaded', revealPage);

})();


// ─────────────────────────────────────────────────────────────────────────────
// SECTION 0B: POST-LOGIN REDIRECT — Bounce user back after login
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

    // Poll for Frappe session becoming authenticated
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

    setTimeout(function () { clearInterval(poll); }, 900000); // 15 min safety
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
    $('head').append('<link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&display=swap" rel="stylesheet">');
    $('head').append('<link rel="stylesheet" href="/fle/css/login.css">');
    if ($('#fle-logout-style').length === 0) {
        $('head').append(`
        <style id="fle-logout-style">
            .sticky-header { background-color:#ffffff!important; box-shadow:0 2px 6px rgba(0,0,0,0.1)!important; }
            .sticky-header .header-top {
                display:flex!important; flex-direction:row!important; align-items:center!important;
                justify-content:space-between!important; width:100%!important;
                box-sizing:border-box!important; padding:10px 24px!important; background-color:#ffffff!important;
            }
            .sticky-header .logo-container { display:none!important; }
            .sticky-header .brand-text { flex:1 1 auto!important; text-align:center!important; padding:0 16px!important; }
            .breadcrumb, .page-breadcrumbs, .breadcrumb-container, .page-head, .navbar-user-icon, .avatar { display:none!important; visibility:hidden!important; }
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
            #fle-logout-modal h2 { font-size:18px; font-weight:700; color:#1a1a1a; margin:0 0 10px; }
            #fle-logout-modal p { font-size:13.5px; color:#555; line-height:1.65; margin:0 0 28px; font-weight:300; }
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
        </style>`);
    }

    const header_html = `
    <header class="sticky-header">
        <div class="header-top">
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

    const footer_html = `
    <footer class="sticky-footer">
        © 2026 National Law School of India University. All Rights Reserved.
    </footer>`;

    if ($('body').length === 0) return;
    $('body').prepend(header_html);
    $('body').append(footer_html);

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

    $(document).on('click', '#fle-logout-btn', function () { $('#fle-logout-modal-overlay').addClass('active'); });
    $(document).on('click', '#fle-modal-cancel', function () { $('#fle-logout-modal-overlay').removeClass('active'); });
    $(document).on('click', '#fle-logout-modal-overlay', function (e) {
        if ($(e.target).is('#fle-logout-modal-overlay')) $('#fle-logout-modal-overlay').removeClass('active');
    });
    $(document).on('keydown', function (e) { if (e.key === 'Escape') $('#fle-logout-modal-overlay').removeClass('active'); });
    $(document).on('click', '#fle-modal-confirm', function () {
        $(this).addClass('loading');
        $.ajax({ url: '/api/method/logout', type: 'GET', complete: function () { window.location.replace('/fle/login.html'); } });
    });

    $('html, body').css({ 'overflow-x': 'hidden', 'height': '100%', 'position': 'relative' });
    $('body').css({ 'display': 'flex', 'flex-direction': 'column', 'min-height': '100vh', 'margin': '0' });
    $('.web-form-page, .page-container').css('flex', '1 0 auto');
    $('.sticky-header').css({ 'position': 'fixed', 'top': '0', 'left': '0', 'z-index': '1020', 'width': '100%' });
    $('body').css('padding-top', '150px');
    $('.sticky-footer').css({ 'margin-top': 'auto', 'width': '100%' });

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
    }, 200);
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
    for (var i = 0; i < valid_routes.length; i++) {
        if (path.indexOf(valid_routes[i]) !== -1) {
            if (typeof inject_fle_header_footer === 'function') inject_fle_header_footer();
            break;
        }
    }
}

$(document).ready(try_inject_fle_theme);
$(window).on('load', try_inject_fle_theme);
document.addEventListener('DOMContentLoaded', try_inject_fle_theme);
if (typeof frappe !== 'undefined' && frappe.ready) { frappe.ready(try_inject_fle_theme); }
setTimeout(try_inject_fle_theme, 500);
setTimeout(try_inject_fle_theme, 1000);