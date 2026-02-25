frappe.pages["exam-score-import"].on_page_load = function(wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: "Exam Score Import",
        single_column: true
    });
    render_import_page(wrapper);
};

// Import workflow has 4 steps
const IMPORT_STEPS = [
    {num:1, label:"Select Cycle"},
    {num:2, label:"Select Exam Type"},
    {num:3, label:"Upload / Sync"},
    {num:4, label:"Result"}
];

function import_progress_html(current_step, completed) {
    // completed = Set of completed step numbers
    let items_html = "";
    IMPORT_STEPS.forEach((s, i) => {
        const done = completed.has(s.num);
        const current = s.num === current_step;

        const circle_bg = done ? "#28a745"
            : current ? "#1a73e8" : "#dee2e6";
        const circle_color = (done||current) ? "#fff" : "#999";
        const circle_content = done
            ? `<svg width="13" height="13" viewBox="0 0 14 14"
                fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 7L5.5 10.5L12 3.5" stroke="white"
                    stroke-width="2" stroke-linecap="round"
                    stroke-linejoin="round"/>
               </svg>`
            : `<span style="font-size:13px;font-weight:700;
                color:${circle_color}">${s.num}</span>`;

        const label_color = done ? "#28a745"
            : current ? "#1a73e8" : "#aaa";
        const label_weight = current ? "700" : "400";

        if (i > 0) {
            const line_color = completed.has(i) ? "#28a745" : "#dee2e6";
            items_html += `<div style="flex:1;height:2px;
                background:${line_color};margin-bottom:20px;
                align-self:center;min-width:12px"></div>`;
        }

        items_html += `
            <div style="display:flex;flex-direction:column;
                align-items:center;gap:8px">
                <div style="width:36px;height:36px;border-radius:50%;
                    background:${circle_bg};
                    display:flex;align-items:center;
                    justify-content:center;flex-shrink:0">
                    ${circle_content}
                </div>
                <div style="font-size:11px;font-weight:${label_weight};
                    color:${label_color};text-align:center;
                    white-space:nowrap">
                    ${s.label}
                </div>
            </div>`;
    });

    return `<div style="display:flex;align-items:flex-start;
        padding:0 0 24px 0;margin-bottom:24px;
        border-bottom:1px solid #f0f2f5">
        ${items_html}
    </div>`;
}

function render_import_page(wrapper) {
    const container = $(wrapper).find(".layout-main-section");

    container.html(`
        <div style="display:flex;justify-content:center;
            padding:32px 16px;background:var(--bg-color,#f4f5f7);
            min-height:80vh">
            <div style="background:#fff;border-radius:12px;
                box-shadow:0 2px 16px rgba(0,0,0,0.08);
                width:100%;max-width:640px;padding:40px 44px;
                font-family:var(--font-stack)">

                <div id="import-progress"></div>

                <h2 style="margin:0 0 4px;color:#1a237e;
                    font-size:22px;font-weight:700">
                    📊 Exam Score Import
                </h2>
                <p style="margin:0 0 28px;color:#888;font-size:13px">
                    Import scores via CSV upload or API sync
                </p>

                <!-- Step 1: Cycle -->
                <div id="step-cycle" style="margin-bottom:22px">
                    <label style="font-weight:600;font-size:13px;
                        color:#333;display:block;margin-bottom:6px">
                        1. Admission Cycle
                        <span style="color:red">*</span>
                    </label>
                    <select id="cycle-select" class="form-control"
                        style="height:38px">
                        <option value="">— Loading cycles... —</option>
                    </select>
                </div>

                <!-- Step 2: Exam Type -->
                <div id="step-exam" style="margin-bottom:22px;
                    display:none">
                    <label style="font-weight:600;font-size:13px;
                        color:#333;display:block;margin-bottom:6px">
                        2. Exam Type
                        <span style="color:red">*</span>
                    </label>
                    <select id="exam-type-select" class="form-control"
                        style="height:38px">
                        <option value="">— Select Exam Type —</option>
                    </select>
                </div>

                <!-- Step 3: Upload / Sync -->
                <div id="step-upload" style="display:none">
                    <div id="csv-section" style="display:none">
                        <div style="font-size:13px;font-weight:600;
                            color:#1a237e;margin-bottom:10px">
                            3. Upload CSV / XLSX
                        </div>
                        <div id="mapping-info" style="display:none;
                            font-size:12px;color:#444;background:#f5f7ff;
                            padding:12px;border-radius:6px;margin-bottom:14px;
                            border-left:3px solid #1a73e8;line-height:1.8">
                        </div>
                        <div style="border:2px dashed #c5cae9;
                            border-radius:8px;padding:28px;text-align:center;
                            background:#fafbff;margin-bottom:14px;
                            cursor:pointer" onclick="$('#csv-file').click()">
                            <div style="font-size:28px;margin-bottom:8px">
                                📤
                            </div>
                            <div style="font-weight:500;color:#3949ab">
                                Click to choose file
                            </div>
                            <div style="font-size:12px;color:#aaa;
                                margin-top:4px">
                                CSV or XLSX
                            </div>
                        </div>
                        <input type="file" id="csv-file"
                            accept=".csv,.xlsx" style="display:none">
                        <div id="file-chosen" style="display:none;
                            font-size:13px;color:#28a745;margin-bottom:12px;
                            background:#e8f5e9;padding:10px;
                            border-radius:6px"></div>
                        <button class="btn btn-primary" id="upload-btn"
                            style="display:none" onclick="do_upload()">
                            Import Scores
                        </button>
                    </div>
                    <div id="api-section" style="display:none">
                        <div style="font-size:13px;font-weight:600;
                            color:#1a237e;margin-bottom:10px">
                            3. API Sync
                        </div>
                        <div style="background:#e8f5e9;border-radius:8px;
                            padding:14px;margin-bottom:16px;font-size:13px;
                            color:#2e7d32;border-left:4px solid #43a047">
                            ✅ Credentials configured in Exam Type Config.
                        </div>
                        <button class="btn btn-primary"
                            onclick="do_api()">
                            🔄 Fetch Scores via API
                        </button>
                    </div>
                    <div id="manual-section" style="display:none">
                        <div style="background:#fff3e0;border-radius:8px;
                            padding:16px;border-left:4px solid #ff9800;
                            font-size:13px">
                            <b>Manual Entry Mode</b><br>
                            Enter scores directly on each Applicant record.
                        </div>
                    </div>
                    <div id="na-section" style="display:none">
                        <div style="background:#f5f5f5;border-radius:8px;
                            padding:16px;border-left:4px solid #bbb;
                            font-size:13px">
                            <b>Not Applicable</b> — No import needed.
                        </div>
                    </div>
                </div>

                <!-- Step 4: Result -->
                <div id="step-result" style="display:none;margin-top:24px;
                    padding-top:20px;border-top:1px solid #f0f2f5">
                    <div style="font-size:13px;font-weight:600;
                        color:#1a237e;margin-bottom:12px">
                        4. Import Result
                    </div>
                    <div id="result-content"></div>
                    <button class="btn btn-default btn-sm"
                        style="margin-top:16px"
                        onclick="reset_import()">
                        ← Start New Import
                    </button>
                </div>

            </div>
        </div>
    `);

    window._import_state = {
        current_step: 1,
        completed: new Set(),
        exam_types: []
    };

    update_import_progress();

    // Load cycles
    frappe.call({
        method: "slcm.admission.page.exam_score_import"
            + ".exam_score_import.get_admission_cycles",
        callback: function(r) {
            const cycles = r.message || [];
            const sel = $("#cycle-select");
            sel.empty().append(
                '<option value="">— Select Admission Cycle —</option>'
            );
            if (!cycles.length) {
                sel.append(
                    '<option disabled>No active or draft cycles found</option>'
                );
            } else {
                cycles.forEach(c => {
                    sel.append(`<option value="${c.name}">
                        ${c.cycle_name} — ${c.admission_year} (${c.status})
                    </option>`);
                });
            }
        }
    });

    // Load exam types
    frappe.call({
        method: "slcm.admission.page.exam_score_import"
            + ".exam_score_import.get_exam_types",
        callback: function(r) {
            window._import_state.exam_types = r.message || [];
            const sel = $("#exam-type-select");
            sel.empty().append(
                '<option value="">— Select Exam Type —</option>'
            );
            window._import_state.exam_types.forEach(et => {
                sel.append(`<option value="${et.name}">
                    ${et.exam_name} (${et.exam_code})
                    — ${et.score_import_method}
                </option>`);
            });
        }
    });

    // Cycle selected → unlock step 2
    $("#cycle-select").on("change", function() {
        if ($(this).val()) {
            window._import_state.completed.add(1);
            window._import_state.current_step = 2;
            $("#step-exam").show();
        } else {
            window._import_state.completed.delete(1);
            window._import_state.current_step = 1;
            $("#step-exam").hide();
            $("#step-upload").hide();
        }
        update_import_progress();
    });

    // Exam type selected → show import method
    $("#exam-type-select").on("change", function() {
        const et = window._import_state.exam_types.find(
            e => e.name === $(this).val()
        );
        $("#csv-section,#api-section,#manual-section,#na-section").hide();
        $("#mapping-info").hide();
        $("#step-upload").hide();
        if (!et) {
            window._import_state.completed.delete(2);
            window._import_state.current_step = 2;
            update_import_progress();
            return;
        }
        window._import_state.completed.add(2);
        window._import_state.current_step = 3;
        $("#step-upload").show();
        const m = et.score_import_method;
        if (m === "CSV Upload") {
            $("#csv-section").show();
            if (et.csv_field_mapping) {
                try {
                    const map = JSON.parse(et.csv_field_mapping);
                    let info = "<b>Column Mapping:</b><br>";
                    Object.entries(map).forEach(([k,v]) => {
                        info += `&nbsp;<code>${k}</code> → <b>${v}</b><br>`;
                    });
                    $("#mapping-info").html(info).show();
                } catch(e) {}
            }
        } else if (m === "API Integration") {
            $("#api-section").show();
        } else if (m === "Manual Entry") {
            $("#manual-section").show();
            mark_step3_done();
        } else {
            $("#na-section").show();
            mark_step3_done();
        }
        update_import_progress();
    });

    // File chosen
    $("#csv-file").on("change", function() {
        const f = this.files[0];
        if (f) {
            $("#file-chosen").html(
                `✓ <b>${f.name}</b> (${(f.size/1024).toFixed(1)} KB)`
            ).show();
            $("#upload-btn").show();
        }
    });
}

function update_import_progress() {
    const s = window._import_state;
    $("#import-progress").html(
        import_progress_html(s.current_step, s.completed)
    );
}

function mark_step3_done() {
    window._import_state.completed.add(3);
    window._import_state.current_step = 4;
    update_import_progress();
}

window.do_upload = function() {
    const cycle = $("#cycle-select").val();
    const exam = $("#exam-type-select").val();
    const file = $("#csv-file")[0].files[0];
    if (!cycle || !exam || !file) {
        frappe.show_alert({
            message: "Select cycle, exam type and file.",
            indicator: "orange"
        }, 4);
        return;
    }
    $("#upload-btn").prop("disabled", true).text("Uploading...");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("is_private", 1);
    fetch("/api/method/upload_file", {
        method: "POST",
        headers: {"X-Frappe-CSRF-Token": frappe.csrf_token},
        body: fd
    })
    .then(r => r.json())
    .then(data => {
        if (data.message && data.message.file_url) {
            frappe.call({
                method: "slcm.admission.page.exam_score_import"
                    + ".exam_score_import.import_csv_scores",
                args: {
                    exam_type: exam,
                    file_url: data.message.file_url,
                    admission_cycle: cycle
                },
                callback: function(r) {
                    $("#upload-btn").prop("disabled", false)
                        .text("Import Scores");
                    show_result(r.message);
                }
            });
        }
    })
    .catch(err => {
        $("#upload-btn").prop("disabled", false).text("Import Scores");
        frappe.show_alert({
            message: "Upload failed: " + err,
            indicator: "red"
        }, 5);
    });
}

window.do_api = function() {
    const cycle = $("#cycle-select").val();
    const exam = $("#exam-type-select").val();
    if (!cycle || !exam) {
        frappe.show_alert({
            message: "Select cycle and exam type.",
            indicator: "orange"
        }, 4);
        return;
    }
    frappe.show_alert({message:"Syncing...",indicator:"blue"},3);
    frappe.call({
        method: "slcm.admission.page.exam_score_import"
            + ".exam_score_import.trigger_api_sync",
        args: {exam_type: exam, admission_cycle: cycle},
        callback: function(r) { show_result(r.message); }
    });
}

function show_result(result) {
    if (!result) return;
    mark_step3_done();
    $("#step-result").show();
    let html = "";
    if (result.success) {
        html = `
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px">
            <div style="flex:1;background:#e8f5e9;border-radius:8px;
                padding:18px;text-align:center;min-width:120px">
                <div style="font-size:28px;font-weight:700;color:#28a745">
                    ${result.imported || 0}
                </div>
                <div style="color:#666;font-size:12px;margin-top:4px">
                    Imported
                </div>
            </div>
            <div style="flex:1;background:#fff3e0;border-radius:8px;
                padding:18px;text-align:center;min-width:120px">
                <div style="font-size:28px;font-weight:700;color:#e65100">
                    ${result.unmatched || 0}
                </div>
                <div style="color:#666;font-size:12px;margin-top:4px">
                    Unmatched
                </div>
            </div>
        </div>`;
        if ((result.unmatched_rows||[]).length) {
            html += `<div style="background:#fff8e1;border-radius:6px;
                padding:12px;font-size:12px;color:#555">
                <b>Unmatched rows:</b><br>
                ${result.unmatched_rows.map(r=>`• ${r}`).join("<br>")}
            </div>`;
        }
    } else {
        html = `<div style="background:#ffebee;color:#c62828;
            padding:14px;border-radius:6px;font-size:13px">
            ✗ ${result.error || "Import failed."}
        </div>`;
    }
    $("#result-content").html(html);
    window._import_state.completed.add(3);
    window._import_state.current_step = 4;
    window._import_state.completed.add(4);
    update_import_progress();
    $("html,body").animate({
        scrollTop: $("#step-result").offset().top - 60
    }, 400);
}

window.reset_import = function() {
    window._import_state = {
        current_step: 1,
        completed: new Set(),
        exam_types: window._import_state.exam_types
    };
    frappe.set_route("exam-score-import");
}
