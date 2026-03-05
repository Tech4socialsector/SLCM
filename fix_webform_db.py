import frappe

def run():
    css = """
/* ── Admission Navbar ───────────────────────────────────────── */
.web-header-bar, .navbar, .web-form-header,
header.navbar, #navbar-main { display: none !important; }

.page-content { padding-top: 0 !important; margin-top: 0 !important; }
.main-section  { padding-top: 0 !important; }

/* ── Admission nav bar ──────────────────────────────────────── */
#adm-nav-inject {
    background: var(--adm-primary, #1a3c6e);
    padding: 0 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 60px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    font-family: 'Segoe UI', system-ui, sans-serif;
}
#adm-nav-inject a {
    color: rgba(255,255,255,0.85);
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
}
#adm-nav-inject a:hover { color: #fff; }
.adm-nav-brand {
    font-size: 17px;
    font-weight: 700;
    color: #fff !important;
    display: flex;
    align-items: center;
    gap: 10px;
}
.adm-nav-links {
    display: flex;
    gap: 20px;
    align-items: center;
}
.adm-nav-btn {
    background: #c8a14b;
    color: #fff !important;
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
}

/* ── Stage Tracker ──────────────────────────────────────────── */
#stage-tracker-wrap {
    background: #fff;
    border-radius: 12px;
    padding: 20px 24px 12px;
    margin: 20px 0 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    border: 1px solid #e9ecef;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
.st-tracker-title {
    font-size: 12px;
    font-weight: 600;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
}
.st-rail {
    display: flex;
    align-items: flex-start;
    overflow-x: auto;
    padding-bottom: 6px;
    scrollbar-width: thin;
    scrollbar-color: #dee2e6 transparent;
}
.st-rail::-webkit-scrollbar { height: 3px; }
.st-rail::-webkit-scrollbar-thumb { background: #dee2e6; border-radius: 3px; }
.st-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex-shrink: 0;
    min-width: 80px;
    max-width: 100px;
}
.st-circle {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
    border: 2px solid #dee2e6;
    background: #fff; color: #6c757d;
    position: relative; z-index: 1;
    transition: all 0.3s;
}
.st-completed .st-circle { background:#065f46; border-color:#065f46; color:#fff; }
.st-active    .st-circle {
    background:#1a3c6e; border-color:#1a3c6e; color:#fff;
    box-shadow: 0 0 0 4px rgba(26,60,110,0.15);
}
.st-rejected   .st-circle { background:#dc2626; border-color:#dc2626; color:#fff; }
.st-waitlisted .st-circle { background:#f59e0b; border-color:#f59e0b; color:#fff; }

.st-pulse {
    position: absolute;
    width: 44px; height: 44px;
    border-radius: 50%;
    border: 2px solid #1a3c6e;
    opacity: 0;
    animation: stPulse 2s ease-out infinite;
    top: -6px; left: -6px;
}
 @keyframes stPulse {
    0%   { transform: scale(0.8); opacity: 0.6; }
    100% { transform: scale(1.4); opacity: 0; }
}
.st-connector {
    flex: 1; height: 2px; min-width: 20px;
    margin-top: 17px; align-self: flex-start;
}
.st-line-done    { background: #065f46; }
.st-line-active  { background: repeating-linear-gradient(
    90deg, #1a3c6e 0 6px, transparent 6px 12px); }
.st-line-pending { background: #dee2e6; }
.st-label {
    text-align: center; margin-top: 6px;
}
.st-stage-name {
    font-size: 10px; font-weight: 600; color: #1a1a2e;
    line-height: 1.3; max-width: 80px;
    word-break: break-word;
}
.st-pending   .st-stage-name { color: #6c757d; font-weight: 400; }
.st-completed .st-stage-name { color: #065f46; }
.st-active    .st-stage-name { color: #1a3c6e; font-weight: 700; }
.st-rejected  .st-stage-name { color: #dc2626; }
.st-stage-date { font-size: 9px; color: #6c757d; margin-top: 2px; }
.st-action-btn {
    display: inline-block; margin-top: 5px;
    padding: 3px 8px; background: #c8a14b;
    color: #fff; border-radius: 4px;
    font-size: 9px; font-weight: 700;
    text-decoration: none;
}
.st-banner {
    padding: 10px 14px; border-radius: 8px;
    font-size: 12px; font-weight: 500; margin-bottom: 14px;
}
.st-banner-rejected   { background:#fee2e2; color:#991b1b; border-left:4px solid #dc2626; }
.st-banner-waitlisted { background:#fef3c7; color:#92400e; border-left:4px solid #f59e0b; }
.st-banner-offer      { background:#d1fae5; color:#065f46; border-left:4px solid #10b981; }
.st-empty { padding:20px; text-align:center; color:#6c757d; font-size:12px; }
.st-loading { padding:20px; text-align:center; color:#6c757d; font-size:12px; }

 @media (max-width: 600px) {
    .st-node  { min-width: 56px; max-width: 68px; }
    .st-circle { width:28px; height:28px; font-size:11px; }
    .st-connector { margin-top:13px; }
    .st-stage-date { display:none; }
}
"""

    js = """
/* ── Inject Admission Navbar ─────────────────────────────── */
(function injectNav() {
    if (document.getElementById('adm-nav-inject')) return;
    var nav = document.createElement('div');
    nav.id = 'adm-nav-inject';
    nav.innerHTML = [
        '<a href="/admission" class="adm-nav-brand">Admissions</a>',
        '<div class="adm-nav-links">',
        '  <a href="/admission">Programs</a>',
        '  <a href="/my-applications">My Applications</a>',
        '  <a href="/me" class="adm-nav-btn">Account</a>',
        '</div>'
    ].join('');
    document.body.insertBefore(nav, document.body.firstChild);
})();

/* ── Stage Tracker ───────────────────────────────────────── */
var STATUS_CFG = {
    completed:  { cls: 'st-completed', line: 'st-line-done'    },
    active:     { cls: 'st-active',    line: 'st-line-active'  },
    pending:    { cls: 'st-pending',   line: 'st-line-pending' },
    rejected:   { cls: 'st-rejected',  line: 'st-line-done'    },
    waitlisted: { cls: 'st-waitlisted',line: 'st-line-active'  }
};

var TYPE_ICON = {
    'Application':'&#x1F4CB;','Screening':'&#x1F50D;','Exam':'&#x270F;&#xFE0F;',
    'Interview':'&#x1F3A4;','Evaluation':'&#x1F4CA;','Merit':'&#x1F3C6;',
    'Document':'&#x1F4C1;','Fee':'&#x1F4B3;','Enrollment':'&#x1F393;',''  :'&#x25CE;'
};

function escHtml(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderTracker(data) {
    var wrap = document.getElementById('stage-tracker-wrap');
    if (!wrap) return;

    var stages    = data.stages    || [];
    var trackType = data.track_type || 'normal';
    var status    = data.app_status || '';

    if (!stages.length) {
        wrap.innerHTML = '<div class="st-empty">No stages configured for this cycle.</div>';
        return;
    }

    var html = '<div class="st-tracker-title">Application Progress</div>';

    if (status === 'Rejected') {
        html += '<div class="st-banner st-banner-rejected">Application not shortlisted at this stage.</div>';
    } else if (trackType === 'waitlisted') {
        html += '<div class="st-banner st-banner-waitlisted">You are on the waitlist. We will notify you if a seat becomes available.</div>';
    } else if (status === 'Offer Issued' || status === 'Offer Accepted') {
        html += '<div class="st-banner st-banner-offer">Congratulations! An offer has been issued. Please accept before the deadline.</div>';
    }

    html += '<div class="st-rail">';
    stages.forEach(function(stage, idx) {
        var sc   = STATUS_CFG[stage.status] || STATUS_CFG.pending;
        var icon = TYPE_ICON[stage.stage_type] || TYPE_ICON[''];
        var seq  = stage.sequence || (idx + 1);

        html += '<div class="st-node ' + sc.cls + '">';
        html += '<div class="st-circle">';
        if (stage.status === 'completed') {
            html += '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>';
        } else if (stage.status === 'rejected') {
            html += '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
        } else if (stage.status === 'active') {
            html += '<div class="st-pulse"></div>' + seq;
        } else {
            html += seq;
        }
        html += '</div>';

        html += '<div class="st-label">';
        html += '<div style="font-size:13px;margin-bottom:2px;">' + icon + '</div>';
        html += '<div class="st-stage-name">' + escHtml(stage.stage_name) + '</div>';
        if (stage.reached_on) {
            html += '<div class="st-stage-date">' + escHtml(stage.reached_on) + '</div>';
        }
        if (stage.show_action && stage.action_label) {
            html += '<a href="' + escHtml(stage.action_url||'#') + '" class="st-action-btn">'
                 + escHtml(stage.action_label) + '</a>';
        }
        html += '</div></div>';

        if (idx < stages.length - 1) {
            html += '<div class="st-connector ' + sc.line + '"></div>';
        }
    });
    html += '</div>';
    wrap.innerHTML = html;

    // Scroll active into view
    var active = wrap.querySelector('.st-active');
    if (active) active.scrollIntoView({behavior:'smooth', inline:'center', block:'nearest'});
}

function loadTracker(applicantName) {
    var wrap = document.getElementById('stage-tracker-wrap');
    if (!wrap) return;
    if (!applicantName) {
        wrap.innerHTML = '<div class="st-empty">Save the form first to see progress.</div>';
        return;
    }
    wrap.innerHTML = '<div class="st-loading">Loading progress...</div>';
    fetch('/api/method/slcm.admission.utils.web.get_stage_tracker_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': frappe.csrf_token || ''
        },
        body: JSON.stringify({ applicant_name: applicantName })
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.message) renderTracker(d.message);
        else wrap.innerHTML = '<div class="st-empty">Could not load progress.</div>';
    })
    .catch(function() {
        wrap.innerHTML = '<div class="st-empty">Could not load progress.</div>';
    });
}

frappe.ready(function() {
    var webForm = document.querySelector('.web-form-container, .web-form, [data-web-form]');
    if (webForm && !document.getElementById('stage-tracker-wrap')) {
        var wrap = document.createElement('div');
        wrap.id = 'stage-tracker-wrap';
        webForm.parentNode.insertBefore(wrap, webForm);
    }

    var parts = window.location.pathname.split('/').filter(Boolean);
    var applicantName = parts.length >= 2 ? decodeURIComponent(parts[parts.length - 1]) : null;

    if (!applicantName && frappe.web_form && frappe.web_form.doc && frappe.web_form.doc.name) {
        applicantName = frappe.web_form.doc.name;
    }

    if (applicantName && applicantName !== 'new' && applicantName.startsWith('APP-')) {
        loadTracker(applicantName);
    }
});
"""

    frappe.db.set_value("Web Form", "applicant-form", {
        "is_standard": 0,
        "custom_css": css,
        "client_script": js
    })
    frappe.db.commit()
    print("SUCCESS — direct DB update applied to applicant-form")

if __name__ == "__main__":
    run()
