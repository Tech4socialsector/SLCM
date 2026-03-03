frappe.pages["applicant-results"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "My Results & Scholarships",
        single_column: true,
    });

    const $body = $(wrapper).find(".layout-main-section");

    // Inject CSS
    const style = document.createElement("style");
    style.id = "ar-style";
    style.textContent = `
        #ar-wrap {
            font-family: 'Inter', 'Segoe UI', sans-serif;
            max-width: 1100px;
            margin: 0 auto;
            padding: 8px 4px 40px;
        }
        .ar-header {
            background: linear-gradient(135deg, #1a237e 0%, #283593 60%, #3949ab 100%);
            border-radius: 16px;
            padding: 28px 32px;
            color: #fff;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 18px;
            box-shadow: 0 8px 32px rgba(26,35,126,0.2);
        }
        .ar-header-icon { font-size: 44px; }
        .ar-header h2 { margin: 0 0 4px; font-size: 1.5rem; font-weight: 700; color: #fff; }
        .ar-header p { margin: 0; opacity: 0.82; font-size: 0.9rem; }
        .ar-status-badge {
            display: inline-block;
            padding: 2px 11px; border-radius: 20px;
            font-size: 0.74rem; font-weight: 700;
            margin-left: 8px; vertical-align: middle;
        }
        .ar-status-badge.selected { background:#00c853;color:#fff; }
        .ar-status-badge.offered   { background:#2979ff;color:#fff; }
        .ar-status-badge.waitlisted{ background:#ff6d00;color:#fff; }
        .ar-status-badge.rejected  { background:#d50000;color:#fff; }
        .ar-status-badge.submitted { background:#607d8b;color:#fff; }
        .ar-status-badge.def       { background:#90a4ae;color:#fff; }
        .ar-card {
            background: var(--card-bg, #fff);
            border-radius: 12px;
            border: 1px solid var(--border-color, #e8eaf0);
            padding: 22px 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .ar-sec-title {
            font-size: 1rem; font-weight: 700;
            color: #1a237e; margin: 0 0 14px;
            display: flex; align-items: center; gap: 7px;
        }
        .ar-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 14px;
        }
        .ar-stat {
            background: #f3f4f8; border-radius: 10px;
            padding: 14px 10px; text-align: center;
        }
        .ar-stat-val {
            font-size: 1.7rem; font-weight: 800;
            color: #1a237e; line-height: 1;
        }
        .ar-stat-lbl {
            font-size: 0.72rem; color: #607d8b; margin-top: 4px;
            font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
        }
        .ar-rank-circle {
            display: inline-flex; align-items: center; justify-content: center;
            width: 50px; height: 50px; border-radius: 50%;
            background: linear-gradient(135deg,#ffd700,#ff8f00);
            color: #fff; font-size: 1rem; font-weight: 900;
            margin: 0 auto 4px;
            box-shadow: 0 4px 12px rgba(255,143,0,0.3);
        }
        .ar-empty {
            text-align: center; padding: 28px; color: #90a4ae;
        }
        .ar-empty-icon { font-size: 2.5rem; margin-bottom: 8px; }
        .ar-seat-row {
            display: flex; flex-wrap: wrap; gap: 20px; margin-top: 10px;
        }
        .ar-seat-field label {
            display: block; font-size: 0.72rem;
            text-transform: uppercase; color: #90a4ae;
            letter-spacing: 0.05em; font-weight: 600; margin-bottom: 2px;
        }
        .ar-seat-field span { font-size: 0.95rem; font-weight: 600; color: #263238; }
        .ar-sch-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 14px; margin-top: 10px;
        }
        .ar-sch-card {
            border: 1px solid var(--border-color, #e8eaf0);
            border-radius: 10px; padding: 16px 18px;
            background: #fafbfc;
            transition: box-shadow 0.2s, transform 0.2s;
        }
        .ar-sch-card:hover { box-shadow: 0 6px 18px rgba(26,35,126,0.09); transform:translateY(-2px); }
        .ar-sch-card h4 { margin: 0 0 5px; font-size: 0.92rem; font-weight: 700; color: #1a237e; }
        .ar-type-tag {
            display: inline-block; padding: 2px 9px;
            border-radius: 10px; font-size: 0.69rem;
            font-weight: 700; margin-bottom: 8px;
            text-transform: uppercase; letter-spacing: 0.04em;
        }
        .ar-type-tag.need   { background:#e3f2fd;color:#1565c0; }
        .ar-type-tag.merit  { background:#f3e5f5;color:#6a1b9a; }
        .ar-type-tag.government { background:#e8f5e9;color:#2e7d32; }
        .ar-type-tag.other  { background:#fff3e0;color:#e65100; }
        .ar-sch-coverage { font-size: 0.84rem; color:#455a64; margin-bottom:12px; }
        .ar-apply-btn {
            display:block; width:100%; padding:7px 0;
            background: linear-gradient(90deg,#1a237e,#3949ab);
            color:#fff; border:none; border-radius:7px;
            font-size:0.84rem; font-weight:600; cursor:pointer;
            text-align:center; text-decoration:none;
            transition:opacity 0.2s;
        }
        .ar-apply-btn:hover { opacity:0.88; color:#fff; }
        .ar-applied-tag {
            display:block; width:100%; padding:7px 0;
            border-radius:7px; font-size:0.82rem; font-weight:600;
            text-align:center; background:#e8f5e9; color:#2e7d32;
        }
        .ar-apps-table {
            width:100%; border-collapse:collapse;
            margin-top:10px; font-size:0.88rem;
        }
        .ar-apps-table th {
            background:#f3f4f8; padding:9px 12px;
            text-align:left; font-size:0.72rem;
            font-weight:700; text-transform:uppercase;
            color:#607d8b; letter-spacing:0.04em;
        }
        .ar-apps-table td { padding:9px 12px; border-top:1px solid #f0f0f0; color:#37474f; }
        .ar-pill {
            display:inline-block; padding:2px 9px;
            border-radius:20px; font-size:0.73rem; font-weight:600;
        }
        .ar-pill.approved { background:#e8f5e9;color:#2e7d32; }
        .ar-pill.submitted { background:#e3f2fd;color:#1565c0; }
        .ar-pill.rejected { background:#ffebee;color:#c62828; }
        .ar-pill.under-review { background:#fff3e0;color:#e65100; }
        .ar-pill.revoked { background:#fce4ec;color:#880e4f; }
        .ar-pill.draft { background:#f5f5f5;color:#616161; }
    `;
    if (document.getElementById("ar-style")) document.getElementById("ar-style").remove();
    document.head.appendChild(style);

    $body.html(`<div id="ar-wrap">
        <div style="text-align:center;padding:60px;color:#90a4ae;">
            <div style="font-size:2.5rem;margin-bottom:12px;">⏳</div>
            <div>Loading your results...</div>
        </div>
    </div>`);

    frappe.call({
        method: "slcm.admission.page.applicant_results.applicant_results.get_my_results",
        callback: function (r) {
            const data = r && r.message;
            if (!data || data.error) {
                $("#ar-wrap").html(`<div class="ar-empty">
                    <div class="ar-empty-icon">🔍</div>
                    <p>${(data && data.error) || "No applicant record linked to this account."}</p>
                </div>`);
                return;
            }
            render(data);
        },
        error: function () {
            $("#ar-wrap").html(`<div class="ar-empty">
                <div class="ar-empty-icon">⚠️</div>
                <p>Failed to load results. Please refresh the page.</p>
            </div>`);
        }
    });

    function render(data) {
        const a = data.applicant || {};
        window._ar_applicant = a;   // used by ar_open_apply_dialog
        const merit = data.merit;
        const seat = data.seat_allocation;
        const schs = data.scholarships || [];
        const apps = data.my_scholarship_applications || [];

        const st = (a.application_status || "").toLowerCase();
        const badge_cls = ["selected", "offered", "waitlisted", "rejected", "submitted"].includes(st) ? st : "def";

        let html = `<div id="ar-wrap">
        <!-- HEADER -->
        <div class="ar-header">
            <div class="ar-header-icon">🎓</div>
            <div>
                <h2>${esc(a.candidate_name || "Applicant")}
                    <span class="ar-status-badge ${badge_cls}">${a.application_status || ""}</span>
                </h2>
                <p>${esc(a.email || "")} &bull; Cycle: <strong>${a.admission_cycle || "N/A"}</strong> &bull; Program: <strong>${a.program || "N/A"}</strong></p>
            </div>
        </div>

        <!-- MERIT -->
        <div class="ar-card">
            <div class="ar-sec-title"><span>🏆</span> Merit Score &amp; Ranking</div>
            ${render_merit(merit)}
        </div>

        <!-- SEAT -->
        <div class="ar-card">
            <div class="ar-sec-title"><span>💺</span> Seat Allocation</div>
            ${render_seat(seat)}
        </div>

        <!-- SCHOLARSHIPS -->
        <div class="ar-card">
            <div class="ar-sec-title"><span>🎁</span> Available Scholarships
                <span style="font-size:0.78rem;font-weight:500;color:#607d8b;">(${schs.length} available)</span>
            </div>
            ${render_scholarships(schs, apps, a)}
        </div>

        <!-- MY APPLICATIONS -->
        ${apps.length ? `<div class="ar-card">
            <div class="ar-sec-title"><span>📄</span> My Scholarship Applications</div>
            ${render_apps(apps)}
        </div>` : ""}
        </div>`;

        $("#ar-wrap").replaceWith(html);
    }

    function render_merit(m) {
        if (!m) return `<div class="ar-empty">
            <div class="ar-empty-icon">📊</div>
            <p>Merit list not yet published for your program.</p></div>`;

        const fields = [
            { label: "Overall Rank", val: m.overall_rank, rank: true },
            { label: "Program Rank", val: m.program_rank },
            { label: "Category Rank", val: m.category_rank },
            { label: "Total Score", val: fmt(m.total_score), color: "#2e7d32" },
        ];
        if (m.hsc_percentage) fields.push({ label: "HSC %", val: fmt(m.hsc_percentage) + "%" });
        if (m.entrance_percentage) fields.push({ label: "Entrance %", val: fmt(m.entrance_percentage) + "%" });
        if (m.interview_percentage) fields.push({ label: "Interview %", val: fmt(m.interview_percentage) + "%" });
        if (m.ug_cgpa) fields.push({ label: "UG CGPA", val: fmt(m.ug_cgpa) });
        if (m.pg_cgpa) fields.push({ label: "PG CGPA", val: fmt(m.pg_cgpa) });

        const cards = fields.map(f => {
            const inner = f.rank
                ? `<div class="ar-rank-circle">#${f.val || "–"}</div>`
                : `<div class="ar-stat-val" style="${f.color ? 'color:' + f.color : ''}">${f.val !== null && f.val !== undefined ? f.val : "–"}</div>`;
            return `<div class="ar-stat">${inner}<div class="ar-stat-lbl">${f.label}</div></div>`;
        });

        return `<div class="ar-grid">${cards.join("")}</div>
        <div style="margin-top:10px;font-size:0.8rem;color:#90a4ae;">
            Status: <strong>${m.merit_status || "N/A"}</strong> &bull;
            Type: <strong>${m.program_level || "N/A"}</strong> &bull;
            Generated: <strong>${m.generated_on ? frappe.datetime.str_to_user(m.generated_on) : "N/A"}</strong>
        </div>`;
    }

    function render_seat(seat) {
        if (!seat) return `<div class="ar-empty">
            <div class="ar-empty-icon">💺</div>
            <p>No seat allocated yet. You will be notified once seat allocation is finalised.</p></div>`;

        const sel_color = {
            "Selected": "#2e7d32", "Offer Issued": "#1565c0",
            "Accepted": "#1b5e20", "Fee Paid": "#00695c"
        }[seat.selection_status] || "#2e7d32";

        return `
        <div style="background:#e8f5e9;border-radius:10px;padding:14px 18px;margin-bottom:14px;border-left:4px solid ${sel_color};">
            <div style="font-size:1.1rem;font-weight:800;color:${sel_color};">✅ ${seat.selection_status || seat.status}</div>
            <div style="font-size:0.84rem;color:#455a64;margin-top:3px;">Seat allocation published</div>
        </div>
        <div class="ar-seat-row">
            <div class="ar-seat-field"><label>Program</label><span>${seat.program || "N/A"}</span></div>
            <div class="ar-seat-field"><label>Campus</label><span>${seat.campus || "N/A"}</span></div>
            <div class="ar-seat-field"><label>Cycle</label><span>${seat.admission_cycle || "N/A"}</span></div>
            <div class="ar-seat-field"><label>Published On</label><span>${seat.published_on ? frappe.datetime.str_to_user(seat.published_on) : "N/A"}</span></div>
            <div class="ar-seat-field"><label>Reference</label><span>${seat.name || "N/A"}</span></div>
        </div>`;
    }

    // Global registry populated by render_scholarships — avoids extra API call
    window._ar_schemes = {};

    function render_scholarships(schs, apps, ap) {
        if (!schs.length) return `<div class="ar-empty">
            <div class="ar-empty-icon">🎁</div>
            <p>No scholarships currently available for your profile. Check back after your status is updated.</p></div>`;

        // Store scheme metadata for dialog use (no extra API call)
        schs.forEach(s => { window._ar_schemes[s.name] = s; });

        const applied = (apps || []).map(a => a.scholarship_scheme);
        const cards = schs.map(s => {
            const type = (s.scheme_type || "other").toLowerCase().replace(" ", "-");
            let cov = "";
            if (s.coverage_type === "Percentage") cov = `${s.coverage_value || 0}% coverage`;
            else if (s.coverage_type === "Fixed") cov = `₹${frappe.format(s.coverage_value || 0, { fieldtype: "Currency" })} fixed`;
            else cov = "Component-wise";
            if (s.apply_on) cov += ` on ${s.apply_on}`;

            const is_applied = applied.includes(s.name);
            const safe_name = s.name.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
            const action = is_applied
                ? `<span class="ar-applied-tag">✓ Already Applied</span>`
                : `<button class="ar-apply-btn" onclick="ar_open_apply_dialog('${safe_name}')">Apply Now →</button>`;

            return `<div class="ar-sch-card">
                <h4>${esc(s.scheme_name || s.name)}</h4>
                <span class="ar-type-tag ${type}">${s.scheme_type || "Scheme"}</span>
                <div class="ar-sch-coverage">${cov}</div>
                ${action}
            </div>`;
        });
        return `<div class="ar-sch-grid">${cards.join("")}</div>`;
    }

    // ── INLINE APPLY DIALOG ──
    // Uses data from window._ar_schemes — no permission-restricted API call needed
    window.ar_open_apply_dialog = function (scheme_name) {
        const s = window._ar_schemes[scheme_name];
        if (!s) { frappe.msgprint(__("Scheme data not found. Please refresh the page.")); return; }

        const is_need = s.scheme_type === "Need" && s.income_certificate_required;
        const doc_label = s.scheme_type === "Merit"
            ? "Merit/Achievement Documents (Optional)"
            : s.scheme_type === "Government"
                ? "Category/Caste Certificate (Optional)"
                : "Supporting Documents (Optional)";

        const ap = window._ar_applicant || {};
        const cov_text = s.coverage_type === "Percentage"
            ? `${s.coverage_value || 0}% of ${s.apply_on || "Fee"}`
            : s.coverage_type === "Fixed"
                ? `₹${s.coverage_value || 0} fixed`
                : "Component-wise";

        // Info section — scheme details + applicant preview (read-only)
        const info_html = `
            <div style="background:#f0f4ff;border-radius:8px;padding:14px 16px;margin-bottom:8px;border-left:4px solid #1a237e;">
                <div style="font-weight:700;color:#1a237e;font-size:1rem;">${frappe.utils.escape_html(s.scheme_name || s.name)}</div>
                <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:8px;font-size:0.84rem;color:#37474f;">
                    <span>📋 <b>Type:</b> ${s.scheme_type || "N/A"}</span>
                    <span>💰 <b>Coverage:</b> ${cov_text}</span>
                </div>
            </div>
            <div style="background:#f9f9f9;border-radius:8px;padding:12px 16px;margin-bottom:10px;font-size:0.84rem;">
                <div style="font-weight:600;color:#455a64;margin-bottom:8px;font-size:0.82rem;text-transform:uppercase;letter-spacing:0.04em;">📌 Application Details (auto-filled)</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 20px;">
                    <div><div style="font-size:0.72rem;color:#90a4ae;">APPLICANT</div><div style="font-weight:600;color:#263238;">${frappe.utils.escape_html(ap.candidate_name || ap.name || "—")}</div></div>
                    <div><div style="font-size:0.72rem;color:#90a4ae;">ADMISSION CYCLE</div><div style="font-weight:600;color:#263238;">${frappe.utils.escape_html(ap.admission_cycle || "—")}</div></div>
                    <div><div style="font-size:0.72rem;color:#90a4ae;">PROGRAM</div><div style="font-weight:600;color:#263238;">${frappe.utils.escape_html(ap.program || "—")}</div></div>
                    <div><div style="font-size:0.72rem;color:#90a4ae;">CAMPUS</div><div style="font-weight:600;color:#263238;">${frappe.utils.escape_html(ap.campus || "—")}</div></div>
                </div>
            </div>`;

        const fields = [
            { fieldtype: "HTML", options: info_html }
        ];

        if (is_need) {
            const stored_income = frappe.utils.flt(ap.annual_house_hold_income || 0);
            fields.push(
                {
                    fieldtype: "Currency",
                    fieldname: "family_income",
                    label: "Annual Family Income (₹)",
                    reqd: 1,
                    default: stored_income || undefined,
                    description: stored_income
                        ? `Pre-filled from your applicant record. Edit if it has changed.`
                        : "Enter your family's total annual income"
                },
                {
                    fieldtype: "Attach",
                    fieldname: "income_certificate",
                    label: "Income Certificate",
                    reqd: 1,
                    description: "Upload income certificate issued by a government authority (PDF/JPG/PNG)"
                }
            );
        }

        fields.push({
            fieldtype: "Attach",
            fieldname: "supporting_documents",
            label: doc_label,
            reqd: 0,
            description: "Any additional documents to support your application"
        });

        const dialog = new frappe.ui.Dialog({
            title: __('Apply for Scholarship'),
            fields: fields,
            primary_action_label: __('Submit Application'),
            primary_action(values) {
                dialog.disable_primary_action();
                frappe.call({
                    method: "slcm.admission.page.applicant_results.applicant_results.apply_for_scholarship",
                    args: {
                        scheme: scheme_name,
                        family_income: values.family_income || 0,
                        income_certificate: values.income_certificate || "",
                        supporting_documents: values.supporting_documents || ""
                    },
                    freeze: true,
                    freeze_message: __('Submitting your application...'),
                    callback(res) {
                        dialog.hide();
                        if (res.message && res.message.name) {
                            frappe.show_alert({
                                message: `✅ Application <b>${res.message.name}</b> submitted!`,
                                indicator: "green"
                            }, 6);
                            setTimeout(() => location.reload(), 1500);
                        }
                    },
                    error() { dialog.enable_primary_action(); }
                });
            }
        });
        dialog.show();
    };

    function render_apps(apps) {
        const rows = apps.map(a => {
            const st = (a.status || "").toLowerCase().replace(/ /g, "-");
            const amt = a.calculated_benefit ? `₹${frappe.format(a.calculated_benefit, { fieldtype: "Currency" })}` : "—";
            return `<tr>
                <td>${esc(a.scholarship_scheme || "")}</td>
                <td><span class="ar-pill ${st}">${a.status || ""}</span></td>
                <td>${amt}</td>
                <td>${a.creation ? frappe.datetime.str_to_user(a.creation.split(" ")[0]) : ""}</td>
            </tr>`;
        });
        return `<table class="ar-apps-table">
            <thead><tr>
                <th>Scheme</th><th>Status</th><th>Benefit</th><th>Applied On</th>
            </tr></thead>
            <tbody>${rows.join("")}</tbody>
        </table>`;
    }

    function esc(s) { return frappe.utils.escape_html(s || ""); }
    function fmt(v) {
        if (v === null || v === undefined) return "–";
        const n = parseFloat(v);
        return isNaN(n) ? v : (Number.isInteger(n) ? n : n.toFixed(2));
    }
};
