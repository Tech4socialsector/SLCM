frappe.pages["admission-setup-wizard"].on_page_load = function(wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: "Admission Setup Wizard",
        single_column: true
    });
    frappe.call({
        method: "slcm.admission.page.admission_setup_wizard.admission_setup_wizard.get_wizard_state",
        callback: function(r) {
            if (r.message) {
                new AdmissionWizard(wrapper, r.message);
            }
        }
    });
};

class AdmissionWizard {
    constructor(wrapper, state) {
        this.wrapper = wrapper;
        this.state = state;
        this.draft = state.draft || {};
        this.current_step = 1;
        this.total_steps = 9;
        this.completed_steps = new Set(
            Object.entries(state.step_status || {})
                .filter(([k,v]) => v)
                .map(([k]) => parseInt(k))
        );
        this.render();
    }

    steps_meta() {
        return [
            {num:1, label:"Institution Profile", icon:"🏛️"},
            {num:2, label:"Campus Mode",         icon:"🏫"},
            {num:3, label:"Exam Types",          icon:"📝"},
            {num:4, label:"Quota & Reservation", icon:"⚖️"},
            {num:5, label:"Admission Stages",    icon:"🔄"},
            {num:6, label:"Documents",           icon:"📄"},
            {num:7, label:"Email Templates",     icon:"📧"},
            {num:8, label:"App Form",            icon:"📋"},
            {num:9, label:"Review & Activate",   icon:"🚀"}
        ];
    }

    steps_config() {
        const ex = this.state.existing || {};
        return [
            {
                num:1, title:"Institution Profile", icon:"🏛️",
                desc:"Your institution's basic details and branding.",
                type:"fields",
                fields:[
                    {label:"Institution Name", name:"institution_name",
                     type:"text", reqd:true,
                     placeholder:"e.g. National Law School of India University"},
                    {label:"Institution Code", name:"institution_code",
                     type:"text", reqd:true, placeholder:"e.g. NLSIU"},
                    {label:"Support Email", name:"support_email",
                     type:"email", reqd:true,
                     placeholder:"admissions@university.ac.in"},
                    {label:"Compliance Mode", name:"compliance_mode",
                     type:"select", reqd:true,
                     options:["India","International","Both"],
                     help:"India = RTI/NAAC | International = GDPR | Both = All"},
                    {label:"Portal Theme Color", name:"portal_theme_color",
                     type:"color"}
                ]
            },
            {
                num:2, title:"Campus Mode", icon:"🏫",
                desc:"Configure campus settings and payment gateway.",
                type:"fields",
                fields:[
                    {label:"Enable Multi Campus Mode",
                     name:"enable_multi_campus", type:"checkbox",
                     help:"Turn ON if your institution has multiple campuses"},
                    {label:"Max Campus Preferences per Applicant",
                     name:"max_campus_preferences", type:"number",
                     placeholder:"3"},
                    {label:"Payment Gateway", name:"payment_gateway",
                     type:"select",
                     options:["Offline Only","Razorpay","PayU","Stripe"]}
                ]
            },
            {
                num:3, title:"Exam Types", icon:"📝",
                desc:"Define all entrance exams your institution uses.",
                type:"table",
                existing_count:(ex.exam_types||[]).length,
                existing_label:"Exam Types already configured",
                table_fields:[
                    {label:"Exam Name", name:"exam_name", type:"text",
                     reqd:true, placeholder:"e.g. CLAT"},
                    {label:"Code", name:"exam_code", type:"text",
                     reqd:true, placeholder:"e.g. CLAT"},
                    {label:"Category", name:"exam_category", type:"select",
                     options:["National","State","Institution-Own",
                              "Merit-Based","International"]},
                    {label:"Import Method", name:"score_import_method",
                     type:"select",
                     options:["CSV Upload","API Integration",
                              "Manual Entry","Not Applicable"]}
                ]
            },
            {
                num:4, title:"Quota & Reservation", icon:"⚖️",
                desc:"Define reservation categories and percentages.",
                type:"quota",
                existing_count:(ex.quota_policies||[]).length,
                existing_label:"Quota Policies already configured",
                header_fields:[
                    {label:"Policy Name", name:"quota_policy_name",
                     type:"text", reqd:true,
                     placeholder:"e.g. NLSIU-UG-2025-26"},
                    {label:"Legally Mandated", name:"is_legal_mandate",
                     type:"checkbox",
                     help:"Check if categories are legally required"}
                ],
                table_fields:[
                    {label:"Category Name", name:"category_name",
                     type:"text", reqd:true,
                     placeholder:"e.g. Scheduled Caste"},
                    {label:"Code", name:"category_code", type:"text",
                     reqd:true, placeholder:"e.g. SC"},
                    {label:"Mandated %", name:"mandated_percentage",
                     type:"number", placeholder:"15"},
                    {label:"Certificate Required",
                     name:"requires_certificate", type:"checkbox"},
                    {label:"Certificate Label", name:"certificate_label",
                     type:"text", placeholder:"e.g. SC Certificate"}
                ]
            },
            {
                num:5, title:"Admission Stages", icon:"🔄",
                desc:"Define your admission workflow stage sequence.",
                type:"stages",
                existing_count:(ex.stage_templates||[]).length,
                existing_label:"Stage Templates already configured",
                header_fields:[
                    {label:"Template Name", name:"template_name",
                     type:"text", reqd:true,
                     placeholder:"e.g. CLAT UG Flow 2025"}
                ],
                table_fields:[
                    {label:"Stage Name", name:"stage_name",
                     type:"text", reqd:true,
                     placeholder:"e.g. Application"},
                    {label:"Stage Type", name:"stage_type",
                     type:"select",
                     options:["Application","Screening","Exam",
                              "Interview","Evaluation","Merit",
                              "Document","Fee","Enrollment"]},
                    {label:"Mandatory", name:"is_mandatory",
                     type:"checkbox"}
                ]
            },
            {
                num:6, title:"Document Requirements", icon:"📄",
                desc:"Define required documents per program and category.",
                type:"redirect",
                route:"List/Document Requirement Config/List",
                count:ex.document_configs||0
            },
            {
                num:7, title:"Email Templates", icon:"📧",
                desc:"Configure notification emails with placeholders.",
                type:"redirect",
                route:"List/Email Template Config/List",
                count:ex.email_templates||0
            },
            {
                num:8, title:"Application Form", icon:"📋",
                desc:"Configure application form fields per program.",
                type:"redirect",
                route:"List/Application Form Config/List",
                count:ex.form_configs||0
            },
            {
                num:9, title:"Review & Activate", icon:"🚀",
                desc:"Review all configuration and commit to database.",
                type:"review"
            }
        ];
    }

    // ── PROGRESS BAR ──────────────────────────────────────────
    progress_bar_html() {
        const meta = this.steps_meta();
        const total = meta.length;

        // Build connector line segments + circles
        let items_html = "";
        meta.forEach((s, i) => {
            const done = this.completed_steps.has(s.num);
            const current = s.num === this.current_step;
            const future = !done && !current;

            // Circle
            const circle_bg = done ? "#28a745"
                : current ? "#1a73e8" : "#dee2e6";
            const circle_color = (done || current) ? "#fff" : "#999";
            const circle_border = done ? "#28a745"
                : current ? "#1a73e8" : "#dee2e6";
            const circle_content = done
                ? `<svg width="14" height="14" viewBox="0 0 14 14"
                    fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2 7L5.5 10.5L12 3.5" stroke="white"
                        stroke-width="2" stroke-linecap="round"
                        stroke-linejoin="round"/>
                   </svg>`
                : `<span style="font-size:13px;font-weight:700;
                    color:${circle_color}">${s.num}</span>`;

            const label_weight = current ? "700" : "400";
            const label_color = done ? "#28a745"
                : current ? "#1a73e8" : "#aaa";

            // Connector line before this circle (except first)
            if (i > 0) {
                const line_color = this.completed_steps.has(s.num - 1)
                    || done ? "#28a745" : "#dee2e6";
                items_html += `
                    <div style="flex:1;height:2px;background:${line_color};
                        margin-bottom:20px;align-self:center;
                        min-width:8px"></div>`;
            }

            items_html += `
                <div style="display:flex;flex-direction:column;
                    align-items:center;gap:8px;cursor:pointer"
                    onclick="window._aw.go_to_step(${s.num})">
                    <div style="width:36px;height:36px;border-radius:50%;
                        background:${circle_bg};
                        border:2px solid ${circle_border};
                        display:flex;align-items:center;
                        justify-content:center;
                        transition:all 0.2s;flex-shrink:0">
                        ${circle_content}
                    </div>
                    <div style="font-size:11px;font-weight:${label_weight};
                        color:${label_color};text-align:center;
                        max-width:60px;line-height:1.3;white-space:nowrap;
                        overflow:hidden;text-overflow:ellipsis">
                        ${s.label}
                    </div>
                </div>`;
        });

        return `
            <div style="display:flex;align-items:flex-start;
                justify-content:center;padding:0 0 24px 0;
                margin-bottom:24px;border-bottom:1px solid #f0f2f5">
                ${items_html}
            </div>`;
    }

    // ── RENDER ROOT ───────────────────────────────────────────
    render() {
        const container = $(this.wrapper).find(".layout-main-section");
        container.html(`
            <div style="display:flex;justify-content:center;
                padding:32px 16px;min-height:80vh;
                background:var(--bg-color,#f4f5f7)">
                <div id="aw-card" style="background:#fff;
                    border-radius:12px;
                    box-shadow:0 2px 16px rgba(0,0,0,0.08);
                    width:100%;max-width:680px;
                    padding:40px 44px;
                    font-family:var(--font-stack)">
                    <div id="aw-progress"></div>
                    <div id="aw-body"></div>
                    <div id="aw-nav" style="display:flex;
                        justify-content:space-between;
                        align-items:center;margin-top:32px;
                        padding-top:20px;
                        border-top:1px solid #f0f2f5">
                        <button id="aw-back" class="btn btn-default"
                            style="display:none"
                            onclick="window._aw.go_back()">
                            ← Back
                        </button>
                        <div></div>
                        <button id="aw-next" class="btn btn-primary"
                            style="min-width:140px"
                            onclick="window._aw.go_next()">
                            Save & Next →
                        </button>
                    </div>
                </div>
            </div>
        `);
        window._aw = this;
        this.render_step(1);
    }

    render_step(num) {
        this.current_step = num;
        const configs = this.steps_config();
        const step = configs[num - 1];

        // Progress bar
        $("#aw-progress").html(this.progress_bar_html());

        // Body
        let body = `
            <div style="margin-bottom:28px">
                <div style="font-size:11px;color:#aaa;
                    text-transform:uppercase;letter-spacing:1px;
                    margin-bottom:6px">
                    Step ${num} of ${this.total_steps}
                </div>
                <h2 style="margin:0 0 4px;color:#1a237e;
                    font-size:22px;font-weight:700">
                    ${step.icon} ${step.title}
                </h2>
                <p style="margin:0;color:#888;font-size:13px">
                    ${step.desc}
                </p>
            </div>
        `;

        if (step.type === "fields") {
            body += this.render_fields(step);
        } else if (step.type === "table") {
            body += this.render_table(step);
        } else if (step.type === "quota") {
            body += this.render_quota(step);
        } else if (step.type === "stages") {
            body += this.render_stages(step);
        } else if (step.type === "redirect") {
            body += this.render_redirect(step);
        } else if (step.type === "review") {
            body += this.render_review();
        }

        $("#aw-body").html(body);
        this.prefill(step);

        // Nav
        $("#aw-back").toggle(num > 1);
        if (num === this.total_steps) {
            $("#aw-next").hide();
        } else {
            $("#aw-next").show();
            if (step.type === "redirect") {
                $("#aw-next").text("Continue →");
            } else if (num === this.total_steps - 1) {
                $("#aw-next").text("Save & Review →");
            } else {
                $("#aw-next").text("Save & Next →");
            }
        }
    }

    render_fields(step) {
        return (step.fields || []).map(f => this.field_html(f)).join("");
    }

    render_table(step) {
        let html = this.existing_banner(step);
        html += this.table_wrapper(step.table_fields);
        html += `<button class="btn btn-xs btn-default"
            style="margin-top:10px"
            onclick="window._aw.add_row(${step.num})">
            + Add Row
        </button>`;
        return html;
    }

    render_quota(step) {
        let html = this.existing_banner(step);
        html += `<div style="background:#f8f9ff;border-radius:8px;
            padding:20px;margin-bottom:16px;
            border:1px solid #e8eaf6">
            <div style="font-size:12px;font-weight:600;color:#1a237e;
                margin-bottom:12px;text-transform:uppercase;
                letter-spacing:0.5px">Policy Details</div>
            ${(step.header_fields||[]).map(f=>this.field_html(f)).join("")}
        </div>
        <div style="font-size:12px;font-weight:600;color:#1a237e;
            margin-bottom:8px;text-transform:uppercase;
            letter-spacing:0.5px">Quota Categories</div>
        ${this.table_wrapper(step.table_fields)}
        <button class="btn btn-xs btn-default" style="margin-top:10px"
            onclick="window._aw.add_row(${step.num})">
            + Add Category
        </button>`;
        return html;
    }

    render_stages(step) {
        let html = this.existing_banner(step);
        html += `<div style="background:#f8f9ff;border-radius:8px;
            padding:20px;margin-bottom:16px;
            border:1px solid #e8eaf6">
            <div style="font-size:12px;font-weight:600;color:#1a237e;
                margin-bottom:12px;text-transform:uppercase;
                letter-spacing:0.5px">Template Details</div>
            ${(step.header_fields||[]).map(f=>this.field_html(f)).join("")}
        </div>
        <div style="font-size:12px;font-weight:600;color:#1a237e;
            margin-bottom:8px;text-transform:uppercase;
            letter-spacing:0.5px">Stages (in order)</div>
        ${this.table_wrapper(step.table_fields)}
        <button class="btn btn-xs btn-default" style="margin-top:10px"
            onclick="window._aw.add_row(${step.num})">
            + Add Stage
        </button>`;
        return html;
    }

    render_redirect(step) {
        const done = step.count > 0;
        return `
            <div style="text-align:center;padding:32px 16px">
                <div style="font-size:52px;margin-bottom:14px">
                    ${done ? "✅" : "📂"}
                </div>
                <div style="font-size:16px;font-weight:600;
                    color:#1a237e;margin-bottom:8px">
                    ${done
                        ? step.count + " record(s) configured"
                        : "Not yet configured"
                    }
                </div>
                <p style="color:#aaa;margin-bottom:24px;font-size:13px">
                    ${done
                        ? "You can add more or click Continue."
                        : "Click below to configure, then come back."
                    }
                </p>
                <button class="btn btn-primary"
                    onclick="frappe.set_route('${step.route}')">
                    Open ${step.title} →
                </button>
                <br>
                <small style="color:#ccc;margin-top:12px;display:block">
                    Configured in its DocType list view.
                </small>
            </div>`;
    }

    render_review() {
        const status = this.state.step_status || {};
        const configs = this.steps_config().slice(0, 8);
        let all_ok = true;
        const d = this.draft;

        let rows = configs.map(s => {
            const done = status[String(s.num)];
            if (!done) all_ok = false;
            return `<tr style="border-bottom:1px solid #f5f5f5">
                <td style="padding:11px 14px;font-size:13px">
                    ${s.icon} <b>${s.title}</b>
                </td>
                <td style="padding:11px 14px;text-align:center">
                    ${done
                        ? '<span style="color:#28a745;font-weight:600">✓ Ready</span>'
                        : '<span style="color:#e65100;font-weight:600">⚠ Pending</span>'
                    }
                </td>
                <td style="padding:11px 14px">
                    ${!done
                        ? `<button class="btn btn-xs btn-default"
                            onclick="window._aw.go_to_step(${s.num})">
                            Fix →
                           </button>`
                        : '<span style="color:#ccc;font-size:12px">—</span>'
                    }
                </td>
            </tr>`;
        }).join("");

        const has_draft = d.institution_name;
        return `
            ${has_draft ? `
            <div style="background:#f0f4ff;border-radius:8px;
                padding:14px 18px;margin-bottom:20px;font-size:13px;
                border-left:4px solid #1a73e8;line-height:1.8">
                <b>📋 Draft Summary</b><br>
                <span style="color:#555">
                    <b>${d.institution_name||"—"}</b> (${d.institution_code||"—"}) ·
                    ${d.compliance_mode||"—"} mode ·
                    ${(d.exam_types||[]).length} exam type(s) ·
                    ${(d.categories||[]).length} quota categor(ies) ·
                    ${(d.stages||[]).length} stage(s)
                </span>
            </div>` : `
            <div style="background:#fff3e0;border-radius:8px;
                padding:14px 18px;margin-bottom:20px;font-size:13px;
                border-left:4px solid #ff9800">
                ⚠ No draft data found. Go back and fill the steps.
            </div>`}

            <div style="border:1px solid #eee;border-radius:8px;
                overflow:hidden;margin-bottom:24px">
                <table style="width:100%;border-collapse:collapse">
                    <thead>
                        <tr style="background:#f5f7ff">
                            <th style="padding:11px 14px;text-align:left;
                                font-size:12px;color:#777;font-weight:600">
                                Step
                            </th>
                            <th style="padding:11px 14px;text-align:center;
                                font-size:12px;color:#777;font-weight:600">
                                Status
                            </th>
                            <th style="padding:11px 14px;font-size:12px;
                                color:#777;font-weight:600">Action</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>

            <div style="text-align:center;padding:24px;background:#f8f9ff;
                border-radius:10px;border:1px solid #e8eaf6">
                ${this.state.onboarding_complete
                    ? `<div style="color:#28a745;font-size:16px;
                        font-weight:700">🟢 System is Live</div>`
                    : all_ok
                    ? `<p style="color:#666;margin-bottom:16px;font-size:13px">
                        All steps ready. Click Activate to commit all
                        draft data and go live.
                       </p>
                       <button class="btn btn-success btn-lg"
                        onclick="window._aw.activate()"
                        style="padding:12px 48px;font-size:15px;
                        font-weight:600">
                        🚀 Activate System
                       </button>`
                    : `<div style="color:#e65100;font-size:14px;
                        font-weight:500">
                        ⚠ Complete all steps before activating.
                       </div>`
                }
            </div>`;
    }

    // ── HELPERS ───────────────────────────────────────────────

    existing_banner(step) {
        if (!step.existing_count) return "";
        return `<div style="background:#e8f5e9;border-radius:8px;
            padding:12px 16px;margin-bottom:16px;
            border-left:4px solid #43a047;font-size:13px;color:#2e7d32">
            ✅ <b>${step.existing_count}</b> ${step.existing_label}.
            Add more below or click Continue.
        </div>`;
    }

    table_wrapper(fields) {
        const heads = fields.map(f =>
            `<th style="padding:9px 10px;text-align:left;font-size:12px;
                color:#666;font-weight:600;background:#f5f7ff;
                border-bottom:1px solid #e8eaf0">
                ${f.label}
                ${f.reqd?'<span style="color:red">*</span>':""}
            </th>`
        ).join("") + `<th style="width:36px;background:#f5f7ff;
            border-bottom:1px solid #e8eaf0"></th>`;
        return `<div style="border:1px solid #e8eaf0;border-radius:8px;
            overflow:hidden">
            <table style="width:100%;border-collapse:collapse" id="aw-table">
                <thead><tr>${heads}</tr></thead>
                <tbody id="aw-tbody"></tbody>
            </table>
        </div>`;
    }

    field_html(f) {
        const reqd = f.reqd
            ? '<span style="color:red;margin-left:2px">*</span>' : "";
        let input = "";
        if (f.type === "select") {
            const opts = (f.options||[]).map(o =>
                `<option value="${o}">${o}</option>`
            ).join("");
            input = `<select id="aw_${f.name}"
                class="form-control" style="height:36px">
                ${opts}
            </select>`;
        } else if (f.type === "checkbox") {
            input = `<div style="display:flex;align-items:center;
                gap:8px;margin-top:6px">
                <input type="checkbox" id="aw_${f.name}"
                    style="width:16px;height:16px;cursor:pointer">
                ${f.help
                    ? `<small style="color:#aaa">${f.help}</small>`
                    : ""}
            </div>`;
        } else if (f.type === "color") {
            input = `<input type="color" id="aw_${f.name}"
                style="width:52px;height:36px;border:1px solid #ddd;
                border-radius:4px;cursor:pointer;padding:2px">`;
        } else {
            input = `<input type="${f.type||'text'}" id="aw_${f.name}"
                class="form-control" style="height:36px"
                placeholder="${f.placeholder||''}">`;
        }
        return `<div style="margin-bottom:18px">
            <label style="font-weight:600;color:#333;font-size:13px;
                display:block;margin-bottom:5px">
                ${f.label}${reqd}
            </label>
            ${input}
            ${f.help && f.type !== "checkbox"
                ? `<small style="color:#bbb;display:block;margin-top:3px">
                    ${f.help}</small>` : ""}
        </div>`;
    }

    row_html(fields, data) {
        data = data || {};
        const cells = fields.map(f => {
            let inp = "";
            if (f.type === "select") {
                const opts = (f.options||[]).map(o =>
                    `<option value="${o}"
                        ${data[f.name]===o?"selected":""}>${o}</option>`
                ).join("");
                inp = `<select class="form-control form-control-sm aw-cell"
                    data-field="${f.name}"
                    style="min-width:90px;height:32px">${opts}</select>`;
            } else if (f.type === "checkbox") {
                inp = `<input type="checkbox" class="aw-cell"
                    data-field="${f.name}"
                    ${data[f.name]?"checked":""}
                    style="width:16px;height:16px">`;
            } else {
                inp = `<input type="text"
                    class="form-control form-control-sm aw-cell"
                    data-field="${f.name}"
                    value="${data[f.name] || ''}"
                    placeholder="${f.placeholder||f.label}"
                    style="height:32px">`;
            }
            return `<td style="padding:6px 8px">${inp}</td>`;
        }).join("");
        return `<tr>${cells}
            <td style="padding:6px 8px">
                <button class="btn btn-xs btn-danger"
                    onclick="$(this).closest('tr').remove()"
                    title="Remove">✕</button>
            </td>
        </tr>`;
    }

    add_row(step_num) {
        const configs = this.steps_config();
        const step = configs[step_num - 1];
        const fields = step.table_fields;
        if ($("#aw-tbody").length === 0) return;
        $("#aw-tbody").append(this.row_html(fields, {}));
    }

    prefill(step) {
        const d = this.draft;
        if (step.num === 1) {
            ["institution_name","institution_code","support_email",
             "compliance_mode","portal_theme_color"].forEach(k => {
                if (d[k] !== undefined) $(`#aw_${k}`).val(d[k]);
            });
        }
        if (step.num === 2) {
            if (d.enable_multi_campus !== undefined) {
                $("#aw_enable_multi_campus").prop("checked",
                    !!d.enable_multi_campus);
            }
            if (d.max_campus_preferences)
                $("#aw_max_campus_preferences").val(d.max_campus_preferences);
            if (d.payment_gateway)
                $("#aw_payment_gateway").val(d.payment_gateway);
        }
        if (step.num === 3 && (d.exam_types||[]).length > 0) {
            const configs = this.steps_config();
            d.exam_types.forEach(r =>
                $("#aw-tbody").append(this.row_html(configs[2].table_fields, r))
            );
        }
        if (step.num === 4) {
            if (d.quota_policy_name)
                $("#aw_quota_policy_name").val(d.quota_policy_name);
            if (d.is_legal_mandate)
                $("#aw_is_legal_mandate").prop("checked", true);
            if ((d.categories||[]).length > 0) {
                const configs = this.steps_config();
                d.categories.forEach(r =>
                    $("#aw-tbody").append(
                        this.row_html(configs[3].table_fields, r)
                    )
                );
            }
        }
        if (step.num === 5) {
            if (d.template_name)
                $("#aw_template_name").val(d.template_name);
            if ((d.stages||[]).length > 0) {
                const configs = this.steps_config();
                d.stages.forEach(r =>
                    $("#aw-tbody").append(
                        this.row_html(configs[4].table_fields, r)
                    )
                );
            }
        }
    }

    collect(step) {
        const data = {};
        const all_fields = [
            ...(step.fields || []),
            ...(step.header_fields || [])
        ];
        all_fields.forEach(f => {
            const el = $(`#aw_${f.name}`);
            data[f.name] = f.type === "checkbox"
                ? (el.is(":checked") ? 1 : 0) : el.val();
        });
        if (step.table_fields) {
            const rows = [];
            $("#aw-tbody tr").each(function() {
                const row = {};
                $(this).find(".aw-cell").each(function() {
                    const field = $(this).data("field");
                    row[field] = $(this).is(":checkbox")
                        ? ($(this).is(":checked") ? 1 : 0)
                        : $(this).val();
                });
                if (Object.values(row).some(v => v && v !== "0"))
                    rows.push(row);
            });
            if (step.type === "table")  data.exam_types  = rows;
            if (step.type === "quota")  data.categories  = rows;
            if (step.type === "stages") data.stages      = rows;
        }
        return data;
    }

    go_next() {
        const configs = this.steps_config();
        const step = configs[this.current_step - 1];

        if (step.type === "redirect" || step.type === "review") {
            this.refresh_and_go(this.current_step + 1);
            return;
        }

        const data = this.collect(step);
        const btn = $("#aw-next");
        btn.prop("disabled", true).text("Saving...");

        frappe.call({
            method: "slcm.admission.page.admission_setup_wizard"
                + ".admission_setup_wizard.save_step_draft",
            args: {
                step: this.current_step,
                data: JSON.stringify(data)
            },
            callback: (r) => {
                btn.prop("disabled", false).text("Save & Next →");
                if (r.message && r.message.success) {
                    this.draft = Object.assign(this.draft, data);
                    this.completed_steps.add(this.current_step);
                    frappe.show_alert({
                        message: "✓ Draft saved",
                        indicator: "green"
                    }, 2);
                    this.refresh_and_go(this.current_step + 1);
                } else {
                    frappe.show_alert({
                        message: "Save failed.",
                        indicator: "red"
                    }, 4);
                }
            }
        });
    }

    refresh_and_go(next) {
        frappe.call({
            method: "slcm.admission.page.admission_setup_wizard"
                + ".admission_setup_wizard.get_wizard_state",
            callback: (r) => {
                if (r.message) {
                    this.state = r.message;
                    this.draft = r.message.draft || this.draft;
                    this.completed_steps = new Set(
                        Object.entries(r.message.step_status || {})
                            .filter(([k,v]) => v)
                            .map(([k]) => parseInt(k))
                    );
                }
                if (next <= this.total_steps)
                    this.render_step(next);
            }
        });
    }

    go_back() {
        if (this.current_step > 1)
            this.render_step(this.current_step - 1);
    }

    go_to_step(num) {
        this.render_step(num);
    }

    activate() {
        frappe.confirm(
            "<b>Commit all draft data to the database and go live?</b>"
            + "<br><br>This cannot be undone.",
            () => {
                frappe.call({
                    method: "slcm.admission.page.admission_setup_wizard"
                        + ".admission_setup_wizard.activate_system",
                    callback: (r) => {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: "🎉 " + r.message.message,
                                indicator: "green"
                            }, 10);
                            setTimeout(() =>
                                this.refresh_and_go(9), 2000);
                        } else if (r.message && r.message.errors) {
                            frappe.msgprint({
                                title: "Cannot Activate",
                                message: "<ul><li>"
                                    + r.message.errors.join("</li><li>")
                                    + "</li></ul>",
                                indicator: "red"
                            });
                        }
                    }
                });
            }
        );
    }
}
