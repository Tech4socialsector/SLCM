/**
 * Global Javascript functions for Foundations for Legal Education UI
 */

window.inject_fle_header_footer = function () {
    // Only inject if not already present to prevent duplicate headers on rapid reloads
    if ($('.sticky-header').length > 0) return;

    $('head').append('<link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&display=swap" rel="stylesheet">');
    $('head').append('<link rel="stylesheet" href="/fle/css/login.css">');

    const header_html = `
    <header class="sticky-header">
        <div class="header-top" style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center;">
                <div class="logo-container">
                    <img src="/files/nlsiu-logo.jpg" alt="Logo" class="logo-img">
                </div>
                <div class="brand-text">
                    <h5 class="university-name">National Law School of India University, Bengaluru</h5>
                    <h1 class="department-name">Foundations for a Legal Education Certificate Course</h1>
                </div>
            </div>
        </div>
        <nav class="navbar-navy">
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item" target="_blank">OVERVIEW</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">COURSES</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FACULTY</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FEE</a>
            <a href="https://pace.nls.ac.in/programmes/foundations-for-a-legal-education/" class="nav-item">FAQs</a>
            <a href="https://pace.nls.ac.in/contact-us/" class="nav-item">CONTACT US</a>
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

    // Check if current URL matches any of the routes
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
