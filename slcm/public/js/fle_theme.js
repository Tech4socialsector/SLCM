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
// SECTION 0C: UPDATE-PASSWORD REDIRECT
// Frappe's update-password.html passes statusCode:{200:…} to frappe.call,
// but frappe.call never forwards statusCode to jQuery — so the redirect
// handler is dead code.  This section patches frappe.call ON THE
// UPDATE-PASSWORD PAGE ONLY to add a proper callback that reads the
// redirect URL returned by update_password() and navigates to it.
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    'use strict';

    // Only activate on the update-password page
    var path = window.location.pathname;
    if (path.indexOf('update-password') === -1) return;

    function patchFrappeCall() {
        if (typeof frappe === 'undefined' || !frappe.call) return;
        if (frappe.call.__fle_pwd_patched) return;

        var _originalCall = frappe.call;
        frappe.call.__fle_pwd_patched = true;

        frappe.call = function (opts) {
            // Only intercept the update_password API call
            if (opts && opts.method &&
                opts.method.indexOf('update_password') !== -1 &&
                !opts.callback) {

                // Clone opts and add a proper callback
                var patchedOpts = Object.assign({}, opts);
                patchedOpts.callback = function (r) {
                    if (r && r.message) {
                        // r.message is the redirect URL returned by update_password()
                        var redirectUrl = r.message;

                        // Show success message
                        if (typeof frappe.msgprint === 'function') {
                            frappe.msgprint({
                                title: __('Password Updated'),
                                message: __('Your password has been set successfully. Redirecting…'),
                                indicator: 'green'
                            });
                        }

                        // Redirect after a short delay
                        setTimeout(function () {
                            window.location.href = redirectUrl;
                        }, 1500);
                    }
                };

                return _originalCall.call(this, patchedOpts);
            }

            // All other calls pass through unchanged
            return _originalCall.apply(this, arguments);
        };

        // Preserve any properties on the original frappe.call
        Object.keys(_originalCall).forEach(function (key) {
            if (!(key in frappe.call)) {
                frappe.call[key] = _originalCall[key];
            }
        });
    }

    // Patch at multiple lifecycle points to catch frappe.call being ready
    document.addEventListener('DOMContentLoaded', patchFrappeCall);
    window.addEventListener('load', patchFrappeCall);
    [0, 100, 300, 500, 1000].forEach(function (ms) {
        setTimeout(patchFrappeCall, ms);
    });
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
// SECTION 1B: LINKED DOCTYPE FIX — Master solution for all Link fields
// Fetches data from Frappe REST API and populates <select> dropdowns for
// Gender, Country, State (Candidate's State), and any other Link fields
// that render as empty selects in the web form.
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    'use strict';

    /**
     * Fetch all documents from a given doctype via the Frappe REST API.
     * Uses /api/resource/<doctype>?fields=["name"]&limit_page_length=500
     * Returns a Promise resolving to an array of name strings.
     */
    function fetchDoctypeOptions(doctype) {
        return new Promise(function (resolve) {
            try {
                var url = '/api/resource/' + encodeURIComponent(doctype) +
                    '?fields=["name"]&limit_page_length=500&order_by=name+asc';

                $.ajax({
                    url: url,
                    type: 'GET',
                    dataType: 'json',
                    xhrFields: { withCredentials: true },
                    success: function (data) {
                        if (data && data.data && Array.isArray(data.data)) {
                            resolve(data.data.map(function (d) { return d.name; }));
                        } else {
                            resolve([]);
                        }
                    },
                    error: function () { resolve([]); }
                });
            } catch (e) { resolve([]); }
        });
    }

    /**
     * Populate a <select> element with an array of option strings.
     * Preserves any currently selected value.
     * Skips if the select already has more than 1 option (already populated).
     */
    function populateSelect($select, options) {
        if (!$select || $select.length === 0) return;
        // If already has real options, don't overwrite
        if ($select.find('option').length > 1) return;

        var currentVal = $select.val() || '';
        $select.find('option:not([value=""])').remove();

        // Ensure blank placeholder exists
        if ($select.find('option[value=""]').length === 0) {
            $select.prepend('<option value=""></option>');
        }

        options.forEach(function (opt) {
            $select.append($('<option></option>').val(opt).text(opt));
        });

        // Restore previously selected value if it exists in the new list
        if (currentVal && options.indexOf(currentVal) !== -1) {
            $select.val(currentVal);
        }

        // Trigger Frappe's change detection so it registers the value
        $select.trigger('change');
    }

    /**
     * Map of fieldname keywords → Frappe doctype names.
     * Keys are lowercase substrings matched against the field's name/id/data-fieldname.
     */
    var LINK_FIELD_MAP = {
        'gender': 'Gender',
        'nationality': 'Country',
        'country': 'Country',
        'state': 'State'         // Frappe's built-in "State" doctype
    };

    /**
     * Find all select elements in the web form that correspond to linked
     * doctypes and populate them.
     */
    function populateAllLinkFields() {
        var path = window.location.pathname;
        // Only run on FLE web form pages
        if (path.indexOf('/foundations-for-a-legal-education') === -1 &&
            path.indexOf('/fle') === -1) return;

        // Collect unique doctypes we need to fetch
        var doctypesToFetch = {};

        $('select, .frappe-control[data-fieldtype="Link"] select').each(function () {
            var $sel = $(this);
            // Skip if already populated
            if ($sel.find('option').length > 1) return;

            // Try to identify the doctype from various attributes
            var fieldname = (
                $sel.attr('data-fieldname') ||
                $sel.closest('.frappe-control').attr('data-fieldname') ||
                $sel.attr('name') ||
                $sel.attr('id') ||
                ''
            ).toLowerCase();

            Object.keys(LINK_FIELD_MAP).forEach(function (keyword) {
                if (fieldname.indexOf(keyword) !== -1) {
                    doctypesToFetch[keyword] = LINK_FIELD_MAP[keyword];
                }
            });
        });

        // Also target by label text — more robust for Frappe web forms
        $('.frappe-control, .form-group').each(function () {
            var $ctrl = $(this);
            var labelText = ($ctrl.find('.control-label, label').first().text() || '').toLowerCase();
            var $sel = $ctrl.find('select');
            if ($sel.length === 0) return;
            if ($sel.find('option').length > 1) return;

            Object.keys(LINK_FIELD_MAP).forEach(function (keyword) {
                if (labelText.indexOf(keyword) !== -1) {
                    doctypesToFetch[keyword] = LINK_FIELD_MAP[keyword];
                }
            });
        });

        if (Object.keys(doctypesToFetch).length === 0) return;

        // Fetch all needed doctypes (deduplicated by doctype name)
        var fetchedDoctypes = {};
        var promises = [];

        Object.keys(doctypesToFetch).forEach(function (keyword) {
            var doctype = doctypesToFetch[keyword];
            if (!fetchedDoctypes[doctype]) {
                fetchedDoctypes[doctype] = true;
                promises.push(
                    fetchDoctypeOptions(doctype).then(function (options) {
                        return { doctype: doctype, keyword: keyword, options: options };
                    })
                );
            }
        });

        // Build a reverse map: doctype → options
        Promise.all(promises).then(function (results) {
            var doctypeOptions = {};
            results.forEach(function (r) {
                doctypeOptions[r.doctype] = r.options;
            });

            // Now populate each matching select
            $('select, .frappe-control[data-fieldtype="Link"] select').each(function () {
                var $sel = $(this);
                if ($sel.find('option').length > 1) return;

                var fieldname = (
                    $sel.attr('data-fieldname') ||
                    $sel.closest('.frappe-control').attr('data-fieldname') ||
                    $sel.attr('name') ||
                    $sel.attr('id') ||
                    ''
                ).toLowerCase();

                var $ctrl = $sel.closest('.frappe-control, .form-group');
                var labelText = ($ctrl.find('.control-label, label').first().text() || '').toLowerCase();
                var combinedText = fieldname + ' ' + labelText;

                Object.keys(LINK_FIELD_MAP).forEach(function (keyword) {
                    if (combinedText.indexOf(keyword) !== -1) {
                        var doctype = LINK_FIELD_MAP[keyword];
                        if (doctypeOptions[doctype] && doctypeOptions[doctype].length > 0) {
                            populateSelect($sel, doctypeOptions[doctype]);
                        }
                    }
                });
            });

            // Also handle Frappe's autocomplete/awesomplete link inputs (non-select)
            // These are <input> fields with data-fieldtype="Link"
            applyLinkInputAutocomplete(doctypeOptions);
        });
    }

    /**
     * For Frappe Link fields rendered as <input> (autocomplete style),
     * attach a datalist or override the search to use our fetched data.
     */
    function applyLinkInputAutocomplete(doctypeOptions) {
        $('.frappe-control[data-fieldtype="Link"]').each(function () {
            var $ctrl = $(this);
            var $input = $ctrl.find('input.input-with-feedback, input.form-control').first();
            if ($input.length === 0) return;

            var fieldname = ($ctrl.attr('data-fieldname') || '').toLowerCase();
            var labelText = ($ctrl.find('.control-label, label').first().text() || '').toLowerCase();
            var combinedText = fieldname + ' ' + labelText;

            Object.keys(LINK_FIELD_MAP).forEach(function (keyword) {
                if (combinedText.indexOf(keyword) !== -1) {
                    var doctype = LINK_FIELD_MAP[keyword];
                    var options = doctypeOptions[doctype];
                    if (!options || options.length === 0) return;

                    // Attach datalist for native browser autocomplete
                    var listId = 'fle-datalist-' + doctype.replace(/\s+/g, '-').toLowerCase();
                    if ($('#' + listId).length === 0) {
                        var $dl = $('<datalist></datalist>').attr('id', listId);
                        options.forEach(function (opt) {
                            $dl.append($('<option></option>').val(opt));
                        });
                        $('body').append($dl);
                    }
                    $input.attr('list', listId);

                    // Also override Frappe's get_query if available
                    try {
                        if (typeof frappe !== 'undefined' && frappe.web_form) {
                            // Patch the field's get_query to return local data
                            var fieldObj = frappe.web_form.fields_dict &&
                                frappe.web_form.fields_dict[fieldname];
                            if (fieldObj) {
                                fieldObj.get_query = function () {
                                    return { filters: [] };
                                };
                            }
                        }
                    } catch (e) { /* silent */ }
                }
            });
        });
    }

    /**
     * Override Frappe's Link field search (awesomplete / frappe.utils.search_link)
     * to always query via REST when the standard query fails or returns empty.
     */
    function patchFrappeLinkSearch() {
        if (typeof frappe === 'undefined') return;

        // Patch frappe.utils.search_link if it exists
        var _origSearchLink = frappe.utils && frappe.utils.search_link;
        if (_origSearchLink && !frappe.utils._fle_patched) {
            frappe.utils._fle_patched = true;
            frappe.utils.search_link = function (opts) {
                // Call original first
                try { _origSearchLink.call(frappe.utils, opts); } catch (e) { }

                // If the doctype is one of ours and the results are empty, supplement
                var doctype = opts && opts.doctype;
                if (!doctype) return;

                var doctypeLower = doctype.toLowerCase();
                var isOurs = ['gender', 'country', 'state'].some(function (k) {
                    return doctypeLower.indexOf(k) !== -1;
                });
                if (!isOurs) return;

                fetchDoctypeOptions(doctype).then(function (options) {
                    if (!options || options.length === 0) return;
                    var txt = (opts.txt || '').toLowerCase();
                    var filtered = txt
                        ? options.filter(function (o) { return o.toLowerCase().indexOf(txt) !== -1; })
                        : options;

                    if (filtered.length > 0 && opts.callback) {
                        opts.callback({ results: filtered.map(function (o) { return { value: o, description: '' }; }) });
                    }
                });
            };
        }
    }

    /**
     * Master init — runs at multiple lifecycle points to ensure fields
     * are populated regardless of when Frappe finishes rendering the form.
     */
    function fle_init_link_fields() {
        patchFrappeLinkSearch();
        populateAllLinkFields();
    }

    // Run at all Frappe + DOM lifecycle events
    $(document).ready(fle_init_link_fields);
    $(window).on('load', fle_init_link_fields);
    document.addEventListener('DOMContentLoaded', fle_init_link_fields);

    // Frappe-specific events
    ['frappe:ready', 'page-change', 'page-load', 'after-ajax', 'web-form-load'].forEach(function (evt) {
        document.addEventListener(evt, fle_init_link_fields);
    });

    // Delayed retries — Frappe often renders fields asynchronously
    [300, 800, 1500, 2500, 4000].forEach(function (ms) {
        setTimeout(fle_init_link_fields, ms);
    });

    // MutationObserver: watch for new select elements being added by Frappe
    var _linkObserver = null;
    function startLinkObserver() {
        if (_linkObserver) return;
        _linkObserver = new MutationObserver(function (mutations) {
            var hasNewSelects = mutations.some(function (m) {
                return Array.prototype.some.call(m.addedNodes, function (node) {
                    if (node.nodeType !== 1) return false;
                    return node.tagName === 'SELECT' ||
                        (node.querySelector && node.querySelector('select')) !== null;
                });
            });
            if (hasNewSelects) {
                setTimeout(populateAllLinkFields, 50);
            }
        });
        _linkObserver.observe(document.body || document.documentElement, {
            childList: true,
            subtree: true
        });
        // Stop observing after 30 seconds to avoid memory leaks
        setTimeout(function () {
            if (_linkObserver) { _linkObserver.disconnect(); _linkObserver = null; }
        }, 30000);
    }

    document.addEventListener('DOMContentLoaded', startLinkObserver);
    if (document.body) startLinkObserver();

})();


// ─────────────────────────────────────────────────────────────────────────────
// SECTION 2: HEADER + FOOTER INJECTION (non-login pages)
// ─────────────────────────────────────────────────────────────────────────────
window.inject_fle_header_footer = function () {
    if ($('.sticky-header').length > 0) return;

    // ── 0. Global CSS refinement for FLE ──────────────────────────────────────
    // Hide web form title on /new pages immediately (JS will update once doc loads)
    if (window.location.pathname.indexOf('/new') !== -1) {
        $('head').append('<style id="fle-new-form-title-hide">.web-form-title h1, .web-form-header h1 { display: none !important; }</style>');
    }

    if ($('#fle-global-refinements').length === 0) {
        $('head').append(`
        <style id="fle-global-refinements">
            /* Ensure web form content is not hidden behind the fixed header */
            .web-form-container { padding-top: 0 !important; margin-top: 0 !important; }
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

            .frappe-control,
            .form-group {
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .web-form-page input,
            .web-form-page select,
            .web-form-page textarea,
            .web-form-page label,
            .web-form-page .control-label,
            .web-form-wrapper input,
            .web-form-wrapper select,
            .web-form-wrapper textarea,
            .web-form-wrapper label,
            .web-form-wrapper .control-label,
            .web-form-wrapper .help-box,
            .web-form-wrapper .form-text,
            .web-form-wrapper .form-control {
                font-family: 'Merriweather', Georgia, serif !important;
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

                letter-spacing: 0.2px !important;
                font-size: 13px !important;
                font-weight: 400 !important;
                color: #444444 !important;
                font-family: 'Merriweather', Georgia, serif !important;
            }

            .web-form-header {
  margin-top: 155px;
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

            .control-label, label.control-label, .web-form-page label,
            .web-form-wrapper label, .frappe-control label, .form-group label {
                text-transform: none !important;
                margin-bottom: 8px !important;
                display: block !important;
                font-size: 13px !important;
                font-weight: 600 !important;
                color: #333 !important;
            }
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
                font-size:23px !important; font-weight:700 !important; color:#8B0000 !important;
                margin:0 0 4px !important; letter-spacing:0.5px !important;
            }
            .sticky-header .brand-text .department-name {
                font-family:'Merriweather', Georgia, serif !important;
                font-size:21px !important; font-weight:700 !important; color:#8B0000 !important;
                margin:0 !important; letter-spacing:0.2px !important;
            }
            .department-name-bar {
                background-color:#ffffff !important; text-align:center !important;
                padding:10px 16px !important; width:100% !important;
            }
            .department-name-bar .department-name {
                color:#8B0000 !important;
            }
            .breadcrumb, .page-breadcrumbs, .breadcrumb-container,
            .page-head .breadcrumb-container, .page-head .page-breadcrumbs,
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
            .fle-modal-btn-confirm { background:#8B0000 !important; color:#ffffff !important; box-shadow:0 2px 6px rgba(139,0,0,0.3); }
            .fle-modal-btn-confirm:hover { background:#6a0000 !important; color:#ffffff !important; transform:translateY(-1px); box-shadow:0 4px 12px rgba(139,0,0,0.4); }
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
                font-family:'Merriweather',Georgia,serif!important; min-height:14px!important;
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

            /* ── Mobile responsive styles ── */
            @media (max-width: 600px) {
                .sticky-header .header-top {
                    padding: 5px 8px !important;
                    flex-wrap: nowrap !important;
                }
                .sticky-header .logo-img {
                    height: 38px !important;
                    max-width: 38px !important;
                }
                .sticky-header .logo-container {
                    margin-right: 6px !important;
                    flex-shrink: 0 !important;
                }
                .sticky-header .brand-text {
                    padding: 0 4px !important;
                    min-width: 0 !important;
                }
                .sticky-header .brand-text .university-name {
                    font-size: 11px !important;
                    letter-spacing: 0px !important;
                    margin: 0 0 2px !important;
                }
                .sticky-header .brand-text .department-name {
                    font-size: 10px !important;
                    letter-spacing: 0px !important;
                }
                .sticky-header .header-logout-area {
                    min-width: auto !important;
                    flex-shrink: 0 !important;
                }
                button.fle-logout-btn {
                    padding: 5px 8px !important;
                    font-size: 10px !important;
                    letter-spacing: 0.2px !important;
                    gap: 3px !important;
                }
                button.fle-logout-btn svg {
                    width: 11px !important;
                    height: 11px !important;
                }
                .navbar-navy .nav-item {
                    padding: 8px 10px !important;
                    font-size: 10px !important;
                    letter-spacing: 0.3px !important;
                }
            }

            @media (max-width: 400px) {
                .sticky-header .header-top {
                    padding: 4px 6px !important;
                }
                .sticky-header .logo-img {
                    height: 32px !important;
                    max-width: 32px !important;
                }
                .sticky-header .logo-container {
                    margin-right: 5px !important;
                }
                .sticky-header .brand-text .university-name {
                    font-size: 9.5px !important;
                }
                .sticky-header .brand-text .department-name {
                    font-size: 9px !important;
                }
                button.fle-logout-btn {
                    padding: 4px 7px !important;
                    font-size: 9.5px !important;
                    gap: 3px !important;
                }
                button.fle-logout-btn svg {
                    width: 10px !important;
                    height: 10px !important;
                }
            }
        </style>`);
    }

    // ── 4. Inject Header HTML ─────────────────────────────────────────────────
    var header_html = `
    <header class="sticky-header">
        <div class="header-top">
            <div class="logo-container">
                <a href="https://pace.nls.ac.in/" target="_blank" rel="noopener noreferrer">
                    <img src="/files/nlsiu-logo.jpg" alt="NLSIU Logo" class="logo-img"
                         onerror="this.onerror=null; this.style.display='none';">
                </a>
            </div>
            <div class="brand-text">
                <h1 class="university-name">National Law School of India University, Bengaluru</h1>
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
        <nav class="navbar-navy" aria-label="Main navigation"></nav>
        <div class="department-name page-department-name fle-page-title">Foundations for a Legal Education Certificate Course (FLE)</div>
    </header>`;

    // ── 5. Inject Footer HTML ─────────────────────────────────────────────────
    var footer_html = `
    <footer class="sticky-footer">
        &copy; 2026 National Law School of India University, Bengaluru
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
    function updateBodyPaddingTop() {
        var hdr = document.querySelector('.sticky-header');
        if (hdr) $('body').css('padding-top', hdr.offsetHeight + 'px');
    }
    updateBodyPaddingTop();
    $(window).on('resize', updateBodyPaddingTop);
    [100, 300, 600, 800, 1200, 1800, 2500].forEach(function(ms) {
        setTimeout(updateBodyPaddingTop, ms);
    });
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
            el.style.setProperty('text-transform', 'none', 'important');
            el.style.setProperty('letter-spacing', '0.2px', 'important');
            el.style.setProperty('margin-bottom', '8px', 'important');
            el.style.setProperty('font-size', '13px', 'important');
            el.style.setProperty('font-weight', '600', 'important');
            el.style.setProperty('color', '#333', 'important');
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
            el.style.setProperty('text-transform', 'none', 'important');
            el.style.setProperty('letter-spacing', '0.2px', 'important');
            el.style.setProperty('margin-bottom', '8px', 'important');
            el.style.setProperty('font-size', '13px', 'important');
            el.style.setProperty('font-weight', '600', 'important');
            el.style.setProperty('color', '#333', 'important');
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

window.check_payment_status_buttons = function () {
    var path = window.location.pathname;
    if (path.indexOf('/foundations-for-a-legal-education') === -1) return;

    // Prevent multiple simultaneous intervals from running
    if (window._fle_payment_check_running) return;
    window._fle_payment_check_running = true;

    // Immediately remove any persisted title-hide CSS from /new page visits
    $('#fle-new-form-title-hide').remove();

    // Always hide the Edit button — page defaults to edit mode until payment is authorized
    if ($('#fle-hide-edit-btn-style').length === 0) {
        $('head').append('<style id="fle-hide-edit-btn-style">.edit-button { display: none !important; visibility: hidden !important; }</style>');
    }

    var checks = 0;
    var maxChecks = 40; // Max 20 seconds

    var interval = setInterval(function () {
        checks++;
        if (typeof frappe !== 'undefined' && frappe.web_form && frappe.web_form.doc && frappe.web_form.doc.name) {
            clearInterval(interval);

            // Show document ID in the title area (hide the long web form title)
            var docName = frappe.web_form.doc.name;
            var isRealDoc = docName && docName.indexOf('new-') === -1;
            var $titleH1 = $('.web-form-title h1, .web-form-header h1').first();

            if (isRealDoc) {
                // Remove any persisted hide CSS and make visible
                $('#fle-new-form-title-hide').remove();
                if ($titleH1.length > 0) {
                    $titleH1[0].style.removeProperty('display');
                    $titleH1.show().text('Application number:' + docName);
                } else {
                    // Fallback: insert a dedicated ID display if h1 isn't found
                    if ($('#fle-doc-id-display').length === 0) {
                        var $idDisplay = $('<div id="fle-doc-id-display" style="text-align:left; padding:8px 0 4px; font-family:Merriweather,Georgia,serif; font-weight:700; font-size:1.8em; color:#1a1a1a; margin-bottom:8px;">Application number:' + docName + '</div>');
                        $('.web-form-wrapper, .web-form-container, .page-content').first().prepend($idDisplay);
                    }
                }
            } else if ($titleH1.length > 0) {
                $titleH1.hide();
            }

            // Only show payment/PDF controls for an existing (saved) submission
            if (isRealDoc) {
                frappe.call({
                    method: 'slcm.api.user.get_payment_status',
                    args: {
                        docname: frappe.web_form.doc.name
                    },
                    callback: function (r) {
                        if (r && r.message) {
                            const status = r.message.payment_status;
                            if (status !== 'Authorized' && status !== 'Captured') {
                                // Payment not yet done: auto-enter edit mode
                                function triggerEditMode() {
                                    var editBtn = $('.edit-button');
                                    if (editBtn.length > 0) {
                                        editBtn[0].click();
                                    }
                                }
                                triggerEditMode();
                                setTimeout(triggerEditMode, 500);
                                setTimeout(triggerEditMode, 1500);
                            }
                            if (status === 'Authorized' || status === 'Captured') {
                                // Inject CSS to forcefully hide standard frappe action buttons
                                if ($('#fle-hide-btn-style').length === 0) {
                                    const styleBlock = `
                                        <style id="fle-hide-btn-style">
                                            .submit-btn, .discard-btn, .delete-btn,
                                            .web-form-actions .btn:not(.download-pdf-btn),
                                            .web-form-footer .btn:not(.download-pdf-btn) {
                                                display: none !important;
                                                visibility: hidden !important;
                                            }
                                        </style>
                                    `;
                                    $('head').append(styleBlock);
                                }

                                // Also hide directly via jQuery (belt-and-suspenders)
                                function hideActionButtons() {
                                    $('.submit-btn, .discard-btn, .delete-btn').hide();
                                    $('.web-form-footer .btn:not(.download-pdf-btn)').hide();
                                }
                                hideActionButtons();
                                setTimeout(hideActionButtons, 500);
                                setTimeout(hideActionButtons, 1500);

                                // Download Receipt button — hidden until enabled
                                /* ENABLE WHEN READY:
                                if ($('.download-pdf-btn').length === 0) {
                                    const docname = frappe.web_form.doc.name;
                                    window._fle_download_receipt = function () {
                                        const url = `/api/method/slcm.api.user.download_fle_receipt?docname=${encodeURIComponent(docname)}`;
                                        fetch(url, { method: 'GET', credentials: 'same-origin' })
                                            .then(function (res) {
                                                if (!res.ok) { frappe.msgprint(__('Failed to download receipt. Please try again.')); return null; }
                                                return res.blob();
                                            })
                                            .then(function (blob) {
                                                if (!blob) return;
                                                var blobUrl = URL.createObjectURL(blob);
                                                var a = document.createElement('a');
                                                a.href = blobUrl;
                                                a.download = 'FLE_Receipt_' + docname + '.pdf';
                                                document.body.appendChild(a);
                                                a.click();
                                                document.body.removeChild(a);
                                                URL.revokeObjectURL(blobUrl);
                                            })
                                            .catch(function () { frappe.msgprint(__('Failed to download receipt. Please try again.')); });
                                    };
                                    const pdf_btn = `<a href="#" onclick="window._fle_download_receipt(); return false;" class="btn btn-primary btn-sm ml-2 download-pdf-btn" style="background-color: #8B0000; color: #ffffff; border: none !important; display: inline-block !important;">Download Receipt</a>`;
                                    if ($('.web-form-footer .right-area').length > 0) {
                                        $('.web-form-footer .right-area').append(pdf_btn);
                                    } else {
                                        $('.web-form-footer').append(pdf_btn);
                                    }
                                }
                                */
                            }
                        }
                    }
                });
            }
        } else if (checks >= maxChecks) {
            clearInterval(interval);
            window._fle_payment_check_running = false;
        }
    }, 500);
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
                if (typeof check_payment_status_buttons === 'function') check_payment_status_buttons();
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

// ─────────────────────────────────────────────────────────────────────────────
// SECTION: Hide "Not Saved" indicator on FLE web form pages
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    var path = window.location.pathname;
    if (path.indexOf('/foundations-for-a-legal-education') === -1) return;

    var style = document.createElement('style');
    style.textContent = '.indicator-pill.orange { display: none !important; }';
    document.head.appendChild(style);
})();

// ─────────────────────────────────────────────────────────────────────────────
// SECTION: Set India (+91) as default for candidate contact number
// Frappe v16 uses its own ControlPhone (not intl-tel-input).
// set_default_country() is skipped when a value is already present (URL param),
// so we poll until the control is ready and apply India manually.
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    var path = window.location.pathname;
    if (path.indexOf('/foundations-for-a-legal-education') === -1) return;

    function setIndiaDefault(attempts) {
        attempts = attempts || 0;
        if (!window.frappe || !frappe.web_form) {
            if (attempts < 30) setTimeout(function () { setIndiaDefault(attempts + 1); }, 200);
            return;
        }
        var fd = frappe.web_form.fields_dict;
        var field = fd && fd['candidate_contact_number'];
        if (field && field.country_code_picker && field.country_codes && field.$isd) {
            if (!field.$isd.text().trim()) {
                field.country_code_picker.on_change('India', false);
            }
        } else if (attempts < 30) {
            setTimeout(function () { setIndiaDefault(attempts + 1); }, 200);
        }
    }

    document.addEventListener('DOMContentLoaded', function () { setIndiaDefault(); });
    setTimeout(function () { setIndiaDefault(); }, 800);
})();