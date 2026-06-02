// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

// ── Gate state (loaded from server on refresh) ────────────────────────
let _gates = {};

frappe.ui.form.on("Faculty Portal User Preferences", {
    refresh(frm) {
        _lock_to_current_user(frm);
        _load_gates_and_render(frm);
    },
    theme_mode(frm) {
        _render_appearance_preview(frm);
    },
    primary_color_override(frm) {
        _render_appearance_preview(frm);
    },
    font_size_pref(frm) {
        _render_appearance_preview(frm);
    },
    layout_density_pref(frm) {
        _render_appearance_preview(frm);
    },
});


// ── Auto-lock the record to the current user ──────────────────────────
function _lock_to_current_user(frm) {
    if (frm.is_new() && !frm.doc.faculty_user) {
        frm.set_value("faculty_user", frappe.session.user);
    }

    const isAdmin = frappe.user.has_role("System Manager") || frappe.session.user === "Administrator";
    if (!isAdmin) {
        frm.set_df_property("faculty_user", "read_only", 1);
        frm.add_custom_button(__("Open Faculty Portal"), () => {
            window.open("/faculty-portal", "_blank");
        });
    }
}


// ── Load gate state, then render everything ───────────────────────────
function _load_gates_and_render(frm) {
    frappe.call({
        method: "slcm.slcm.doctype.faculty_portal_user_preferences.faculty_portal_user_preferences.get_my_preferences",
        callback(r) {
            if (r.message) {
                _gates = r.message.gates || {};
            }
            _apply_gates(frm);
            _render_gates_summary(frm);
            _render_appearance_preview(frm);
            _inject_styles();
        },
    });
}


// ── Grey-out / read-only fields that admin has not unlocked ───────────
function _apply_gates(frm) {
    const gateMap = {
        "allow_theme_override":         ["theme_mode", "primary_color_override"],
        "allow_font_size_override":     ["font_size_pref"],
        "allow_density_override":       ["layout_density_pref"],
        "allow_dashboard_customization":["hide_today_schedule", "hide_pending_evaluations",
                                         "hide_class_statistics", "hide_workload_summary",
                                         "hide_leave_status", "default_course_view"],
        "allow_notification_settings":  ["notify_assignment_submission", "notify_attendance_discrepancy",
                                         "notify_student_query", "notify_leave_request_update",
                                         "notify_marks_due", "email_digest_frequency"],
    };

    Object.entries(gateMap).forEach(([gate, fields]) => {
        const open = !!_gates[gate];
        fields.forEach(f => {
            frm.set_df_property(f, "read_only", open ? 0 : 1);
            frm.set_df_property(f, "description",
                open ? frm.fields_dict[f]?.df?.description
                     : "🔒 Locked by administrator — contact your portal admin to enable this setting.");
        });
    });
    frm.refresh_fields();
}


// ── Gates summary banner ──────────────────────────────────────────────
function _render_gates_summary(frm) {
    const section = frm.get_field("appearance_section");
    if (!section || !section.$wrapper) return;
    section.$wrapper.find(".fup-gates-banner").remove();

    const items = [
        { gate: "allow_theme_override",         label: "Theme", icon: "palette" },
        { gate: "allow_font_size_override",      label: "Font Size", icon: "text_fields" },
        { gate: "allow_density_override",        label: "Density", icon: "density_medium" },
        { gate: "allow_dashboard_customization", label: "Dashboard", icon: "dashboard_customize" },
        { gate: "allow_notification_settings",   label: "Notifications", icon: "notifications" },
        { gate: "allow_language_preference",     label: "Language", icon: "language" },
    ];

    const unlocked = items.filter(i => _gates[i.gate]);
    const locked   = items.filter(i => !_gates[i.gate]);

    if (!locked.length) return; // Everything open — no need for the banner

    const chips = items.map(i => {
        const open = !!_gates[i.gate];
        return `
        <span style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:12px;
              font-size:10px;font-weight:600;
              background:${open ? "#f0fdf4" : "#f9fafb"};
              border:1px solid ${open ? "#bbf7d0" : "#e5e7eb"};
              color:${open ? "#15803d" : "#9ca3af"};">
          <span style="font-family:'Material Symbols Outlined';font-size:13px;">${open ? "check_circle" : "lock"}</span>
          ${i.label}
        </span>`;
    }).join("");

    const html = `
    <div class="fup-gates-banner" style="margin:10px 0 4px;padding:10px 14px;
         background:#fafafa;border:1px solid #e5e7eb;border-radius:8px;">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
           color:#9ca3af;margin-bottom:7px;">Your Customization Permissions</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">${chips}</div>
      ${locked.length ? `
        <div style="margin-top:8px;font-size:10px;color:#9ca3af;">
          <span style="font-family:'Material Symbols Outlined';font-size:12px;vertical-align:middle;">info</span>
          ${locked.length} setting(s) are locked. Ask your portal administrator to enable them in
          <b>Faculty Portal Settings › Faculty Self-Service Permissions</b>.
        </div>` : ""}
    </div>`;

    $(html).prependTo(section.$wrapper);
}


// ── Appearance preview card ────────────────────────────────────────────
function _render_appearance_preview(frm) {
    const d = frm.doc;
    const section = frm.get_field("appearance_section");
    if (!section || !section.$wrapper) return;

    const mode       = d.theme_mode || "Follow Portal";
    const colorOver  = (d.primary_color_override || "").trim();
    const fontSize   = d.font_size_pref      || "Normal";
    const density    = d.layout_density_pref || "Normal";

    const isDark   = mode === "Dark";
    const previewBg   = isDark ? "#1e293b" : "#f0f2f5";
    const previewCard = isDark ? "#2d3748" : "#ffffff";
    const previewText = isDark ? "#f1f5f9" : "#111827";
    const previewSub  = isDark ? "#94a3b8" : "#6b7280";
    const accent = colorOver && _valid_hex(colorOver) ? colorOver : "#1e3a5f";

    const fsLabel = { "Small": "13px", "Normal": "14px", "Large": "15px" }[fontSize] || "14px";
    const densLabel = density === "Compact" ? "Reduced padding" : "Standard padding";

    const tagStyle = `display:inline-block;padding:2px 8px;border-radius:4px;font-size:9px;
                      font-weight:600;background:${accent}18;color:${accent};border:1px solid ${accent}33;`;

    const html = `
    <div class="fup-appearance-preview" style="padding:10px 0 4px;">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
           color:#9ca3af;margin-bottom:8px;">Your Portal Preview</div>
      <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start;">
        <div style="width:240px;border-radius:10px;overflow:hidden;border:1px solid ${isDark ? "#374151" : "#e5e7eb"};
             box-shadow:0 2px 10px rgba(0,0,0,0.1);">
          <div style="height:30px;background:${accent};display:flex;align-items:center;padding:0 10px;gap:8px;">
            <div style="width:16px;height:16px;background:rgba(255,255,255,0.2);border-radius:4px;"></div>
            <div style="width:55px;height:5px;background:rgba(255,255,255,0.35);border-radius:2px;"></div>
            <div style="flex:1;"></div>
            <div style="width:18px;height:18px;background:rgba(255,255,255,0.2);border-radius:50%;"></div>
          </div>
          <div style="padding:8px;background:${previewBg};display:flex;flex-direction:column;gap:4px;">
            <div style="height:6px;background:${previewSub}44;border-radius:2px;width:45%;margin-bottom:4px;"></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;">
              ${[0,1].map(i => `
              <div style="height:${density === "Compact" ? "24px" : "30px"};background:${previewCard};
                   border-radius:6px;border:1px solid ${isDark ? "#374151" : "#e5e7eb"};
                   padding:4px 6px;display:flex;flex-direction:column;justify-content:space-between;">
                <div style="height:3px;background:${["#16a34a","#0369a1"][i]};border-radius:2px;width:40%;"></div>
                <div style="height:${density === "Compact" ? "4px" : "5px"};background:${previewSub}33;border-radius:2px;"></div>
              </div>`).join("")}
            </div>
            <div style="height:${density === "Compact" ? "28px" : "36px"};background:${previewCard};
                 border-radius:6px;border:1px solid ${isDark ? "#374151" : "#e5e7eb"};"></div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;padding-top:4px;">
          <div>
            <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
                 color:#9ca3af;margin-bottom:5px;">Active Settings</div>
            <div style="display:flex;flex-wrap:wrap;gap:5px;">
              <span style="${tagStyle}">Mode: ${mode}</span>
              <span style="${tagStyle}">Font: ${fsLabel}</span>
              <span style="${tagStyle}">${densLabel}</span>
              ${colorOver && _valid_hex(colorOver) ? `<span style="${tagStyle}">Color: ${colorOver}</span>` : ""}
            </div>
          </div>
          ${!_gates.allow_theme_override && !_gates.allow_font_size_override && !_gates.allow_density_override ? `
          <div style="padding:8px 10px;background:#fef9c3;border:1px solid #fde68a;border-radius:6px;
               font-size:10px;color:#92400e;max-width:200px;">
            <span style="font-family:'Material Symbols Outlined';font-size:13px;vertical-align:middle;">lock</span>
            Appearance customization is disabled by your administrator.
          </div>` : ""}
        </div>
      </div>
    </div>`;

    let el = section.$wrapper.find(".fup-appearance-preview");
    if (!el.length) {
        el = $('<div class="fup-appearance-preview"></div>').appendTo(section.$wrapper);
    }
    el.replaceWith(html);
}


// ── Helpers ────────────────────────────────────────────────────────────
function _valid_hex(color) {
    return /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test((color || "").trim());
}

function _inject_styles() {
    if (document.getElementById("fup-styles")) return;
    $("<style id='fup-styles'>").text(`
        .fup-appearance-preview { padding: 10px 0 4px; }
    `).appendTo("head");
}
