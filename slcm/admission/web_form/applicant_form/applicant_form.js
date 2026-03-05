frappe.ready(function() {
    // 1. Navbar Injection (Replicate admission_base.html exactly)
    function injectPortalNav() {
        if (document.getElementById('portal-nav-injected')) return;

        // Fetch context data passed from Python
        var pc = frappe.web_form.context.portal_config || {};
        var ws = frappe.web_form.context.website_settings || {};
        var user = frappe.session.user;
        var title = pc.portal_title || ws.title || "Admissions";
        var logo = ws.banner_image ? `<img src="${ws.banner_image}" alt="Logo" style="height:36px;width:auto;">` : "";

        var linksHtml = `
            <a href="/admission" class="nav-hide-mobile">Programs</a>
            ${user !== "Guest" ? `
                <a href="/my-applications" class="nav-hide-mobile">My Applications</a>
                <a href="/eligibility/entrance_test_seat_allocation" class="nav-hide-mobile">Entrance Test</a>
                <a href="/eligibility/interview_management" class="nav-hide-mobile">Interview</a>
                <a href="/offer_letter/offer-letter-list" class="nav-hide-mobile">Offer Letter</a>
            ` : ""}
        `;

        var drawerLinksHtml = `
            <a href="/admission" class="drawer-link">Programs</a>
            ${user !== "Guest" ? `
                <a href="/my-applications" class="drawer-link">My Applications</a>
                <a href="/offer_letter/offer-letter-list" class="drawer-link">Offer Letter</a>
            ` : ""}
        `;

        var navbarHtml = `
            <nav class="adm-nav" id="portal-nav-injected">
                <a href="/admission" class="adm-nav-brand">
                    ${logo} <span>${title}</span>
                </a>
                <div class="adm-nav-links">
                    ${linksHtml}
                    <a href="/login" class="nav-btn nav-logout-btn">${user === "Guest" ? "Login / Apply" : "Logout"}</a>
                </div>
                <button class="nav-hamburger" id="nav-hamburger" aria-label="Open menu" aria-expanded="false">
                    <span class="ham-line"></span>
                    <span class="ham-line"></span>
                    <span class="ham-line"></span>
                </button>
            </nav>
            <div class="mobile-drawer" id="mobile-drawer" aria-hidden="true">
                ${drawerLinksHtml}
                <div class="drawer-divider"></div>
                <a href="/login" class="drawer-link">${user === "Guest" ? "Login" : "Logout"}</a>
            </div>
            <div class="drawer-overlay" id="drawer-overlay"></div>
        `;

        var header = document.createElement('div');
        header.innerHTML = navbarHtml;
        document.body.insertBefore(header, document.body.firstChild);

        // Wire hamburger
        var btn = document.getElementById('nav-hamburger');
        var drawer = document.getElementById('mobile-drawer');
        var overlay = document.getElementById('drawer-overlay');

        if (btn) {
            btn.onclick = function() {
                var isOpen = drawer.classList.toggle('open');
                btn.classList.toggle('open');
                overlay.classList.toggle('open');
                document.body.style.overflow = isOpen ? 'hidden' : '';
            };
        }
        if (overlay) {
            overlay.onclick = function() {
                drawer.classList.remove('open');
                btn.classList.remove('open');
                overlay.classList.remove('open');
                document.body.style.overflow = '';
            };
        }
    }

    // 2. Stage Tracker Logic
    function initTracker() {
        var applicantName = frappe.web_form_doc.name;
        if (!applicantName || applicantName === 'new') return;

        // Create container if not exists
        if (!document.getElementById('stage-tracker-wrap')) {
            var container = document.createElement('div');
            container.id = 'stage-tracker-wrap';
            container.style.cssText = "background:#fff;border-radius:16px;padding:24px;margin-bottom:32px;box-shadow:0 4px 20px rgba(0,0,0,0.08);";
            
            var form = document.querySelector('.web-form-container');
            if (form) form.parentNode.insertBefore(container, form);
        }

        // Load & Init Widget
        frappe.require('/assets/slcm/js/stage_tracker.js', function() {
            frappe.require('/assets/slcm/css/stage_tracker.css', function() {
                if (window.StageTracker) {
                    StageTracker.init({
                        container: '#stage-tracker-wrap',
                        applicant: applicantName,
                        mode: 'full',
                        csrf: frappe.csrf_token
                    });
                }
            });
        });
    }

    // 3. Spacing Fix
    function fixSpacing() {
        $('.page-content').css({
            'padding-top': '0',
            'margin-top': '0'
        });
        $('.main-section').css('padding-top', '0');
    }

    // Execution
    injectPortalNav();
    initTracker();
    fixSpacing();
    
    // Retry tracker injection if form was slow to render
    setTimeout(initTracker, 1000);
});
