/**
 * Global Javascript functions for Foundations for Legal Education UI
 */

window.inject_fle_header_footer = function () {
    // Only inject if not already present to prevent duplicate headers on rapid reloads
    if ($('.sticky-header').length > 0) return;

    $('head').append('<link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&display=swap" rel="stylesheet">');
    $('head').append('<link rel="stylesheet" href="/fle/css/login.css">');

    // Inject all styles FIRST before any HTML is added to the DOM
    if ($('#fle-logout-style').length === 0) {
        $('head').append(`
        <style id="fle-logout-style">
            /* ── Header Top Row ── */
            .sticky-header {
                background-color: #ffffff !important;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
            }

            .sticky-header .header-top {
                display: flex !important;
                flex-direction: row !important;
                align-items: center !important;
                justify-content: space-between !important;
                width: 100% !important;
                box-sizing: border-box !important;
                padding: 10px 24px !important;
                background-color: #ffffff !important;
            }

            .sticky-header .logo-container {
                flex: 0 0 auto !important;
                display: flex !important;
                align-items: center !important;
            }

            .sticky-header .brand-text {
                flex: 1 1 auto !important;
                text-align: center !important;
                padding: 0 16px !important;
            }

            /* ── Logout Button Wrapper ── */
            .sticky-header .header-logout-area {
                flex: 0 0 auto !important;
                display: flex !important;
                align-items: center !important;
                justify-content: flex-end !important;
                min-width: 130px !important;
            }

            /* ── Logout Button ── */
            button.fle-logout-btn {
                all: unset !important;
                box-sizing: border-box !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 7px !important;
                background-color: #8B0000 !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 5px !important;
                padding: 8px 18px !important;
                font-size: 13px !important;
                font-family: 'Merriweather', Georgia, serif !important;
                font-weight: 700 !important;
                cursor: pointer !important;
                letter-spacing: 0.6px !important;
                text-transform: uppercase !important;
                white-space: nowrap !important;
                visibility: visible !important;
                opacity: 1 !important;
                pointer-events: auto !important;
                transition: background-color 0.2s ease, transform 0.1s ease !important;
                box-shadow: 0 2px 5px rgba(139,0,0,0.35) !important;
                position: relative !important;
                z-index: 9999 !important;
            }

            button.fle-logout-btn:hover {
                background-color: #6a0000 !important;
                transform: translateY(-1px) !important;
                box-shadow: 0 4px 10px rgba(139,0,0,0.45) !important;
                color: #ffffff !important;
            }

            button.fle-logout-btn:active {
                transform: translateY(0px) !important;
                background-color: #5a0000 !important;
            }

            button.fle-logout-btn svg {
                display: inline-block !important;
                flex-shrink: 0 !important;
                vertical-align: middle !important;
            }
        </style>
        `);
    }

    const header_html = `
    <header class="sticky-header">
        <div class="header-top">
            <div class="logo-container">
                <img src="/files/nlsiu-logo.jpg" alt="Logo" class="logo-img">
            </div>
            <div class="brand-text">
                <h5 class="university-name">National Law School of India University, Bengaluru</h5>
                <h1 class="department-name">Foundations for a Legal Education Certificate Course</h1>
            </div>
            <div class="header-logout-area">
                <button class="fle-logout-btn" id="fle-logout-btn" type="button">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                         fill="none" stroke="#ffffff" stroke-width="2.5"
                         stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                    Logout
                </button>
            </div>
        </div>
        <nav class="navbar-navy">
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" data-tab="courses" class="nav-item" target="_blank">OVERVIEW</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">COURSES</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FACULTY</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FEE</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FAQs</a>
            <a href="https://pace.nls.ac.in/contact-us/" class="nav-item">Contact Us</a>
        </nav>
    </header>
    `;

    const footer_html = `
    <footer class="sticky-footer">
        © 2026 National Law School of India University. All Rights Reserved.
    </footer>
    `;

    // Make sure that the DOM body actually exists before prepending
    if ($('body').length === 0) return;

    $('body').prepend(header_html);
    $('body').append(footer_html);

    // Bind logout click via JS (avoids inline onclick conflicts with Frappe CSP)
    $(document).on('click', '#fle-logout-btn', function (e) {
        e.preventDefault();
        frappe.confirm(
            'Are you sure you want to logout?',
            () => {
                frappe.call({
                    method: 'logout',
                    callback: function (r) {
                        window.location.href = '/fle/login.html';
                    }
                });
            }
        );
    });

    // Add specific fixes for positioning in Web Forms
    $('html, body').css({
        'overflow-x': 'hidden',
        'height': '100%',
        'position': 'relative'
    });

    // Ensure the middle content expands to push footer down
    $('body').css({
        'display': 'flex',
        'flex-direction': 'column',
        'min-height': '100vh',
        'margin': '0'
    });

    $('.web-form-page, .page-container').css('flex', '1 0 auto');

    // Fix z-index and top positioning specifically for frappe DOM
    $('.sticky-header').css({
        'position': 'fixed',
        'top': '0',
        'left': '0',
        'z-index': '1020',
        'width': '100%'
    });

    $('body').css('padding-top', '150px');

    // Ensure the footer is sticky at the very bottom
    $('.sticky-footer').css({
        'margin-top': 'auto',
        'width': '100%'
    });

    // Final safety enforcement after DOM settles
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
            btn.style.setProperty('position', 'relative', 'important');
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

// Automatically run injection on specific Frappe routes
function try_inject_fle_theme() {
    var path = window.location.pathname;
    var valid_routes = [
        '/payment-success',
        '/payment-failed',
        '/payment-cancel',
        '/fle-success-page',
        '/integration-request',
        '/foundations-for-a-legal-education'
    ];

    for (var i = 0; i < valid_routes.length; i++) {
        if (path.includes(valid_routes[i])) {
            if (typeof inject_fle_header_footer === 'function') {
                inject_fle_header_footer();
            }
            break;
        }
    }
}

// Frappe dynamic page loads can be incredibly unpredictable with standard jQuery ready events.
// We bind to multiple document lifecycle events to guarantee this fires.
$(document).ready(try_inject_fle_theme);
$(window).on('load', try_inject_fle_theme);
document.addEventListener('DOMContentLoaded', try_inject_fle_theme);
if (typeof frappe !== 'undefined' && frappe.ready) {
    frappe.ready(try_inject_fle_theme);
}
// Absolute safety fallback in case all standard bindings are suppressed
setTimeout(try_inject_fle_theme, 500);
setTimeout(try_inject_fle_theme, 1000);