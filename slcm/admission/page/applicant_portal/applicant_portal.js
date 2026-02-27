frappe.pages['applicant-portal'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Applicant Portal',
        single_column: true
    });

    const $body = $(wrapper).find('.layout-main-section');

    const state = {
        config: null,
        programs: [],
        media: {},           // program -> array of media
        heroMedia: [],       // featured media for banner
        announcements: [],
        heroIndex: 0,
        selected_program: null,
        selected_campuses: [],
        applicant: null,
        form: null,
        form_data: {},
        current_tab: 0,
        tabs: []
    };

    // ── THEME ────────────────────────────────────────────────────
    function applyTheme(primary, secondary) {
        const existing = document.getElementById('portal-theme');
        if (existing) existing.remove();
        const style = document.createElement('style');
        style.id = 'portal-theme';
        style.textContent = `
            :root {
                --portal-primary: ${primary || '#1a237e'};
                --portal-secondary: ${secondary || '#ffffff'};
                --portal-light: ${primary || '#1a237e'}18;
            }
            /* Hero Carousel */
            .portal-hero-carousel {
                position: relative;
                width: 100%;
                height: 320px;
                overflow: hidden;
                border-radius: var(--border-radius-lg);
                margin-bottom: 20px;
                background: var(--portal-primary);
            }
            .hero-slide {
                position: absolute;
                inset: 0;
                opacity: 0;
                transition: opacity 0.6s ease;
                background-size: cover;
                background-position: center;
            }
            .hero-slide.active { opacity: 1; }
            .hero-slide-overlay {
                position: absolute;
                bottom: 0; left: 0; right: 0;
                background: linear-gradient(transparent, rgba(0,0,0,0.65));
                padding: 24px 28px;
                color: #fff;
            }
            .hero-slide-title { font-size: 22px; font-weight: 700; margin: 0; }
            .hero-slide-caption { font-size: 14px; opacity: 0.85; margin: 4px 0 0; }
            .hero-dots {
                position: absolute;
                bottom: 14px; right: 16px;
                display: flex; gap: 6px;
            }
            .hero-dot {
                width: 8px; height: 8px; border-radius: 50%;
                background: rgba(255,255,255,0.5); cursor: pointer;
                transition: background 0.2s;
            }
            .hero-dot.active { background: #fff; }
            .hero-fallback {
                display: flex; align-items: center; justify-content: center;
                height: 100%; color: #fff; flex-direction: column; gap: 8px;
            }
            /* Program Cards */
            .portal-program-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 16px; margin-top: 16px;
            }
            .portal-program-list { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
            .portal-program-card {
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                overflow: hidden;
                background: var(--card-bg);
                transition: box-shadow 0.2s, border-color 0.2s;
            }
            .portal-program-card:hover {
                box-shadow: var(--shadow-md);
                border-color: var(--portal-primary);
            }
            .card-media-area {
                position: relative;
                height: 160px;
                background: var(--portal-light);
                overflow: hidden;
            }
            .card-media-area img {
                width: 100%; height: 100%; object-fit: cover;
            }
            .card-media-nav {
                position: absolute; top: 50%; transform: translateY(-50%);
                background: rgba(0,0,0,0.4); color: #fff;
                border: none; border-radius: 4px;
                padding: 4px 8px; cursor: pointer; font-size: 16px;
            }
            .card-media-nav.prev { left: 6px; }
            .card-media-nav.next { right: 6px; }
            .card-media-badges {
                position: absolute; bottom: 6px; right: 6px;
                display: flex; gap: 4px;
            }
            .card-body { padding: 16px; }
            .card-program-name {
                font-weight: 700; font-size: 15px;
                color: var(--portal-primary); margin-bottom: 4px;
            }
            .card-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
            /* Announcements */
            .portal-announcements { margin: 24px 0; }
            .announcement-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 14px; margin-top: 12px;
            }
            .ann-card {
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                overflow: hidden;
                background: var(--card-bg);
                cursor: pointer;
                transition: box-shadow 0.2s;
            }
            .ann-card:hover { box-shadow: var(--shadow-md); }
            .ann-card-img { width: 100%; height: 120px; object-fit: cover; }
            .ann-card-img-placeholder {
                width: 100%; height: 120px;
                background: var(--portal-light);
                display: flex; align-items: center; justify-content: center;
                color: var(--portal-primary); font-size: 28px;
            }
            .ann-card-body { padding: 12px; }
            .ann-type-badge {
                display: inline-block;
                font-size: 10px; font-weight: 700;
                padding: 2px 8px; border-radius: 10px;
                text-transform: uppercase; margin-bottom: 6px;
            }
            .ann-type-badge.event { background: #e3f2fd; color: #1565c0; }
            .ann-type-badge.announcement { background: var(--portal-light); color: var(--portal-primary); }
            .ann-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
            .ann-summary { font-size: 12px; color: var(--text-muted); }
            .ann-countdown {
                margin-top: 8px; font-size: 11px; font-weight: 600;
                color: #e65100; background: #fff3e0;
                padding: 3px 8px; border-radius: 4px; display: inline-block;
            }
            /* Bell icon */
            .portal-bell-btn {
                position: relative;
                background: none; border: none;
                cursor: pointer; padding: 4px 8px;
                color: var(--portal-primary);
                font-size: 16px;
            }
            .portal-bell-badge {
                position: absolute; top: -2px; right: -2px;
                background: var(--red); color: #fff;
                border-radius: 8px; font-size: 9px;
                padding: 1px 4px; font-weight: 700;
                min-width: 14px; text-align: center;
            }
            /* Side Drawer */
            .portal-drawer-backdrop {
                position: fixed; inset: 0;
                background: rgba(0,0,0,0.45);
                z-index: 1040;
            }
            .portal-drawer {
                position: fixed; top: 0; right: 0;
                width: min(520px, 95vw); height: 100%;
                background: var(--card-bg);
                box-shadow: -4px 0 24px rgba(0,0,0,0.18);
                z-index: 1050;
                display: flex; flex-direction: column;
                transform: translateX(100%);
                transition: transform 0.3s ease;
            }
            .portal-drawer.open { transform: translateX(0); }
            .drawer-header {
                padding: 16px 20px;
                border-bottom: 1px solid var(--border-color);
                display: flex; align-items: flex-start; gap: 12px;
            }
            .drawer-header h4 { margin: 0; flex: 1; font-size: 17px; }
            .drawer-close-btn {
                background: none; border: none;
                font-size: 20px; cursor: pointer;
                color: var(--text-muted); padding: 0;
            }
            .drawer-body {
                flex: 1; overflow-y: auto;
                padding: 20px;
            }
            .drawer-img { width: 100%; border-radius: var(--border-radius); margin-bottom: 16px; }
            /* Stage progress */
            .portal-stage-row {
                display: flex; align-items: center; gap: 12px;
                padding: 12px 0; border-bottom: 1px solid var(--border-color);
            }
            .portal-stage-row:last-child { border-bottom: none; }
            .stage-dot {
                width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0;
            }
            .stage-dot.completed { background: var(--green); }
            .stage-dot.active { background: var(--portal-primary); }
            .stage-dot.pending { background: var(--border-color); }
            /* Misc */
            .portal-announcement-banner {
                background: var(--portal-light);
                border-left: 4px solid var(--portal-primary);
                padding: 12px 16px; border-radius: var(--border-radius);
                margin-bottom: 16px; font-size: 13px;
            }
            @media (max-width: 768px) {
                .portal-program-grid { grid-template-columns: 1fr; }
                .announcement-grid { grid-template-columns: 1fr; }
                .portal-hero-carousel { height: 220px; }
                .portal-drawer { width: 100%; }
            }
            /* Closed card */
            .portal-program-card.card-closed {
                opacity: 0.8;
                border-color: var(--red-100);
            }
            .portal-program-card.card-closed .card-media-area {
                filter: grayscale(40%);
            }
        `;
        document.head.appendChild(style);
    }

    // ── HELPERS ──────────────────────────────────────────────────
    function isLoggedIn() {
        return frappe.session.user && frappe.session.user !== 'Guest';
    }

    function requireLogin() {
        window.location.href = '/login?redirect-to=' + encodeURIComponent('/applicant-portal');
    }

    function renderFooter() {
        const c = state.config || {};
        return `<div class="text-center text-muted"
            style="padding:24px;font-size:12px;border-top:1px solid var(--border-color);margin-top:32px;">
            ${c.footer_text || ''}
            ${c.contact_email ? ` &middot; <a href="mailto:${c.contact_email}"
                style="color:var(--portal-primary)">${c.contact_email}</a>` : ''}
            ${c.contact_phone ? ` &middot; ${c.contact_phone}` : ''}
        </div>`;
    }

    // ── COUNTDOWN TIMER ──────────────────────────────────────────
    function getCountdown(eventDate) {
        if (!eventDate) return null;
        const now = new Date();
        const target = new Date(eventDate);
        const diff = target - now;
        if (diff <= 0) return 'Event has passed';
        const days = Math.floor(diff / 86400000);
        const hours = Math.floor((diff % 86400000) / 3600000);
        if (days > 0) return `${days} day${days !== 1 ? 's' : ''} remaining`;
        return `${hours} hour${hours !== 1 ? 's' : ''} remaining`;
    }

    // ── HERO CAROUSEL ────────────────────────────────────────────
    function renderHeroBanner(config) {
        // Fetch slides from Portal Config slideshow_images
        frappe.call({
            method: "slcm.admission.utils.portal.api_get_hero_slides",
            callback: function (r) {
                const slides = r.message || [];
                console.log(slides);
                const banner = $("#hero-carousel-container"); // Note: I should add this ID to the renderProgramSelection HTML
                if (!banner.length) return;

                if (!slides.length) {
                    // No slides — show text-only hero
                    banner.html(`
                        <div style="
                            background: linear-gradient(135deg,
                                var(--portal-primary, #1a237e),
                                var(--portal-primary-dark, #283593));
                            color: white;
                            padding: 80px 40px;
                            text-align: center;
                            border-radius: 12px;
                            margin-bottom: 32px;">
                            <h1 style="font-size:2.2rem;font-weight:700;
                                margin-bottom:12px">
                                ${config.portal_title || "Admissions Portal"}
                            </h1>
                            <p style="font-size:1.1rem;opacity:0.85">
                                ${config.portal_subtitle || ""}
                            </p>
                        </div>
                    `);
                    return;
                }

                // Build carousel
                let dots = slides.map((s, i) =>
                    `<span class="hero-dot ${i === 0 ? 'active' : ''}"
                        onclick="goToHeroSlide(${i})"
                        style="
                            display:inline-block;
                            width:${i === 0 ? '24px' : '8px'};
                            height:8px;
                            border-radius:4px;
                            background:${i === 0 ? 'white' : 'rgba(255,255,255,0.5)'};
                            margin:0 3px;
                            cursor:pointer;
                            transition:all 0.3s;">
                    </span>`
                ).join("");

                let slideHtml = slides.map((s, i) =>
                    `<div class="hero-slide ${i === 0 ? 'active' : ''}"
                        style="
                            display:${i === 0 ? 'block' : 'none'};
                            position:relative;
                            border-radius:12px;
                            overflow:hidden;
                            cursor:${s.link_url ? 'pointer' : 'default'}"
                        ${s.link_url
                        ? `onclick="window.open('${s.link_url}','_blank')"` : ""}>
                        <img src="${s.url}"
                            style="width:100%;height:380px;
                                object-fit:cover;display:block"
                            onerror="this.style.display='none'">
                        ${s.caption ? `
                        <div style="
                            position:absolute;bottom:0;left:0;right:0;
                            background:linear-gradient(transparent,
                                rgba(0,0,0,0.6));
                            color:white;padding:20px 24px;font-size:1rem">
                            ${s.caption}
                        </div>` : ""}
                    </div>`
                ).join("");

                banner.html(`
                    <div id="hero-carousel"
                        style="position:relative;margin-bottom:32px;
                            border-radius:12px;overflow:hidden;
                            box-shadow:0 4px 20px rgba(0,0,0,0.12)">
                        ${slideHtml}
                        ${slides.length > 1 ? `
                        <button onclick="prevHeroSlide()"
                            style="
                                position:absolute;left:12px;top:50%;
                                transform:translateY(-50%);
                                background:rgba(0,0,0,0.4);
                                color:white;border:none;
                                border-radius:50%;
                                width:40px;height:40px;
                                font-size:18px;cursor:pointer;
                                display:flex;align-items:center;
                                justify-content:center;
                                transition:background 0.2s;
                                z-index:10"
                            onmouseover="this.style.background='rgba(0,0,0,0.7)'"
                            onmouseout="this.style.background='rgba(0,0,0,0.4)'">
                            &#8249;
                        </button>
                        <button onclick="nextHeroSlide()"
                            style="
                                position:absolute;right:12px;top:50%;
                                transform:translateY(-50%);
                                background:rgba(0,0,0,0.4);
                                color:white;border:none;
                                border-radius:50%;
                                width:40px;height:40px;
                                font-size:18px;cursor:pointer;
                                display:flex;align-items:center;
                                justify-content:center;
                                transition:background 0.2s;
                                z-index:10"
                            onmouseover="this.style.background='rgba(0,0,0,0.7)'"
                            onmouseout="this.style.background='rgba(0,0,0,0.4)'">
                            &#8250;
                        </button>
                        <div style="
                            position:absolute;bottom:14px;left:50%;
                            transform:translateX(-50%);
                            display:flex;align-items:center;
                            z-index:10">
                            ${dots}
                        </div>` : ""}
                    </div>
                `);

                if (slides.length > 1) {
                    startHeroAutoplay();
                }
            }
        });
    }

    // Hero carousel controls
    window.goToHeroSlide = function (index) {
        const slides = $(".hero-slide");
        const dots = $(".hero-dot");
        if (!slides.length) return;
        slides.hide().removeClass("active");
        $(slides[index]).show().addClass("active");
        dots.removeClass("active").each(function (i) {
            $(this).css({
                width: i === index ? "24px" : "8px",
                background: i === index
                    ? "white" : "rgba(255,255,255,0.5)"
            });
            if (i === index) $(this).addClass("active");
        });
        state.heroIndex = index;
    };

    window.nextHeroSlide = function () {
        const total = $(".hero-slide").length;
        if (!total) return;
        goToHeroSlide((state.heroIndex + 1) % total);
        resetHeroAutoplay();
    };

    window.prevHeroSlide = function () {
        const total = $(".hero-slide").length;
        if (!total) return;
        goToHeroSlide(
            (state.heroIndex - 1 + total) % total
        );
        resetHeroAutoplay();
    };

    function startHeroAutoplay() {
        if (window._heroAutoplayTimer) clearInterval(window._heroAutoplayTimer);
        window._heroAutoplayTimer = setInterval(() => {
            const total = $(".hero-slide").length;
            if (total) {
                goToHeroSlide((state.heroIndex + 1) % total);
            }
        }, 3000);
        // Pause on hover
        $("#hero-carousel")
            .off("mouseenter mouseleave")
            .on("mouseenter", () => clearInterval(window._heroAutoplayTimer))
            .on("mouseleave", () => startHeroAutoplay());
    }

    function resetHeroAutoplay() {
        clearInterval(window._heroAutoplayTimer);
        startHeroAutoplay();
    }

    // ── PROGRAM CARD IMAGES ──────────────────────────────────────
    function renderProgramCardImage(program) {
        // program has: program_image, program_media
        // Fetch images then inject into card
        if (!program.program_media && !program.program_image) {
            return `<div class="prog-card-banner prog-card-banner-${program.program.replace(/\W/g, '_')}"
                style="
                    height:180px;
                    background:linear-gradient(135deg,
                        var(--portal-primary,#1a237e),
                        var(--portal-accent,#283593));
                    border-radius:10px 10px 0 0;
                    display:flex;align-items:center;
                    justify-content:center;">
                <span style="color:white;font-size:2rem;opacity:0.4">🎓</span>
            </div>`;
        }
        // Return placeholder — images loaded async below
        return `<div class="prog-card-banner"
            id="prog-banner-${program.program.replace(/\W/g, '_')}"
            style="height:180px;border-radius:10px 10px 0 0;
                overflow:hidden;position:relative;background:#f0f2f5">
            <div style="
                position:absolute;inset:0;display:flex;
                align-items:center;justify-content:center;
                color:#ccc;font-size:24px">⏳</div>
        </div>`;
    }

    function loadProgramCardImages(program) {
        if (!program.program_media && !program.program_image) return;
        frappe.call({
            method: "slcm.admission.utils.portal.api_get_program_images",
            args: {
                program_media: program.program_media || null,
                program_image: program.program_image || null
            },
            callback: function (r) {
                const images = r.message || [];
                const bannerId = `prog-banner-${program.program.replace(/\W/g, '_')}`;
                const banner = $(`#${bannerId}`);
                if (!banner.length || !images.length) return;

                if (images.length === 1) {
                    banner.html(`
                        <img src="${images[0].url}"
                            style="width:100%;height:180px;
                                object-fit:cover;display:block"
                            onerror="this.closest('.prog-card-banner')
                                .style.background='#f0f2f5'">
                    `);
                    return;
                }

                // Multiple images — build mini carousel
                let slides = images.map((img, i) =>
                    `<div class="pc-slide pc-slide-${program.program.replace(/\W/g, '_')}"
                        style="display:${i === 0 ? 'block' : 'none'};
                            position:absolute;inset:0">
                        <img src="${img.url}"
                            style="width:100%;height:180px;
                                object-fit:cover"
                            onerror="this.style.display='none'">
                        ${img.caption ? `
                        <div style="
                            position:absolute;bottom:0;left:0;right:0;
                            background:linear-gradient(transparent,
                                rgba(0,0,0,0.55));
                            color:white;font-size:11px;
                            padding:8px 10px">
                            ${img.caption}
                        </div>` : ""}
                    </div>`
                ).join("");

                let dots = images.map((_, i) =>
                    `<span class="pc-dot pc-dot-${program.program.replace(/\W/g, '_')}"
                        data-index="${i}"
                        style="
                            display:inline-block;
                            width:${i === 0 ? '16px' : '6px'};
                            height:6px;border-radius:3px;
                            background:${i === 0
                        ? 'white' : 'rgba(255,255,255,0.5)'};
                            margin:0 2px;cursor:pointer;
                            transition:all 0.25s">
                    </span>`
                ).join("");

                banner.css("position", "relative").html(`
                    <div style="position:relative;height:180px;
                        overflow:hidden">
                        ${slides}
                        <div style="
                            position:absolute;bottom:8px;left:50%;
                            transform:translateX(-50%);
                            display:flex;align-items:center;z-index:5">
                            ${dots}
                        </div>
                    </div>
                `);

                // Dot click handlers
                banner.find(`.pc-dot-${program.program.replace(/\W/g, '_')}`)
                    .on("click", function () {
                        const idx = parseInt($(this).data("index"));
                        goToProgramSlide(program.program, idx, images.length);
                    });

                // Auto-transition
                startProgramSlideshow(program.program, images.length);
            }
        });
    }

    window._progSlideshows = {};

    window.goToProgramSlide = function (prog, index, total) {
        const p_id = prog.replace(/\W/g, '_');
        $(`.pc-slide-${p_id}`).hide().eq(index).show();
        $(`.pc-dot-${p_id}`).each(function (i) {
            $(this).css({
                width: i === index ? "16px" : "6px",
                background: i === index
                    ? "white" : "rgba(255,255,255,0.5)"
            });
        });
        window._progSlideshows[prog] = window._progSlideshows[prog] || {};
        window._progSlideshows[prog].current = index;
    };

    function startProgramSlideshow(prog, total) {
        if (window._progSlideshows[prog]
            && window._progSlideshows[prog].timer) {
            clearInterval(window._progSlideshows[prog].timer);
        }
        window._progSlideshows[prog] = {
            current: 0,
            timer: setInterval(() => {
                const cur = window._progSlideshows[prog].current || 0;
                goToProgramSlide(prog, (cur + 1) % total, total);
            }, 3000)
        };
    }

    // ── PROGRAM CARD ─────────────────────────────────────────────
    function buildProgramCard(p) {
        const media = state.media[p.program] || [];
        const images = media.filter(m => m.media_type === 'Image');
        const hasVideo = media.some(m => m.media_type === 'Video');
        const hasBrochure = media.some(m => m.media_type === 'Brochure');
        const brochureUrl = hasBrochure ? media.find(m => m.media_type === 'Brochure').brochure_pdf : null;

        // Seat / status info
        const ps = state.program_statuses[p.program] || {};
        const isClosed = !ps.is_open;
        const showFillingFast = ps.show_filling_fast && !isClosed;
        const showSeatsFilled = ps.show_seats_filled;

        // Seat badge HTML
        let seatBadgeHtml = '';
        if (showSeatsFilled || (isClosed && ps.close_reason === 'seats_filled')) {
            seatBadgeHtml = `<span class="indicator-pill red" style="font-size:11px">
                Seats Filled</span>`;
        } else if (showFillingFast) {
            seatBadgeHtml = `<span class="indicator-pill orange" style="font-size:11px">
                Filling Fast</span>`;
        }

        // Closed badge
        const closedBadgeHtml = isClosed
            ? `<span class="indicator-pill red" style="font-size:11px;margin-left:4px">
                Closed</span>` : '';

        // Apply button
        let applyBtnHtml = '';
        if (isClosed) {
            applyBtnHtml = `<button class="btn btn-default btn-sm" disabled
                style="cursor:not-allowed;opacity:0.6">
                Applications Closed
            </button>`;
        } else {
            applyBtnHtml = `<button class="btn btn-primary btn-sm apply-btn"
                data-program="${p.program}"
                data-name="${encodeURIComponent(p.program_name)}">
                Apply Now
            </button>`;
        }

        let mediaHtml = '';
        if (images.length) {
            const imgNavHtml = images.length > 1
                ? `<button class="card-media-nav prev" data-program="${p.program}" data-dir="-1">&#8249;</button>
                   <button class="card-media-nav next" data-program="${p.program}" data-dir="1">&#8250;</button>`
                : '';
            const badgeHtml = `<div class="card-media-badges">
                ${hasVideo ? `<span class="indicator-pill blue" style="font-size:10px">Video</span>` : ''}
                ${hasBrochure ? `<span class="indicator-pill gray" style="font-size:10px">Brochure</span>` : ''}
            </div>`;
            mediaHtml = `<div class="card-media-area" id="card-media-${p.program.replace(/\W/g, '_')}">
                <img src="${images[0].image}" alt="${p.program_name}" data-images='${JSON.stringify(images.map(i => i.image))}' data-index="0">
                ${imgNavHtml}
                ${badgeHtml}
            </div>`;
        } else {
            mediaHtml = `<div class="card-media-area" style="background:var(--portal-light);
                display:flex;align-items:center;justify-content:center;color:var(--portal-primary);">
                <span style="font-size:32px;opacity:0.4">${p.program_abbreviation || p.program_name.charAt(0)}</span>
            </div>`;
        }

        const seatsHtml = (state.config.show_intake_count && ps.total_seats)
            ? `<div style="font-size:12px;color:var(--text-muted);margin-bottom:6px">
                ${ps.available_seats > 0
                ? `${ps.available_seats} of ${ps.total_seats} seats available`
                : `${ps.total_seats} total seats`}
               </div>`
            : '';

        const eligibilityHtml = p.eligibility_hint
            ? `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">
                ${p.eligibility_hint}</div>` : '';

        return `<div class="portal-program-card ${isClosed ? 'card-closed' : ''}">
            ${renderProgramCardImage(p)}
            <div class="card-body">
                <div style="display:flex;align-items:flex-start;
                    justify-content:space-between;gap:8px;margin-bottom:4px;">
                    <div class="card-program-name">${p.program_name}</div>
                    <div style="flex-shrink:0">
                        ${seatBadgeHtml}${closedBadgeHtml}
                    </div>
                </div>
                ${p.program_abbreviation ? `<div class="text-muted" style="font-size:12px;margin-bottom:6px">${p.program_abbreviation}</div>` : ''}
                ${seatsHtml}
                ${eligibilityHtml}
                <div class="card-actions">
                    ${applyBtnHtml}
                    ${hasVideo ? `<button class="btn btn-default btn-sm video-btn"
                        data-url="${media.find(m => m.media_type === 'Video').video_url}">
                        Watch Video
                    </button>` : ''}
                    ${hasBrochure ? `<a class="btn btn-default btn-sm" href="${brochureUrl}" target="_blank">
                        Brochure
                    </a>` : ''}
                </div>
            </div>
        </div>`;
    }

    // ── ANNOUNCEMENT CARD ────────────────────────────────────────
    function buildAnnouncementCard(ann) {
        const isEvent = ann.announcement_type === 'Event';
        const countdown = isEvent ? getCountdown(ann.event_date) : null;
        const imgHtml = ann.featured_image
            ? `<img class="ann-card-img" src="${ann.featured_image}" alt="${ann.title}">`
            : `<div class="ann-card-img-placeholder">${isEvent ? '&#128197;' : '&#128226;'}</div>`;
        const countdownHtml = countdown
            ? `<div class="ann-countdown">${countdown}</div>` : '';
        const date = ann.publish_date ? frappe.datetime.str_to_user(ann.publish_date.split(' ')[0]) : '';

        return `<div class="ann-card" data-ann="${ann.name}">
            ${imgHtml}
            <div class="ann-card-body">
                <div class="ann-type-badge ${isEvent ? 'event' : 'announcement'}">
                    ${isEvent ? 'Event' : 'Announcement'}
                </div>
                <div class="ann-title">${ann.title}</div>
                <div class="ann-summary text-muted" style="font-size:12px">
                    ${ann.summary || ''}
                </div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:6px">${date}</div>
                ${countdownHtml}
            </div>
        </div>`;
    }

    // ── ANNOUNCEMENTS SECTION ────────────────────────────────────
    function buildAnnouncementsSection(anns) {
        if (!anns || !anns.length) return '';
        return `<div class="portal-announcements">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <h5 style="margin:0;color:var(--portal-primary)">Announcements &amp; Events</h5>
                <span class="text-muted" style="font-size:12px">${anns.length} item${anns.length !== 1 ? 's' : ''}</span>
            </div>
            <div class="announcement-grid">
                ${anns.slice(0, 6).map(buildAnnouncementCard).join('')}
            </div>
            ${anns.length > 6 ? `<div class="text-center" style="margin-top:12px;">
                <button class="btn btn-default btn-sm" id="view-all-ann">View all announcements</button>
            </div>` : ''}
        </div>`;
    }

    // ── SIDE DRAWER ──────────────────────────────────────────────
    function openDrawer(ann) {
        // Increment view count silently
        frappe.call({
            method: 'slcm.admission.utils.portal.api_increment_view_count',
            args: { name: ann.name }
        });

        // Fetch full content
        frappe.call({
            method: 'slcm.admission.utils.portal.api_get_announcement_detail',
            args: { name: ann.name }
        }).then(r => {
            const detail = r.message;
            if (!detail) return;

            const isEvent = detail.announcement_type === 'Event';
            const countdown = isEvent ? getCountdown(detail.event_date) : null;
            const imgHtml = detail.featured_image
                ? `<img class="drawer-img" src="${detail.featured_image}" alt="${detail.title}">` : '';
            const eventHtml = isEvent ? `
                <div class="frappe-card" style="padding:14px;margin-bottom:16px;font-size:13px;">
                    ${detail.event_date ? `<div><strong>Date:</strong> ${frappe.datetime.str_to_user(detail.event_date.split(' ')[0])}</div>` : ''}
                    ${detail.event_venue ? `<div style="margin-top:4px"><strong>Venue:</strong> ${detail.event_venue}</div>` : ''}
                    ${countdown ? `<div class="ann-countdown" style="margin-top:8px">${countdown}</div>` : ''}
                    ${detail.event_registration_url ? `<a href="${detail.event_registration_url}" target="_blank"
                        class="btn btn-primary btn-sm" style="margin-top:12px">Register</a>` : ''}
                </div>` : '';

            // Remove any existing drawer
            $('#portal-drawer-backdrop, #portal-drawer').remove();

            const $backdrop = $('<div class="portal-drawer-backdrop" id="portal-drawer-backdrop"></div>');
            const $drawer = $(`<div class="portal-drawer" id="portal-drawer">
                <div class="drawer-header">
                    <div>
                        <div class="ann-type-badge ${isEvent ? 'event' : 'announcement'}" style="margin-bottom:6px">
                            ${isEvent ? 'Event' : 'Announcement'}
                        </div>
                        <h4>${detail.title}</h4>
                    </div>
                    <button class="drawer-close-btn" id="drawer-close">&times;</button>
                </div>
                <div class="drawer-body">
                    ${imgHtml}
                    ${eventHtml}
                    <div style="font-size:14px;line-height:1.7">${detail.content}</div>
                </div>
            </div>`);

            $('body').append($backdrop).append($drawer);
            setTimeout(() => $drawer.addClass('open'), 20);

            $backdrop.on('click', closeDrawer);
            $('#drawer-close').on('click', closeDrawer);

            // Mark as read in bell
            markBellRead(ann.name);
        });
    }

    function closeDrawer() {
        $('#portal-drawer').removeClass('open');
        setTimeout(() => {
            $('#portal-drawer-backdrop, #portal-drawer').remove();
        }, 320);
    }

    // ── BELL ICON ────────────────────────────────────────────────
    function getBellUnread() {
        try {
            const read = JSON.parse(localStorage.getItem('portal_ann_read') || '[]');
            return state.announcements.filter(a => !read.includes(a.name)).length;
        } catch (e) { return 0; }
    }

    function markBellRead(name) {
        try {
            const read = JSON.parse(localStorage.getItem('portal_ann_read') || '[]');
            if (!read.includes(name)) {
                read.push(name);
                localStorage.setItem('portal_ann_read', JSON.stringify(read));
            }
            updateBellBadge();
        } catch (e) { }
    }

    function updateBellBadge() {
        const count = getBellUnread();
        const $badge = $('#portal-bell-badge');
        if (count > 0) {
            $badge.text(count).show();
        } else {
            $badge.hide();
        }
    }

    function buildBellHtml() {
        const count = getBellUnread();
        return `<button class="portal-bell-btn" id="portal-bell-btn" title="Announcements">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            <span class="portal-bell-badge" id="portal-bell-badge" ${count === 0 ? 'style="display:none"' : ''}>
                ${count}
            </span>
        </button>`;
    }

    function bindBellEvents() {
        $body.find('#portal-bell-btn').on('click', function () {
            if (!state.announcements.length) {
                frappe.show_alert({ message: 'No announcements at this time.', indicator: 'gray' }, 3);
                return;
            }
            // Show a simple dropdown
            const $existing = $('#portal-bell-dropdown');
            if ($existing.length) { $existing.remove(); return; }

            const read_list = JSON.parse(localStorage.getItem('portal_ann_read') || '[]');
            const items = state.announcements.slice(0, 5).map(a => {
                const is_read = read_list.includes(a.name);
                return `
                <div class="ann-bell-item" data-ann="${a.name}"
                    style="padding:10px 14px;border-bottom:1px solid var(--border-color);
                    cursor:pointer;font-size:13px;display:flex;align-items:flex-start;gap:10px;
                    background:${is_read ? 'white' : 'var(--portal-light)'}">
                    <div style="flex:1">
                        <div style="font-weight:600">${a.title}</div>
                        <div style="font-size:11px;color:var(--text-muted)">
                            ${a.announcement_type}
                        </div>
                    </div>
                    <span class="notif-unread-dot"
                        style="display:${is_read ? 'none' : 'inline-block'};
                            width:8px;height:8px;border-radius:50%;
                            background:var(--portal-primary);flex-shrink:0;
                            margin-top:4px">
                    </span>
                    <span class="notif-read-tick"
                        style="display:${is_read ? 'inline-block' : 'none'};
                            color:var(--green);font-size:14px;flex-shrink:0">
                        ✓
                    </span>
                </div>`;
            }).join('');

            const $dd = $(`<div id="portal-bell-dropdown"
                style="position:absolute;z-index:1060;right:0;top:40px;
                width:300px;background:var(--card-bg);
                border:1px solid var(--border-color);border-radius:var(--border-radius);
                box-shadow:var(--shadow-lg);">
                <div style="padding:10px 14px;font-weight:700;border-bottom:1px solid var(--border-color);
                    font-size:13px;display:flex;justify-content:space-between;align-items:center;">
                    <span>Announcements</span>
                    <button class="btn btn-xs btn-default" id="bell-mark-all">Mark all read</button>
                </div>
                ${items}
                <div style="padding:10px 14px;text-align:center;">
                    <a href="#announcements" style="font-size:12px;color:var(--portal-primary)">
                        View all
                    </a>
                </div>
            </div>`);

            $(this).css('position', 'relative').append($dd);

            // Notification item click — close dropdown, open drawer, mark read
            $dd.find('.ann-bell-item').on('click', function () {
                const ann_name = $(this).data("ann");
                const notif_id = $(this).data("notif-id");

                // 1. Close dropdown immediately
                $dd.remove();

                // 2. Mark as read in UI immediately
                $(this).find(".notif-unread-dot").hide();
                $(this).find(".notif-read-tick").show();
                $(this).css("background", "white");

                // 3. Decrement badge
                const badge = $("#portal-bell-badge");
                let count = parseInt(badge.text()) || 0;
                count = Math.max(0, count - 1);
                badge.text(count);
                if (count === 0) badge.hide();

                // 4. Mark as read in DB
                if (notif_id) {
                    frappe.call({
                        method: "slcm.admission.utils.portal.api_mark_notification_read",
                        args: { notification_id: notif_id }
                    });
                }

                // 5. Open side drawer with announcement details
                if (ann_name) {
                    openAnnouncementDrawer(ann_name);
                }
            });

            $('#bell-mark-all').on('click', function (e) {
                e.stopPropagation();
                try {
                    localStorage.setItem('portal_ann_read',
                        JSON.stringify(state.announcements.map(a => a.name)));
                } catch (e) { }
                updateBellBadge();
                $dd.remove();
            });

            $(document).one('click.bell', function (e) {
                if (!$(e.target).closest('#portal-bell-btn, #portal-bell-dropdown').length) {
                    $dd.remove();
                }
            });
        });
    }

    // ── HEADER BAR ───────────────────────────────────────────────
    function buildHeaderBar() {
        const loginHtml = isLoggedIn()
            ? `<span class="text-muted" style="font-size:12px">${frappe.session.user}</span>`
            : `<button class="btn btn-default btn-sm" id="header-login-btn">Login</button>`;
        return `<div style="display:flex;justify-content:flex-end;align-items:center;
            gap:12px;margin-bottom:12px;padding:4px 0;">
            ${buildBellHtml()}
            ${loginHtml}
        </div>`;
    }

    // ── INIT ─────────────────────────────────────────────────────
    async function init() {
        $body.html('<div class="text-center text-muted" style="padding:60px">Loading...</div>');

        const [configR, annsR, mediaR] = await Promise.all([
            frappe.call({ method: 'slcm.admission.utils.portal.api_get_portal_config' }),
            frappe.call({ method: 'slcm.admission.utils.portal.api_get_announcements' }),
            frappe.call({ method: 'slcm.admission.utils.portal.api_get_program_media' })
        ]);

        state.config = configR.message || {};
        state.announcements = annsR.message || [];
        const allMedia = mediaR.message || [];
        state.heroMedia = allMedia.filter(m => m.is_featured && m.media_type === 'Image');

        // Group media by program
        allMedia.forEach(m => {
            if (!state.media[m.program]) state.media[m.program] = [];
            state.media[m.program].push(m);
        });

        // Programs and statuses fetched after config so we have the cycle
        // statuses stored per program in state
        state.program_statuses = {};  // will be populated in renderProgramSelection

        applyTheme(state.config.primary_color, state.config.secondary_color);
        page.set_title(state.config.portal_title || 'Applicant Portal');

        if (!state.config.portal_active) {
            renderMaintenance();
            return;
        }

        // Logged-in: check existing application
        if (isLoggedIn()) {
            const appR = await frappe.call({
                method: 'slcm.admission.utils.portal.api_get_my_application'
            });
            state.applicant = appR.message || null;
            if (state.applicant) {
                renderDashboard();
                return;
            }
        }

        // Check stored program from pre-login
        if (isLoggedIn()) {
            const stored = sessionStorage.getItem('portal_apply_program');
            if (stored) {
                sessionStorage.removeItem('portal_apply_program');
                sessionStorage.removeItem('portal_apply_program_name');
                state.selected_program = {
                    program: stored,
                    program_name: sessionStorage.getItem('portal_apply_program_name') || stored
                };
                proceedToApplication();
                return;
            }
        }

        renderProgramSelection();
    }

    // ── MAINTENANCE ──────────────────────────────────────────────
    function renderMaintenance() {
        $body.html(`
            <div class="text-center" style="padding:80px 20px;">
                <h3>${state.config.portal_title || 'Admissions Portal'}</h3>
                <div class="text-muted" style="max-width:480px;margin:12px auto;">
                    ${state.config.maintenance_message || 'Portal is temporarily unavailable.'}
                </div>
                ${state.config.contact_email ? `<a class="btn btn-default mt-3"
                    href="mailto:${state.config.contact_email}">Contact Admissions</a>` : ''}
            </div>
        `);
    }

    // ── PROGRAM SELECTION ────────────────────────────────────────
    async function renderProgramSelection() {
        const programsR = await frappe.call({
            method: 'slcm.admission.utils.portal.api_get_programs'
        });
        state.programs = programsR.message || [];

        // Fetch all program statuses in one call
        if (state.programs.length > 0) {
            const cycle = state.programs[0].admission_cycle;
            if (cycle) {
                const statusR = await frappe.call({
                    method: 'slcm.admission.utils.portal.api_get_all_program_statuses',
                    args: { cycle: cycle }
                });
                state.program_statuses = statusR.message || {};
            }
        }

        const layoutClass = state.config.program_card_layout === 'List'
            ? 'portal-program-list' : 'portal-program-grid';

        const cardsHtml = state.programs.length
            ? `<div class="${layoutClass}">${state.programs.map(buildProgramCard).join('')}</div>`
            : '<div class="text-muted text-center" style="padding:32px">No programs are currently open for admission.</div>';

        const annsHtml = buildAnnouncementsSection(state.announcements);

        $body.html(`
            <div style="max-width:1100px;margin:0 auto;padding:20px;" id="portal-announcements">
                ${buildHeaderBar()}
                <div id="hero-carousel-container"></div>
                ${state.config.show_announcement && state.config.header_announcement
                ? `<div class="portal-announcement-banner">${state.config.header_announcement}</div>` : ''}
                <div class="frappe-card" style="padding:20px;margin-bottom:20px;">
                    <h5 style="color:var(--portal-primary);margin-bottom:4px">Available Programs</h5>
                    <p class="text-muted" style="font-size:13px;margin-bottom:0">
                        ${isLoggedIn() ? 'Select a program to begin your application.'
                : 'Browse programs below. Click Apply Now to log in and start your application.'}
                    </p>
                    ${cardsHtml}
                </div>
                ${annsHtml}
            </div>
            ${renderFooter()}
        `);

        // Bind events
        renderHeroBanner(state.config);

        state.programs.forEach(p => {
            loadProgramCardImages(p);
        });

        bindBellEvents();

        $body.find('#header-login-btn').on('click', requireLogin);

        // Card image navigation
        $body.find('.card-media-nav').on('click', function (e) {
            e.stopPropagation();
            const program = $(this).data('program');
            const dir = parseInt($(this).data('dir'));
            const $img = $body.find(`#card-media-${program.replace(/\W/g, '_')} img`);
            const images = JSON.parse($img.attr('data-images') || '[]');
            let idx = parseInt($img.attr('data-index') || '0') + dir;
            idx = ((idx % images.length) + images.length) % images.length;
            $img.attr('src', images[idx]).attr('data-index', idx);
        });

        // Video modal
        $body.find('.video-btn').on('click', function () {
            const url = $(this).data('url');
            const d = new frappe.ui.Dialog({
                title: 'Program Video',
                fields: [{
                    fieldtype: 'HTML', fieldname: 'video',
                    options: `<div style="text-align:center">
                        <iframe width="100%" height="315" src="${url}"
                            frameborder="0" allowfullscreen></iframe>
                    </div>` }]
            });
            d.show();
        });

        // Apply Now
        $body.find('.apply-btn').on('click', function () {
            const program = $(this).data('program');
            const programName = decodeURIComponent($(this).data('name'));
            if (!isLoggedIn()) {
                sessionStorage.setItem('portal_apply_program', program);
                sessionStorage.setItem('portal_apply_program_name', programName);
                requireLogin();
                return;
            }
            state.selected_program = { program, program_name: programName };
            proceedToApplication();
        });

        // Announcement cards
        $body.find('.ann-card').on('click', function () {
            const name = $(this).data('ann');
            const ann = state.announcements.find(a => a.name === name);
            if (ann) openDrawer(ann);
        });
    }

    // ── PROCEED TO APPLICATION ───────────────────────────────────
    async function proceedToApplication() {
        if (!isLoggedIn()) { requireLogin(); return; }

        const campusR = await frappe.call({
            method: 'slcm.admission.utils.portal.api_get_campus_options',
            args: { program: state.selected_program.program }
        });
        const campuses = campusR.message || [];

        if (campuses.length > 1) {
            renderCampusSelection(campuses);
        } else {
            state.selected_campuses = campuses.length === 1
                ? [{ campus: campuses[0].campus, preference_order: 1 }] : [];
            await createApplicantAndLoadForm();
        }
    }

    // ── CAMPUS SELECTION ─────────────────────────────────────────
    function renderCampusSelection(campuses) {
        $body.html(`
            <div style="max-width:700px;margin:0 auto;padding:20px;">
                <button class="btn btn-default btn-sm mb-3" id="back-progs">Back to Programs</button>
                <div class="frappe-card" style="padding:24px;">
                    <h4 style="color:var(--portal-primary)">Select Campus Preferences</h4>
                    <p class="text-muted" style="font-size:13px;">
                        Program: <strong>${state.selected_program.program_name}</strong>
                    </p>
                    ${campuses.map((c, i) => `
                        <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;
                            border:1px solid var(--border-color);border-radius:var(--border-radius);
                            margin-bottom:8px;background:var(--card-bg);">
                            <div style="width:28px;height:28px;border-radius:50%;
                                background:var(--portal-primary);color:#fff;
                                display:flex;align-items:center;justify-content:center;
                                font-weight:700;font-size:13px;flex-shrink:0">${i + 1}</div>
                            <div style="flex:1;font-weight:600">${c.campus_name}</div>
                            <label style="display:flex;align-items:center;gap:6px;margin:0;cursor:pointer">
                                <input type="checkbox" class="campus-check"
                                    data-campus="${c.campus}" checked> Include
                            </label>
                        </div>`).join('')}
                    <button class="btn btn-primary mt-3" id="confirm-campus">Confirm and Continue</button>
                </div>
            </div>
            ${renderFooter()}
        `);
        $body.find('#back-progs').on('click', renderProgramSelection);
        $body.find('#confirm-campus').on('click', async function () {
            const checked = $body.find('.campus-check:checked');
            if (!checked.length) {
                frappe.show_alert({ message: 'Please select at least one campus.', indicator: 'red' }, 4);
                return;
            }
            state.selected_campuses = [];
            checked.each(function (i) {
                state.selected_campuses.push({ campus: $(this).data('campus'), preference_order: i + 1 });
            });
            await createApplicantAndLoadForm();
        });
    }

    // ── CREATE APPLICANT + LOAD FORM ─────────────────────────────
    async function createApplicantAndLoadForm() {
        const cycleR = await frappe.call({
            method: 'frappe.client.get_list',
            args: { doctype: 'Admission Cycle', filters: { status: 'Active' }, fields: ['name'], limit: 1 }
        });
        const cycle = cycleR.message && cycleR.message[0] ? cycleR.message[0].name : null;
        if (!cycle) {
            frappe.msgprint({
                title: 'No Active Cycle',
                message: 'No active admission cycle. Please contact admissions.', indicator: 'red'
            });
            return;
        }

        // Get categories for fee calculation
        if (!state.applicant_category) {
            const feeR = await frappe.call({
                method: 'slcm.admission.utils.portal.api_get_application_fee',
                args: {
                    program: state.selected_program.program,
                    cycle: cycle,
                    category: null
                }
            });
            // Only show category selector if fee matrix has multiple categories
            // Otherwise skip straight to form
        }
        state.applicant_cycle = cycle;

        const appR = await frappe.call({
            method: 'slcm.admission.utils.portal.get_or_create_applicant',
            args: {
                email: frappe.session.user,
                full_name: frappe.session.data.full_name || '',
                mobile: '', cycle: cycle,
                program: state.selected_program.program,
                campus_preferences: state.selected_campuses
            }
        });
        if (appR.exc) return;
        state.applicant = appR.message;

        const formR = await frappe.call({
            method: 'slcm.admission.utils.portal.api_get_form',
            args: { program: state.selected_program.program, cycle: cycle }
        });
        state.form = formR.message;

        if (!state.form || !state.form.fields || !state.form.fields.length) {
            frappe.msgprint({
                title: 'Form Not Configured',
                message: 'No application form configured for this program.', indicator: 'orange'
            });
            return;
        }

        buildTabs();
        state.current_tab = 0;
        renderFormView();
    }

    // ── FORM ─────────────────────────────────────────────────────
    function buildTabs() {
        const fields = state.form.fields;
        const size = 5;
        state.tabs = [];
        for (let i = 0; i < fields.length; i += size) {
            state.tabs.push({ type: 'fields', fields: fields.slice(i, i + size) });
        }
        state.tabs.push({ type: 'documents', fields: [] });
        state.tabs.push({ type: 'review', fields: [] });
    }

    function renderFormView() {
        const tabs = state.tabs;
        const current = tabs[state.current_tab];
        const pct = Math.round((state.current_tab / (tabs.length - 1)) * 100);

        const tabNav = tabs.map((t, i) => {
            const label = t.type === 'documents' ? 'Documents'
                : t.type === 'review' ? 'Review & Submit' : `Section ${i + 1}`;
            const done = i < state.current_tab;
            const active = i === state.current_tab;
            return `<li class="nav-item" style="margin:2px">
                <a class="nav-link ${active ? 'active' : ''}" href="#"
                    style="font-size:13px;padding:6px 14px;cursor:pointer;
                    ${active ? 'background:var(--portal-primary);color:#fff;border-radius:20px;' : ''}
                    ${done ? 'color:var(--green);' : ''}"
                    data-tab="${i}">${done ? '&#10003; ' : ''}${label}</a>
            </li>`;
        }).join('');

        let contentHtml = '';
        if (current.type === 'fields') {
            contentHtml = `<div class="row">${current.fields.map(f =>
                `<div class="col-sm-6">${renderField(f)}</div>`).join('')}</div>`;
        } else if (current.type === 'documents') {
            const note = state.config.document_upload_note || 'Upload required supporting documents.';
            contentHtml = `<h5 style="color:var(--portal-primary)">Document Upload</h5>
                <div class="alert alert-info" style="font-size:13px">${note}</div>`;
        } else {
            const rows = Object.entries(state.form_data).filter(([, v]) => v)
                .map(([k, v]) => `<tr>
                    <td style="padding:8px 12px;font-weight:600;border:1px solid var(--border-color);width:45%">
                        ${k.replace(/_/g, ' ')}</td>
                    <td style="padding:8px 12px;border:1px solid var(--border-color)">${v}</td>
                </tr>`).join('');
            contentHtml = `<h5 style="color:var(--portal-primary)">Review Your Application</h5>
                <div class="alert alert-warning" style="font-size:13px">
                    Submission is final. Please review carefully.</div>
                <table style="width:100%;border-collapse:collapse;font-size:13px">
                    <thead><tr style="background:var(--portal-light)">
                        <th style="padding:8px 12px;border:1px solid var(--border-color)">Field</th>
                        <th style="padding:8px 12px;border:1px solid var(--border-color)">Answer</th>
                    </tr></thead>
                    <tbody>${rows || '<tr><td colspan="2" class="text-muted text-center" style="padding:20px">No entries yet.</td></tr>'}</tbody>
                </table>`;
        }

        const isLast = state.current_tab === tabs.length - 1;
        $body.html(`
            <div style="max-width:820px;margin:0 auto;padding:20px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                    <button class="btn btn-default btn-sm" id="back-progs2">Back to Programs</button>
                    <h5 style="margin:0;color:var(--portal-primary)">${state.selected_program.program_name}</h5>
                </div>
                <ul class="nav" style="flex-wrap:wrap;margin-bottom:12px;">${tabNav}</ul>
                <div style="height:4px;background:var(--border-color);border-radius:4px;margin-bottom:16px;">
                    <div style="height:4px;width:${pct}%;background:var(--portal-primary);border-radius:4px;transition:width 0.3s;"></div>
                </div>
                <div class="frappe-card" style="padding:24px;">${contentHtml}</div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:16px;">
                    ${state.current_tab > 0 ? '<button class="btn btn-default" id="prev-tab">Previous</button>' : '<div></div>'}
                    <span class="text-muted" style="font-size:11px" id="save-status"></span>
                    ${isLast
                ? '<button class="btn btn-success" id="submit-btn">Submit Application</button>'
                : '<button class="btn btn-primary" id="next-tab">Save and Continue</button>'}
                </div>
                <div class="text-muted text-center" style="font-size:11px;margin-top:8px;">Progress auto-saved every 60 seconds</div>
            </div>
            ${renderFooter()}
        `);

        $body.find('#back-progs2').on('click', renderProgramSelection);
        $body.find('[data-tab]').on('click', function (e) {
            e.preventDefault();
            const t = parseInt($(this).data('tab'));
            if (t <= state.current_tab) { collectFormData(); state.current_tab = t; renderFormView(); }
        });
        $body.find('#prev-tab').on('click', () => { collectFormData(); state.current_tab--; renderFormView(); });
        $body.find('#next-tab').on('click', () => { collectFormData(); triggerAutoSave(); state.current_tab++; renderFormView(); });
        $body.find('#submit-btn').on('click', () => frappe.confirm(
            'Submit your application? This cannot be undone.', submitApplication));

        if (window._portalTimer) clearInterval(window._portalTimer);
        window._portalTimer = setInterval(() => { collectFormData(); triggerAutoSave(true); }, 60000);
    }

    function renderField(f) {
        const val = state.form_data[f.fieldname] || '';
        const req = f.mandatory ? '<span class="text-danger">*</span>' : '';
        if (f.fieldtype === 'Select' && f.options) {
            const opts = ['', ...f.options.split('\n')].map(o =>
                `<option value="${o}" ${o === val ? 'selected' : ''}>${o || '-- Select --'}</option>`).join('');
            return `<div class="form-group"><label class="control-label">${f.label} ${req}</label>
                <select class="form-control form-field" data-field="${f.fieldname}">${opts}</select></div>`;
        }
        if (f.fieldtype === 'Text') {
            return `<div class="form-group"><label class="control-label">${f.label} ${req}</label>
                <textarea class="form-control form-field" data-field="${f.fieldname}" rows="3">${val}</textarea></div>`;
        }
        if (f.fieldtype === 'Date') {
            return `<div class="form-group"><label class="control-label">${f.label} ${req}</label>
                <input type="date" class="form-control form-field" data-field="${f.fieldname}" value="${val}"></div>`;
        }
        return `<div class="form-group"><label class="control-label">${f.label} ${req}</label>
            <input type="text" class="form-control form-field" data-field="${f.fieldname}"
                value="${val}" placeholder="${f.label}"></div>`;
    }

    function collectFormData() {
        $body.find('.form-field').each(function () {
            const f = $(this).data('field');
            if (f) state.form_data[f] = $(this).val();
        });
    }

    async function triggerAutoSave(silent = false) {
        if (!state.applicant || !state.form) return;
        await frappe.call({
            method: 'slcm.admission.utils.portal.api_autosave',
            args: {
                applicant: state.applicant.name || state.applicant,
                form_config: state.form.form_name,
                responses: JSON.stringify(state.form_data)
            }
        });
        if (!silent) {
            $('#save-status').text('Saved').css('color', 'var(--green)');
            setTimeout(() => $('#save-status').text(''), 3000);
        }
    }

    async function submitApplication() {
        collectFormData();
        const name = state.applicant.name || state.applicant;
        const $btn = $body.find('#submit-btn').text('Submitting...').prop('disabled', true);
        const r = await frappe.call({
            method: 'slcm.admission.utils.portal.api_submit',
            args: { applicant: name, form_config: state.form.form_name, responses: JSON.stringify(state.form_data) }
        });
        if (r.message && r.message.success) {
            clearInterval(window._portalTimer);
            frappe.show_alert({ message: 'Application submitted successfully.', indicator: 'green' }, 6);
            state.applicant = { name, application_status: 'Submitted' };

            // Check if fee is required
            const cycle = state.applicant_cycle || (state.form && state.form.admission_cycle);
            if (state.selected_program && cycle) {
                const feeR = await frappe.call({
                    method: 'slcm.admission.utils.portal.api_get_application_fee',
                    args: {
                        program: state.selected_program.program,
                        cycle: cycle,
                        category: state.applicant_category || null
                    }
                });
                const fee = feeR.message || {};
                if (fee.fee_amount && fee.fee_amount > 0) {
                    renderFeePayment(fee, name);
                    return;
                }
            }
            renderDashboard();
        } else {
            frappe.msgprint({
                title: 'Submission Failed',
                message: (r.message && r.message.error) || 'Please try again.', indicator: 'red'
            });
            $btn.text('Submit Application').prop('disabled', false);
        }
    }

    function renderFeePayment(fee, applicantName) {
        $body.html(`
            <div style="max-width:540px;margin:60px auto;padding:20px;">
                <div class="frappe-card" style="padding:32px;text-align:center;">
                    <div style="width:60px;height:60px;border-radius:50%;
                        background:var(--portal-light);
                        display:flex;align-items:center;justify-content:center;
                        margin:0 auto 16px;">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
                            stroke="var(--portal-primary)" stroke-width="2">
                            <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
                            <line x1="1" y1="10" x2="23" y2="10"/>
                        </svg>
                    </div>
                    <h4 style="margin-bottom:4px">Application Fee Payment</h4>
                    <p class="text-muted" style="font-size:13px;margin-bottom:20px">
                        Your application has been submitted. Please pay the application
                        fee to complete your registration.
                    </p>
                    <div style="background:var(--portal-light);
                        border-radius:var(--border-radius);
                        padding:16px;margin-bottom:24px;">
                        <div style="font-size:13px;color:var(--text-muted);
                            margin-bottom:4px">
                            ${fee.fee_label || 'Application Fee'}
                            ${fee.category_name
                ? `<span class="indicator-pill blue"
                                    style="font-size:10px;margin-left:6px">
                                    ${fee.category_name}</span>`
                : ''}
                        </div>
                        <div style="font-size:28px;font-weight:700;
                            color:var(--portal-primary)">
                            &#8377; ${frappe.format(fee.fee_amount, { fieldtype: 'Currency' })}
                        </div>
                    </div>
                    <div style="display:flex;gap:10px;justify-content:center;">
                        <button class="btn btn-primary" id="pay-now-btn">
                            Pay Now
                        </button>
                        <button class="btn btn-default" id="pay-later-btn">
                            Pay Later
                        </button>
                    </div>
                    <p class="text-muted" style="font-size:11px;margin-top:12px">
                        You can also pay later from your application dashboard.
                    </p>
                </div>
            </div>
            ${renderFooter()}
        `);

        $body.find('#pay-now-btn').on('click', function () {
            // Payment gateway integration — Phase 9 external
            // For now show placeholder
            frappe.msgprint({
                title: 'Payment Gateway',
                message: 'Payment gateway integration is being configured. ' +
                    'Please contact admissions office for payment instructions.',
                indicator: 'blue'
            });
        });

        $body.find('#pay-later-btn').on('click', function () {
            frappe.show_alert({
                message: 'You can pay the fee from your dashboard.',
                indicator: 'orange'
            }, 5);
            state.applicant = { name: applicantName, application_status: 'Submitted' };
            renderDashboard();
        });
    }

    // ── DASHBOARD ────────────────────────────────────────────────
    async function renderDashboard() {
        $body.html('<div class="text-muted text-center" style="padding:40px">Loading dashboard...</div>');

        const applicantName = state.applicant.name || state.applicant;
        const [stageR, campusR] = await Promise.all([
            frappe.call({ method: 'slcm.admission.utils.portal.api_get_stage_progress', args: { applicant: applicantName } }),
            frappe.call({ method: 'slcm.admission.utils.portal.api_get_campus_status', args: { applicant: applicantName } })
        ]);

        const stages = stageR.message || [];
        const campuses = campusR.message || [];
        const appStatus = state.applicant.application_status || 'Submitted';
        const statusColors = { Draft: 'yellow', Submitted: 'blue', Locked: 'grey', Accepted: 'green', Rejected: 'red' };

        const annsHtml = buildAnnouncementsSection(state.announcements);

        const stageHtml = state.config.show_stage_progress && stages.length
            ? `<div class="frappe-card" style="padding:20px;margin-bottom:16px;">
                <h6 style="color:var(--portal-primary);margin-bottom:12px">Admission Progress</h6>
                ${stages.map(s => `
                    <div class="portal-stage-row">
                        <div class="stage-dot ${s.status.toLowerCase()}"></div>
                        <div style="flex:1">
                            <div style="font-weight:600;font-size:13px">${s.stage_name}</div>
                            <div style="font-size:11px;color:var(--text-muted)">${s.stage_type}</div>
                        </div>
                        <span class="indicator-pill ${s.status === 'Active' ? 'blue' : s.status === 'Completed' ? 'green' : 'gray'}"
                            style="font-size:11px">${s.status}</span>
                    </div>`).join('')}
              </div>` : '';

        const campusHtml = campuses.length > 1
            ? `<div class="frappe-card" style="padding:20px;margin-bottom:16px;">
                <h6 style="color:var(--portal-primary);margin-bottom:12px">Campus Status</h6>
                <table class="table table-bordered table-sm" style="font-size:13px">
                    <thead class="thead-light"><tr>
                        <th>Pref</th><th>Campus</th><th>Program</th><th>Status</th>
                    </tr></thead>
                    <tbody>${campuses.map(c => `<tr>
                        <td>#${c.preference_order}</td><td>${c.campus_name}</td>
                        <td>${c.program}</td>
                        <td><span class="indicator-pill ${c.status === 'Offered' ? 'green' : c.status === 'Rejected' ? 'red' : 'blue'}">${c.status}</span></td>
                    </tr>`).join('')}</tbody>
                </table>
              </div>` : '';

        $body.html(`
            <div style="max-width:900px;margin:0 auto;padding:20px;">
                ${buildHeaderBar()}
                <div class="frappe-card" style="padding:20px;margin-bottom:16px;
                    background:var(--portal-primary);color:#fff;border:none;">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
                        <div>
                            <h4 style="margin:0;color:#fff">${state.config.portal_title || 'My Application'}</h4>
                            <div style="opacity:0.85;font-size:13px;margin-top:4px">ID: ${applicantName}</div>
                        </div>
                        <span class="indicator-pill ${statusColors[appStatus] || 'blue'}"
                            style="font-size:13px">${appStatus}</span>
                    </div>
                </div>
                ${stageHtml}
                ${campusHtml}
                <div class="frappe-card" style="padding:20px;margin-bottom:16px;">
                    <h6 style="color:var(--portal-primary);margin-bottom:12px">Quick Actions</h6>
                    <div style="display:flex;flex-wrap:wrap;gap:10px;">
                        ${state.config.allow_pdf_download
                ? '<button class="btn btn-default btn-sm" id="dl-pdf">Download Application</button>' : ''}
                        <button class="btn btn-default btn-sm">My Documents</button>
                    </div>
                </div>
                ${annsHtml}
            </div>
            ${renderFooter()}
        `);

        bindBellEvents();

        $body.find('#dl-pdf').on('click', async function () {
            $(this).text('Generating...');
            const r = await frappe.call({
                method: 'slcm.admission.utils.portal.api_download_pdf',
                args: { applicant: applicantName }
            });
            if (r.message && r.message.success) window.open(r.message.file_url, '_blank');
            else frappe.show_alert({ message: 'Could not generate PDF.', indicator: 'red' }, 4);
            $(this).text('Download Application');
        });

        $body.find('.ann-card').on('click', function () {
            const name = $(this).data('ann');
            const ann = state.announcements.find(a => a.name === name);
            if (ann) openDrawer(ann);
        });
    }

    // ── OPEN ANNOUNCEMENT DRAWER BY NAME ─────────────────────────
    function openAnnouncementDrawer(ann_name) {
        if (!ann_name) return;

        frappe.call({
            method: "slcm.admission.utils.portal.api_get_announcement_detail",
            args: { name: ann_name },
            callback: function (r) {
                const ann = r.message;
                if (!ann) return;

                const isEvent = ann.announcement_type === "Event";
                const countdown = isEvent ? getCountdown(ann.event_date) : null;
                const imgHtml = ann.featured_image
                    ? `<img class="drawer-img" src="${ann.featured_image}" alt="${ann.title}">` : "";
                const eventHtml = isEvent ? `
                    <div class="frappe-card" style="padding:14px;margin-bottom:16px;font-size:13px;">
                        ${ann.event_date ? `<div><strong>Date:</strong> ${ann.event_date}</div>` : ""}
                        ${ann.event_venue ? `<div style="margin-top:4px"><strong>Venue:</strong> ${ann.event_venue}</div>` : ""}
                        ${countdown ? `<div class="ann-countdown" style="margin-top:8px">${countdown}</div>` : ""}
                        ${ann.registration_url ? `<a href="${ann.registration_url}" target="_blank"
                            class="btn btn-primary btn-sm" style="margin-top:12px">Register</a>` : ""}
                    </div>` : "";

                // Remove any existing drawer
                $("#portal-drawer-backdrop, #portal-drawer").remove();

                const $backdrop = $('<div class="portal-drawer-backdrop" id="portal-drawer-backdrop"></div>');
                const $drawer = $(`<div class="portal-drawer" id="portal-drawer">
                    <div class="drawer-header">
                        <div>
                            <div class="ann-type-badge ${isEvent ? "event" : "announcement"}"
                                style="margin-bottom:6px">
                                ${isEvent ? "Event" : "Announcement"}
                            </div>
                            <h4>${ann.title}</h4>
                        </div>
                        <button class="drawer-close-btn" id="drawer-close">&times;</button>
                    </div>
                    <div class="drawer-body">
                        ${imgHtml}
                        ${eventHtml}
                        <div style="font-size:14px;line-height:1.7">${ann.content || ""}</div>
                    </div>
                </div>`);

                $("body").append($backdrop).append($drawer);
                setTimeout(() => $drawer.addClass("open"), 20);

                $backdrop.on("click", closeDrawer);
                $("#drawer-close").on("click", closeDrawer);

                // Mark as read in bell (localStorage)
                markBellRead(ann_name);
            }
        });
    }

    init();
};
