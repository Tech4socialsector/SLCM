// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on('Exam Schema', {
    refresh(frm) {
        toggle_components_section(frm);
        render_components_footer(frm);
        calculate_total_effective_marks(frm);
        setup_components_grid(frm);
    },

    schema_name(frm) { toggle_components_section(frm); },
    total_marks(frm) {
        toggle_components_section(frm);
        calculate_total_effective_marks(frm);
    },
    passing_marks(frm) { toggle_components_section(frm); }
});

// ─── Section Gating ───────────────────────────────────────────────
function toggle_components_section(frm) {
    let show = frm.doc.schema_name && frm.doc.total_marks && frm.doc.passing_marks;
    frm.toggle_display('components_section', show);
    frm.toggle_display('components', show);
    frm.toggle_display('components_html', show);
}

// ─── Components Footer + Assessment Sections ─────────────────────
function render_components_footer(frm) {
    if (!frm.fields_dict.components_html || !frm.fields_dict.components_html.$wrapper) return;

    let $wrapper = frm.fields_dict.components_html.$wrapper;
    $wrapper.empty();

    let total_eff = frm.doc.total_effective_marks || 0;
    let total_marks = frm.doc.total_marks || 0;

    // ── Component footer ──
    let $footer = $(`
        <div style="display:flex; align-items:center; gap:20px; margin-top:10px; padding:8px 0;">
            <div style="position:relative; display:inline-block;">
                <button class="btn btn-xs" id="add-component-btn"
                    style="color:#e67e22; border:1.5px dashed #e67e22; background:#fff8f0; border-radius:6px; padding:6px 18px; font-weight:600; cursor:pointer; font-size:12px;">
                    Add New Component ▾
                </button>
                <div id="component-dropdown" style="display:none; position:absolute; left:0; top:100%; z-index:1050; background:#fff; border:1px solid #d1d8dd; border-radius:8px; box-shadow:0 6px 24px rgba(0,0,0,0.12); min-width:240px; max-height:320px; overflow-y:auto; margin-top:4px;">
                    <div style="padding:8px;">
                        <input type="text" id="component-search" placeholder="Search field"
                            style="width:100%; padding:6px 10px; border:1px solid #d1d8dd; border-radius:4px; font-size:13px; outline:none;" />
                    </div>
                    <div style="padding:2px 8px 4px; text-align:right;">
                        <a href="#" id="add-all-link" style="font-size:12px; color:#5e64ff;">Add all</a>
                    </div>
                    <div id="component-list" style="padding:0 4px 8px;"></div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
                <input type="text" readonly value="${total_eff}"
                    style="width:80px; padding:6px 10px; border:1px solid #d1d8dd; border-radius:4px; font-size:13px; background:#f7f7f7; text-align:center;" />
                ${total_eff != total_marks
            ? `<span style="color:#e74c3c; font-size:12px; font-style:italic;">
                        <i class="fa fa-info-circle"></i> Sum of effective maximum marks must be equal to schema total marks = ${total_marks}
                      </span>`
            : `<span style="color:#27ae60; font-size:12px;">
                        <i class="fa fa-check-circle"></i> Total matches schema marks
                      </span>`}
            </div>
        </div>
    `);
    $wrapper.append($footer);

    $footer.find('#add-component-btn').on('click', function (e) {
        e.stopPropagation();
        let $dd = $footer.find('#component-dropdown');
        if ($dd.is(':visible')) { $dd.hide(); } else {
            load_component_list(frm, $footer);
            $dd.show();
            $footer.find('#component-search').focus();
        }
    });
    $(document).off('click.comp_dd').on('click.comp_dd', function (e) {
        if (!$(e.target).closest('#component-dropdown, #add-component-btn').length) {
            $footer.find('#component-dropdown').hide();
        }
    });
    $footer.find('#component-search').on('input', function () {
        let q = $(this).val().toLowerCase();
        $footer.find('.component-item').each(function () { $(this).toggle($(this).text().toLowerCase().includes(q)); });
    });
    $footer.find('#add-all-link').on('click', function (e) { e.preventDefault(); add_all_components(frm, $footer); });

    // ── Per-Custom-component Assessment Sections ──
    $wrapper.append('<div id="all-assessments-container"></div>');
    render_all_assessment_sections(frm);
}

// ═══════════════════════════════════════════════════════════════════
//  ASSESSMENT SECTIONS — one grid per Custom / Re Exam / Makeup
// ═══════════════════════════════════════════════════════════════════

function render_all_assessment_sections(frm) {
    let $container = frm.fields_dict.components_html.$wrapper.find('#all-assessments-container');
    if (!$container.length) return;
    $container.empty();

    let components = frm.doc.components || [];
    if (!components.length) return;

    components.forEach(function (comp_row) {
        let comp_name = comp_row.exam_component;
        if (!comp_name) return;

        let section_id = 'assess_sec_' + comp_row.name;
        $container.append('<div id="' + section_id + '"></div>');

        frappe.db.get_value('Exam Component', comp_name, 'component_type', function (r) {
            if (!r) return;
            if (r.component_type === 'Custom') {
                build_assessment_grid(frm, comp_row, section_id);
            } else if (r.component_type === 'Re Exam' || r.component_type === 'Makeup') {
                build_reexam_grid(frm, comp_row, section_id, r.component_type);
            }
        });
    });
}

function build_assessment_grid(frm, comp_row, section_id) {
    let comp_name = comp_row.exam_component;
    let label = comp_row.label || comp_name;
    let expected_marks = flt(comp_row.effective_max_marks) || 0;

    // CSS grid template shared by header and rows
    let grid_cols = '40px 2fr 1.5fr 1fr 1fr 1fr 1fr 1fr 60px 80px 36px';

    let $section = $(`
        <div class="frappe-control assessment-grid-section" data-component="${comp_name}" style="margin-top:25px;">
            <div class="form-group">
                <div class="clearfix">
                    <label class="control-label" style="display:flex; justify-content:space-between; align-items:center; padding-right:0;">
                        <span>${frappe.utils.escape_html(comp_name)} | ${frappe.utils.escape_html(label)}</span>
                        <span style="font-size:11px; color:#fff; background:#27ae60; border-radius:12px; padding:2px 12px; font-weight:500;">Custom</span>
                    </label>
                </div>
                <div class="grid-body" style="border:1px solid #d1d8dd; border-radius:4px; background:#fff;">
                    <div class="grid-heading-row" style="display:grid; grid-template-columns:${grid_cols}; gap:0; align-items:center; background:#f7f8fa; border-bottom:1px solid #d1d8dd; padding:8px 10px; font-weight:600; font-size:11px; color:#8d99ae;">
                        <div style="text-align:center;">No.</div>
                        <div>Assessment *</div>
                        <div>Label</div>
                        <div>Effective Max</div>
                        <div>Weightage %</div>
                        <div>Max Marks</div>
                        <div>Min Marks</div>
                        <div>Passing Marks</div>
                        <div style="text-align:center;">Pass/Fail</div>
                        <div>Enrollment</div>
                        <div></div>
                    </div>
                    <div class="grid-rows"></div>
                    <div class="grid-footer" style="padding:6px 10px; border-top:1px solid #d1d8dd;">
                        <a class="btn-add-row" style="font-size:12px; color:#36414c; cursor:pointer; text-decoration:none;">
                            Add row
                        </a>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:15px; margin-top:10px; padding:4px 0;">
                    <div style="position:relative; display:inline-block;">
                        <button class="btn btn-xs add-assess-btn"
                            style="color:#e67e22; border:1.5px dashed #e67e22; background:#fff8f0; border-radius:6px; padding:6px 18px; font-weight:600; cursor:pointer; font-size:12px;">
                            Add New Assessment ▾
                        </button>
                        <div class="assess-dropdown" style="display:none; position:absolute; left:0; top:100%; z-index:1060; background:#fff; border:1px solid #d1d8dd; border-radius:8px; box-shadow:0 6px 24px rgba(0,0,0,0.12); min-width:260px; max-height:320px; overflow-y:auto; margin-top:4px;">
                            <div style="padding:8px;">
                                <input type="text" class="assess-search" placeholder="Search assessment"
                                    style="width:100%; padding:6px 10px; border:1px solid #d1d8dd; border-radius:4px; font-size:13px; outline:none;" />
                            </div>
                            <div class="assess-list-items" style="padding:0 4px 8px;"></div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px; margin-left:auto;">
                        <div class="assess-total-box" style="padding:4px 12px; border:1px solid #d1d8dd; border-radius:4px; background:#f7f7f7; font-size:13px; font-weight:600; min-width:50px; text-align:center;">0</div>
                        <div class="assess-validation" style="font-size:11px; font-style:italic;"></div>
                    </div>
                </div>
            </div>
        </div>
    `);

    let $wrapper = $('#' + section_id);
    $wrapper.html('').append($section);

    // Render rows
    render_grid_rows(frm, comp_name, $section, expected_marks);

    // Add row button
    $section.find('.btn-add-row').on('click', function (e) {
        e.preventDefault();
        let row = frm.add_child('assessments');
        row.exam_component = comp_name;
        row.requires_enrolment = 'Auto';
        frm.dirty();
        render_grid_rows(frm, comp_name, $section, expected_marks);
    });

    // ── Dropdown toggle ──
    let $btn = $section.find('.add-assess-btn');
    let $dropdown = $section.find('.assess-dropdown');

    $btn.on('click', function (e) {
        e.stopPropagation();
        $('.assess-dropdown').not($dropdown).hide();
        $('#component-dropdown').hide();
        if ($dropdown.is(':visible')) { $dropdown.hide(); }
        else {
            load_assessment_dropdown(frm, comp_name, $section, expected_marks);
            $dropdown.show();
            $section.find('.assess-search').focus();
        }
    });

    $(document).off('click.assess_dd_' + comp_name).on('click.assess_dd_' + comp_name, function (e) {
        if (!$(e.target).closest('.add-assess-btn, .assess-dropdown').length) { $dropdown.hide(); }
    });

    $section.find('.assess-search').on('input', function () {
        let q = $(this).val().toLowerCase();
        $section.find('.assess-dd-item').each(function () { $(this).toggle($(this).text().toLowerCase().includes(q)); });
    });
}

// ─── Render grid rows (Frappe-native style) ──────────────────────
function render_grid_rows(frm, comp_name, $section, expected_marks) {
    let $rows = $section.find('.grid-rows');
    $rows.empty();

    let all = frm.doc.assessments || [];
    let filtered = all.filter(function (a) { return a.exam_component === comp_name; });

    let total_eff = 0;

    if (filtered.length === 0) {
        $rows.html('<div class="grid-empty text-center text-muted" style="padding:20px; font-size:13px;">No rows</div>');
    } else {
        filtered.forEach(function (assn, i) {
            total_eff += flt(assn.effective_maximum_marks);
            let idx = i + 1;
            let assn_name = assn.name;
            let bg = i % 2 === 0 ? '#fff' : '#fafbfc';

            let grid_cols = '40px 2fr 1.5fr 1fr 1fr 1fr 1fr 1fr 60px 80px 36px';
            let $row = $(`
                <div class="grid-row" data-name="${assn_name}" style="display:grid; grid-template-columns:${grid_cols}; gap:0; align-items:center; padding:6px 10px; background:${bg}; border-bottom:1px solid #ededed;">
                    <div style="text-align:center; font-size:12px; color:#8d99ae;">${idx}</div>
                    <div style="padding:0 4px;">
                        <input type="text" class="form-control input-sm in-assn" value="${frappe.utils.escape_html(assn.assessment || '')}"
                            ${assn.assessment ? 'readonly style="background:transparent; border:none; font-weight:600; height:28px; font-size:12px; padding:0 4px;"' : 'placeholder="Assessment" style="height:28px; font-size:12px;"'} />
                    </div>
                    <div style="padding:0 4px;">
                        <input type="text" class="form-control input-sm in-label" value="${frappe.utils.escape_html(assn.label || '')}" placeholder="Label" style="height:28px; font-size:12px;" />
                    </div>
                    <div style="padding:0 4px;">
                        <input type="number" class="form-control input-sm in-eff" value="${assn.effective_maximum_marks || 0}" readonly
                            style="background:#f7f7f7; border:1px solid #eee; height:28px; font-size:12px; color:#666;" />
                    </div>
                    <div style="padding:0 4px;">
                        <input type="number" class="form-control input-sm in-weight" value="${assn.weightage || 0}" placeholder="0"
                            style="height:28px; font-size:12px;" />
                    </div>
                    <div style="padding:0 4px;">
                        <input type="number" class="form-control input-sm in-max" value="${assn.maximum_marks || 0}" placeholder="0"
                            style="height:28px; font-size:12px;" />
                    </div>
                    <div style="padding:0 4px;">
                        <input type="number" class="form-control input-sm in-min" value="${assn.minimum_marks || 0}" placeholder="0"
                            style="height:28px; font-size:12px;" />
                    </div>
                    <div style="padding:0 4px;">
                        <input type="number" class="form-control input-sm in-pass" value="${assn.passing_marks || 0}" placeholder="0"
                            style="height:28px; font-size:12px;" />
                    </div>
                    <div style="text-align:center;">
                        <input type="checkbox" class="in-cons" ${assn.consider_for_pass_fail ? 'checked' : ''}
                            style="width:15px; height:15px; cursor:pointer;" />
                    </div>
                    <div style="padding:0 4px;">
                        <select class="form-control input-sm in-enroll" style="height:28px; font-size:12px;">
                            <option value="Auto" ${assn.requires_enrolment === 'Auto' ? 'selected' : ''}>Auto</option>
                            <option value="Manual" ${assn.requires_enrolment === 'Manual' ? 'selected' : ''}>Manual</option>
                        </select>
                    </div>
                    <div style="text-align:center;">
                        <button class="btn btn-xs btn-icon del-assess" title="Delete" style="color:#b0b8c5; background:transparent; border:none; padding:4px;">
                            <i class="fa fa-trash-o"></i>
                        </button>
                    </div>
                </div>
            `);

            // ── Row change events ──
            $row.find('input, select').on('change', function () {
                let doc = locals['Exam Schema Assessment'][assn_name];
                if (!doc) return;
                doc.label = $row.find('.in-label').val();
                doc.maximum_marks = flt($row.find('.in-max').val());
                doc.minimum_marks = flt($row.find('.in-min').val());
                doc.passing_marks = flt($row.find('.in-pass').val());
                doc.consider_for_pass_fail = $row.find('.in-cons').is(':checked') ? 1 : 0;
                doc.weightage = flt($row.find('.in-weight').val());
                doc.requires_enrolment = $row.find('.in-enroll').val();
                // Auto-calc: Effective Max = Max Marks
                doc.effective_maximum_marks = flt(doc.maximum_marks);
                frm.dirty();
                render_grid_rows(frm, comp_name, $section, expected_marks);
            });

            // ── Delete ──
            $row.find('.del-assess').on('click', function () {
                let grid = frm.get_field('assessments').grid;
                if (grid && grid.grid_rows) {
                    let gr = grid.grid_rows.find(function (r) { return r.doc.name === assn_name; });
                    if (gr) {
                        gr.remove();
                        frm.refresh_field('assessments');
                        render_grid_rows(frm, comp_name, $section, expected_marks);
                        return;
                    }
                }
                frappe.model.clear_doc('Exam Schema Assessment', assn_name);
                frm.doc.assessments = (frm.doc.assessments || []).filter(function (a) { return a.name !== assn_name; });
                frm.dirty();
                render_grid_rows(frm, comp_name, $section, expected_marks);
            });

            $rows.append($row);
        });
    }

    // Update total + validation
    $section.find('.assess-total-box').text(total_eff);
    let $val = $section.find('.assess-validation');
    if (total_eff !== expected_marks) {
        $val.html('<span style="color:#e74c3c;"><i class="fa fa-info-circle"></i> Sum of effective maximum marks must be equal to component effective total marks = ' + expected_marks + '</span>');
    } else if (expected_marks > 0) {
        $val.html('<span style="color:#27ae60;"><i class="fa fa-check-circle"></i> Total matches component marks (' + expected_marks + ')</span>');
    } else {
        $val.html('<span style="color:#e74c3c;"><i class="fa fa-info-circle"></i> Set component weightage first</span>');
    }
}

// ═══════════════════════════════════════════════════════════════════
//  RE-EXAM / MAKEUP GRID (fewer columns + substitution settings)
// ═══════════════════════════════════════════════════════════════════

function build_reexam_grid(frm, comp_row, section_id, comp_type) {
    let comp_name = comp_row.exam_component;
    let label = comp_row.label || comp_name;
    let badge_bg = get_badge_color(comp_type);
    let gcols = '2fr 1.5fr 1.2fr 1fr 1fr 1fr 36px';

    /* ── shell ─────────────────────────────────────────────────── */
    let $section = $(`
        <div class="frappe-control reexam-grid-section"
             data-component="${frappe.utils.escape_html(comp_name)}"
             style="margin-top:25px;">
          <div class="form-group">

            <!-- header -->
            <div class="clearfix">
              <label class="control-label"
                     style="display:flex;justify-content:space-between;align-items:center;padding-right:0;">
                <span style="font-size:14px;font-weight:600;">
                  ${frappe.utils.escape_html(comp_name)} | ${frappe.utils.escape_html(label)}
                </span>
                <span style="display:flex;align-items:center;gap:8px;">
                  <select class="form-control input-sm sub-type-select"
                          style="height:26px;font-size:11px;width:auto;min-width:130px;
                                 border:1px solid #d1d8dd;border-radius:4px;">
                    <option value="Component">Component</option>
                    <option value="Assessment">Assessment</option>
                  </select>
                  <span style="font-size:11px;color:#fff;background:${badge_bg};
                               border-radius:12px;padding:2px 12px;font-weight:500;">
                    ${frappe.utils.escape_html(comp_type)}
                  </span>
                </span>
              </label>
            </div>

            <!-- grid table -->
            <div class="grid-body"
                 style="border:1px solid #d1d8dd;border-radius:4px;background:#fff;">
              <div class="grid-heading-row"
                   style="display:grid;grid-template-columns:${gcols};gap:0;
                          align-items:center;background:#f7f8fa;
                          border-bottom:1px solid #d1d8dd;
                          padding:8px 15px;font-weight:600;font-size:11px;color:#8d99ae;">
                <div>Assessment</div><div>Label</div>
                <div>Maximum Marks</div><div>Minimum Marks</div>
                <div>Passing Marks</div><div>Enrollment</div><div></div>
              </div>
              <div class="grid-rows"></div>
            </div>

            <!-- "Add New Assessment" dropdown at bottom -->
            <div style="margin-top:10px;padding:4px 0;">
              <div style="position:relative;display:inline-block;">
                <button class="btn btn-xs add-assess-btn"
                        style="color:#e67e22;border:1.5px dashed #e67e22;
                               background:#fff8f0;border-radius:6px;
                               padding:6px 18px;font-weight:600;cursor:pointer;
                               font-size:12px;">
                  Add New Assessment ▾
                </button>
                <div class="assess-dropdown"
                     style="display:none;position:absolute;left:0;top:100%;
                            z-index:1060;background:#fff;border:1px solid #d1d8dd;
                            border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.12);
                            min-width:260px;max-height:320px;overflow-y:auto;
                            margin-top:4px;">
                  <div style="padding:8px;">
                    <input type="text" class="assess-search"
                           placeholder="Search assessment"
                           style="width:100%;padding:6px 10px;border:1px solid #d1d8dd;
                                  border-radius:4px;font-size:13px;outline:none;" />
                  </div>
                  <div class="assess-list-items" style="padding:0 4px 8px;"></div>
                </div>
              </div>
            </div>

          </div>
        </div>
    `);

    $('#' + section_id).html('').append($section);

    /* ── state ──────────────────────────────────────────────────── */
    $section.data('sub_type', 'Component');

    /* ── header dropdown toggles Substitute For everywhere ─────── */
    $section.find('.sub-type-select').on('change', function () {
        var new_type = $(this).val();
        $section.data('sub_type', new_type);
        $section.find('.sub-for-container').each(function () {
            var $c = $(this);
            var name = $c.closest('.grid-row-wrap').data('name');
            load_substitute_options(frm, comp_name, $c, new_type, name);
        });
    });

    /* ── draw rows ────────────────────────────────────────── */
    render_reexam_rows(frm, comp_name, $section);

    /* ── "Add New Assessment" button logic ──────────────────── */
    var $btn = $section.find('.add-assess-btn');
    var $dd = $section.find('.assess-dropdown');

    $btn.on('click', function (e) {
        e.stopPropagation();
        $('.assess-dropdown').not($dd).hide();
        $('#component-dropdown').hide();
        if ($dd.is(':visible')) {
            $dd.hide();
        } else {
            load_reexam_assessment_dropdown(frm, comp_name, $section);
            $dd.show();
            $section.find('.assess-search').focus();
        }
    });

    $(document).off('click.rdd_' + comp_name)
        .on('click.rdd_' + comp_name, function (e) {
            if (!$(e.target).closest('.add-assess-btn, .assess-dropdown').length) {
                $dd.hide();
            }
        });

    $section.find('.assess-search').on('input', function () {
        var q = $(this).val().toLowerCase();
        $section.find('.assess-dd-item').each(function () {
            $(this).toggle($(this).text().toLowerCase().indexOf(q) !== -1);
        });
    });
}

/* ── Populate "Substitute For" select ──────────────────────────── */
function load_substitute_options(frm, comp_name, $container, sub_type, assn_name) {
    var $sel = $container.find('.in-sub-for');
    $sel.empty();

    if (sub_type === 'Component') {
        $sel.append('<option value="">Select Substitute Component</option>');
        (frm.doc.components || []).forEach(function (c) {
            if (c.exam_component && c.exam_component !== comp_name) {
                var doc = assn_name ? (locals['Exam Schema Assessment'] || {})[assn_name] : null;
                var s = (doc && doc.substitute_component === c.exam_component) ? ' selected' : '';
                $sel.append('<option value="' + c.exam_component + '"' + s + '>' +
                    frappe.utils.escape_html(c.exam_component) + '</option>');
            }
        });
    } else {
        $sel.append('<option value="">Select Substitute Exam</option>');
        (frm.doc.assessments || []).forEach(function (a) {
            if (a.exam_component !== comp_name && a.assessment) {
                var doc = assn_name ? (locals['Exam Schema Assessment'] || {})[assn_name] : null;
                var s = (doc && doc.substitute_assessment === a.assessment) ? ' selected' : '';
                var txt = a.assessment + ' (' + a.exam_component + ')';
                $sel.append('<option value="' + a.assessment + '"' +
                    ' data-component="' + a.exam_component + '"' + s + '>' +
                    frappe.utils.escape_html(txt) + '</option>');
            }
        });
    }
}

/* ── Render assessment rows inside Re-Exam grid ────────────────── */
function render_reexam_rows(frm, comp_name, $section) {
    var $rows = $section.find('.grid-rows');
    $rows.empty();

    var filtered = (frm.doc.assessments || []).filter(function (a) {
        return a.exam_component === comp_name;
    });
    var sub_type = $section.data('sub_type') || 'Component';
    var gcols = '2fr 1.5fr 1.2fr 1fr 1fr 1fr 36px';

    if (!filtered.length) {
        $section.find('.grid-body').hide();
        return;
    }
    $section.find('.grid-body').show();

    filtered.forEach(function (assn, i) {
        var nm = assn.name;
        var bg = i % 2 === 0 ? '#fff' : '#fafbfc';

        var $row = $([
            '<div class="grid-row-wrap" data-name="' + nm + '">',

            /* ── data columns ───────────────────────────────── */
            '  <div class="grid-row" style="display:grid;grid-template-columns:' + gcols + ';',
            '       gap:0;align-items:center;padding:10px 15px;background:' + bg + ';',
            '       border-bottom:1px solid #ededed;">',
            '    <div style="padding:0 4px;">',
            '      <div style="font-weight:600;font-size:13px;color:#36414c;">',
            frappe.utils.escape_html(assn.assessment || ''),
            '      </div>',
            '      <div style="margin-top:3px;">',
            '        <span style="font-size:10px;color:#fff;background:#e74c3c;',
            '               border-radius:8px;padding:1px 8px;">ReExam/Makup</span>',
            '      </div>',
            '    </div>',
            '    <div style="padding:0 4px;">',
            '      <input type="text" class="form-control input-sm in-label"',
            '             value="' + frappe.utils.escape_html(assn.label || '') + '"',
            '             placeholder="Label" style="height:30px;font-size:12px;" />',
            '    </div>',
            '    <div style="padding:0 4px;">',
            '      <input type="number" class="form-control input-sm in-max"',
            '             value="' + (assn.maximum_marks || 0) + '"',
            '             style="height:30px;font-size:12px;" />',
            '    </div>',
            '    <div style="padding:0 4px;">',
            '      <input type="number" class="form-control input-sm in-min"',
            '             value="' + (assn.minimum_marks || 0) + '"',
            '             style="height:30px;font-size:12px;" />',
            '    </div>',
            '    <div style="padding:0 4px;">',
            '      <input type="number" class="form-control input-sm in-pass"',
            '             value="' + (assn.passing_marks || 0) + '"',
            '             style="height:30px;font-size:12px;" />',
            '    </div>',
            '    <div style="padding:0 4px;">',
            '      <select class="form-control input-sm in-enroll" style="height:30px;font-size:12px;">',
            '        <option value="Auto"' + (assn.requires_enrolment === 'Auto' ? ' selected' : '') + '>Auto</option>',
            '        <option value="Manual"' + (assn.requires_enrolment === 'Manual' ? ' selected' : '') + '>Manual</option>',
            '      </select>',
            '    </div>',
            '    <div style="text-align:center;">',
            '      <button class="btn btn-xs btn-icon del-assess" title="Delete"',
            '              style="color:#e74c3c;background:transparent;border:none;',
            '                     padding:4px;font-size:14px;">',
            '        <i class="fa fa-trash-o"></i>',
            '      </button>',
            '    </div>',
            '  </div>',

            /* ── toggle link ────────────────────────────────── */
            '  <div style="text-align:right;padding:4px 15px;">',
            '    <a href="#" class="toggle-sub-link"',
            '       style="font-size:12px;color:#5e64ff;text-decoration:none;',
            '              font-weight:500;">Hide Substitution Settings</a>',
            '  </div>',

            /* ── substitution panel (open by default) ───────── */
            '  <div class="sub-settings"',
            '       style="margin:0 15px 4px;padding:18px 20px;',
            '              border:1px solid #edf2f7;border-radius:6px;background:#fafbfc;">',

            '    <div class="sub-header" style="display:grid;grid-template-columns:2fr 1.2fr 1fr 1.5fr 36px;',
            '                gap:16px;font-size:12px;font-weight:600;color:#8d99ae;',
            '                margin-bottom:10px;">',
            '      <div>Substitute For</div>',
            '      <div>Weightage</div>',
            '      <div>Effective marks</div>',
            '      <div>Substitute assessment effective marks</div>',
            '      <div></div>',
            '    </div>',

            '    <div class="sub-rows-container"></div>',

            '    <div style="margin-top:10px;">',
            '      <button class="btn btn-xs btn-add-more-sub"',
            '              style="color:#e67e22;border:1.5px dashed #e67e22;',
            '                     background:#fff8f0;border-radius:6px;',
            '                     padding:4px 14px;font-weight:600;cursor:pointer;',
            '                     font-size:11px;">+Add More</button>',
            '      <span style="margin-left:12px;font-size:11px;color:#e67e22;font-style:italic;">',
            '        Substitute exam effective marks must be less than or equal to the effective maximum marks of assessment',
            '      </span>',
            '    </div>',

            '  </div>',

            /* ── note ───────────────────────────────────────── */
            '  <div class="reexam-note"',
            '       style="padding:4px 15px 10px;font-size:11px;color:#8d99ae;font-style:italic;">',
            '    If a student is enrolled for this component, his/her marks will be distributed as per the above schema.',
            '  </div>',

            '</div>'
        ].join('\n'));

        /* ── helper: add a substitution row ──────────────── */
        function add_sub_row($container, sub_type, data) {
            data = data || {};
            var row_id = 'sub_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
            var $sr = $([
                '<div class="sub-row" data-subid="' + row_id + '"',
                '     style="display:grid;grid-template-columns:2fr 1.2fr 1fr 1.5fr 36px;',
                '            gap:16px;align-items:center;margin-bottom:8px;">',
                '  <div class="sub-for-container">',
                '    <select class="form-control input-sm in-sub-for"',
                '            style="height:30px;font-size:12px;">',
                '      <option value="">Select Substitute Component</option>',
                '    </select>',
                '  </div>',
                '  <div style="display:flex;align-items:center;gap:4px;">',
                '    <input type="number" class="form-control input-sm in-sub-weight"',
                '           value="' + (data.weightage || 0) + '"',
                '           style="height:30px;font-size:12px;" />',
                '    <span style="font-size:12px;color:#8d99ae;">%</span>',
                '  </div>',
                '  <div style="font-size:13px;color:#333;" class="eff-display">',
                (data.eff || 0),
                '  </div>',
                '  <div style="font-size:13px;color:#333;" class="sub-eff-display">',
                (data.sub_eff || 0),
                '  </div>',
                '  <div style="text-align:center;">',
                '    <button class="btn btn-xs btn-icon del-sub-row" title="Remove"',
                '            style="color:#e74c3c;background:transparent;border:none;',
                '                   padding:4px;font-size:13px;">',
                '      <i class="fa fa-times"></i>',
                '    </button>',
                '  </div>',
                '</div>'
            ].join('\n'));

            /* populate dropdown */
            load_substitute_options(frm, comp_name,
                $sr.find('.sub-for-container'), sub_type, nm);

            /* pre-select saved value */
            if (data.sub_val) {
                setTimeout(function () {
                    $sr.find('.in-sub-for').val(data.sub_val);
                }, 50);
            }

            /* change handler: auto-calc effective marks */
            $sr.find('input, select').on('change', function () {
                var doc = (locals['Exam Schema Assessment'] || {})[nm];
                var cur_type = $section.data('sub_type') || 'Component';
                var sv = $sr.find('.in-sub-for').val();
                var wt = flt($sr.find('.in-sub-weight').val());

                if (sv && wt) {
                    var tc_name = (cur_type === 'Component')
                        ? sv
                        : ($sr.find('.in-sub-for option:selected').data('component') || '');
                    var tc = (frm.doc.components || []).find(function (c) {
                        return c.exam_component === tc_name;
                    });
                    if (tc) {
                        var eff = flt(tc.effective_max_marks) * wt / 100;
                        $sr.find('.eff-display').text(eff);
                        $sr.find('.sub-eff-display').text(eff);
                    }
                }

                /* save first row to doc fields */
                var $first = $container.find('.sub-row').first();
                if ($sr.data('subid') === $first.data('subid') && doc) {
                    doc.substitution_type = cur_type;
                    var fv = $first.find('.in-sub-for').val();
                    if (cur_type === 'Component') {
                        doc.substitute_component = fv;
                        doc.substitute_assessment = '';
                    } else {
                        doc.substitute_assessment = fv;
                        doc.substitute_component =
                            $first.find('.in-sub-for option:selected').data('component') || '';
                    }
                    doc.substitute_weightage = flt($first.find('.in-sub-weight').val());
                    var effText = $first.find('.eff-display').text();
                    doc.substitute_effective_marks = flt(effText);
                    doc.substitute_assessment_effective_marks = flt(effText);
                }
                frm.dirty();
            });

            /* delete this sub row */
            $sr.find('.del-sub-row').on('click', function () {
                $sr.remove();
                frm.dirty();
            });

            $container.append($sr);
            return $sr;
        }

        /* ── toggle ────────────────────────────────────── */
        $row.find('.toggle-sub-link').on('click', function (e) {
            e.preventDefault();
            var $sub = $row.find('.sub-settings');
            var $note = $row.find('.reexam-note');
            if ($sub.is(':visible')) {
                $sub.slideUp(200); $note.slideUp(200);
                $(this).text('Show Substitution Settings');
            } else {
                $sub.slideDown(200); $note.slideDown(200);
                $(this).text('Hide Substitution Settings');
            }
        });

        /* ── main row changes ──────────────────────────── */
        $row.find('.grid-row').find('input, select').on('change', function () {
            var doc = (locals['Exam Schema Assessment'] || {})[nm];
            if (!doc) return;
            doc.label = $row.find('.in-label').val();
            doc.maximum_marks = flt($row.find('.in-max').val());
            doc.minimum_marks = flt($row.find('.in-min').val());
            doc.passing_marks = flt($row.find('.in-pass').val());
            doc.requires_enrolment = $row.find('.in-enroll').val();
            doc.effective_maximum_marks = flt(doc.maximum_marks);
            frm.dirty();
        });

        /* ── build initial sub row ───────────────────────── */
        var $subContainer = $row.find('.sub-rows-container');
        add_sub_row($subContainer, sub_type, {
            weightage: assn.substitute_weightage || 0,
            eff: assn.substitute_effective_marks || 0,
            sub_eff: assn.substitute_assessment_effective_marks || 0,
            sub_val: (sub_type === 'Component')
                ? (assn.substitute_component || '')
                : (assn.substitute_assessment || '')
        });

        /* ── +Add More button ────────────────────────────── */
        $row.find('.btn-add-more-sub').on('click', function () {
            var cur = $section.data('sub_type') || 'Component';
            add_sub_row($subContainer, cur, {});
        });

        /* ── delete ────────────────────────────────────── */
        $row.find('.del-assess').on('click', function () {
            var grid = frm.get_field('assessments').grid;
            if (grid && grid.grid_rows) {
                var gr = grid.grid_rows.find(function (r) {
                    return r.doc.name === nm;
                });
                if (gr) {
                    gr.remove();
                    frm.refresh_field('assessments');
                    render_reexam_rows(frm, comp_name, $section);
                    return;
                }
            }
            frappe.model.clear_doc('Exam Schema Assessment', nm);
            frm.doc.assessments = (frm.doc.assessments || []).filter(function (a) {
                return a.name !== nm;
            });
            frm.dirty();
            render_reexam_rows(frm, comp_name, $section);
        });

        $rows.append($row);
    });
}

/* ── "Add New Assessment" dropdown items ───────────────────────── */
function load_reexam_assessment_dropdown(frm, comp_name, $section) {
    var $list = $section.find('.assess-list-items');
    $list.html('<div style="padding:8px;color:#8d99ae;font-size:12px;">Loading…</div>');

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Exam Assessment',
            fields: ['name', 'assessment_name'],
            limit_page_length: 0
        },
        callback: function (r) {
            $list.empty();

            /* only block items already in THIS Re-Exam component */
            var mine = {};
            (frm.doc.assessments || []).forEach(function (a) {
                if (a.assessment && a.exam_component === comp_name) {
                    mine[a.assessment] = true;
                }
            });

            (r.message || []).forEach(function (assn) {
                var taken = !!mine[assn.name];
                var $item = $('<div class="assess-dd-item" style="padding:7px 12px;' +
                    'border-radius:4px;font-size:13px;display:flex;align-items:center;' +
                    'gap:8px;cursor:' + (taken ? 'default' : 'pointer') + ';' +
                    (taken ? 'opacity:.5;' : '') + '"></div>');

                $item.html(
                    '<span style="font-weight:500;">' +
                    frappe.utils.escape_html(assn.assessment_name || assn.name) +
                    '</span>' +
                    (taken ? '<span style="font-size:10px;color:#8d99ae;' +
                        'margin-left:auto;">Added</span>' : '')
                );

                if (!taken) {
                    $item.on('mouseenter', function () { $(this).css('background', '#f0f4ff'); });
                    $item.on('mouseleave', function () { $(this).css('background', ''); });
                    $item.on('click', function () {
                        var row = frm.add_child('assessments');
                        row.exam_component = comp_name;
                        row.assessment = assn.name;
                        row.label = assn.assessment_name || assn.name;
                        row.requires_enrolment = 'Manual';
                        frm.dirty();
                        $section.find('.assess-dropdown').hide();
                        render_reexam_rows(frm, comp_name, $section);
                    });
                }
                $list.append($item);
            });

            $list.append('<hr style="margin:4px 0;">');
            var $create = $('<div class="assess-dd-item" style="padding:7px 12px;' +
                'cursor:pointer;border-radius:4px;font-size:13px;color:#5e64ff;' +
                'font-weight:600;">+ Create New Assessment</div>');
            $create.on('mouseenter', function () { $(this).css('background', '#f0f4ff'); });
            $create.on('mouseleave', function () { $(this).css('background', ''); });
            $create.on('click', function () {
                $section.find('.assess-dropdown').hide();
                create_new_reexam_assessment(frm, comp_name, $section);
            });
            $list.append($create);
        }
    });
}

/* ── Dialog: create a brand-new Exam Assessment master record ──── */
function create_new_reexam_assessment(frm, comp_name, $section) {
    var d = new frappe.ui.Dialog({
        title: 'Create New Exam Assessment',
        fields: [{
            label: 'Assessment Name',
            fieldname: 'assessment_name',
            fieldtype: 'Data',
            reqd: 1
        }],
        primary_action_label: 'Create',
        primary_action: function (values) {
            frappe.call({
                method: 'frappe.client.insert',
                args: {
                    doc: {
                        doctype: 'Exam Assessment',
                        assessment_name: values.assessment_name
                    }
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Assessment "{0}" created',
                                [values.assessment_name]),
                            indicator: 'green'
                        });
                        var row = frm.add_child('assessments');
                        row.exam_component = comp_name;
                        row.assessment = r.message.name;
                        row.label = r.message.assessment_name;
                        row.requires_enrolment = 'Manual';
                        frm.dirty();
                        render_reexam_rows(frm, comp_name, $section);
                        d.hide();
                    }
                }
            });
        }
    });
    d.show();
}

// ─── Dropdown: list of Exam Assessment master records ────────────
function load_assessment_dropdown(frm, comp_name, $section, expected_marks) {
    let $list = $section.find('.assess-list-items');
    $list.html('<div style="padding:8px; color:#8d99ae; font-size:12px;">Loading...</div>');

    frappe.call({
        method: 'frappe.client.get_list',
        args: { doctype: 'Exam Assessment', fields: ['name', 'assessment_name'], limit_page_length: 0 },
        callback: function (r) {
            $list.empty();
            // Build map of ALL used assessments across ALL components
            let used_map = {};
            (frm.doc.assessments || []).forEach(function (a) {
                if (a.assessment) { used_map[a.assessment] = a.exam_component; }
            });

            if (r.message && r.message.length) {
                r.message.forEach(function (assn) {
                    let used_in = used_map[assn.name];
                    let already = !!used_in;
                    let badge_text = already ? (used_in === comp_name ? 'Added' : 'Used in ' + used_in) : '';
                    let $item = $('<div class="assess-dd-item" style="padding:7px 12px; border-radius:4px; font-size:13px; display:flex; align-items:center; gap:8px; cursor:' + (already ? 'default' : 'pointer') + '; ' + (already ? 'opacity:0.5;' : '') + '"></div>');
                    $item.html('<span style="font-weight:500;">' + frappe.utils.escape_html(assn.assessment_name || assn.name) + '</span>' + (already ? '<span style="font-size:10px; color:#8d99ae; margin-left:auto;">' + badge_text + '</span>' : ''));

                    if (!already) {
                        $item.on('mouseenter', function () { $(this).css('background', '#f0f4ff'); });
                        $item.on('mouseleave', function () { $(this).css('background', 'transparent'); });
                        $item.on('click', function () {
                            let row = frm.add_child('assessments');
                            row.exam_component = comp_name;
                            row.assessment = assn.name;
                            row.label = assn.assessment_name || assn.name;
                            row.requires_enrolment = 'Auto';
                            frm.dirty();
                            $section.find('.assess-dropdown').hide();
                            render_grid_rows(frm, comp_name, $section, expected_marks);
                        });
                    }
                    $list.append($item);
                });
            }

            $list.append('<hr style="margin:4px 0;">');
            let $create = $('<div class="assess-dd-item" style="padding:7px 12px; cursor:pointer; border-radius:4px; font-size:13px; color:#5e64ff; font-weight:600;">+ Create New Assessment</div>');
            $create.on('mouseenter', function () { $(this).css('background', '#f0f4ff'); });
            $create.on('mouseleave', function () { $(this).css('background', 'transparent'); });
            $create.on('click', function () {
                $section.find('.assess-dropdown').hide();
                create_new_assessment(frm, comp_name, $section, expected_marks);
            });
            $list.append($create);
        }
    });
}

function create_new_assessment(frm, comp_name, $section, expected_marks) {
    let d = new frappe.ui.Dialog({
        title: 'Create New Exam Assessment',
        fields: [{ label: 'Assessment Name', fieldname: 'assessment_name', fieldtype: 'Data', reqd: 1 }],
        primary_action_label: 'Create',
        primary_action: function (values) {
            frappe.call({
                method: 'frappe.client.insert',
                args: { doc: { doctype: 'Exam Assessment', assessment_name: values.assessment_name } },
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({ message: __('Assessment "{0}" created', [values.assessment_name]), indicator: 'green' });
                        let row = frm.add_child('assessments');
                        row.exam_component = comp_name;
                        row.assessment = r.message.name;
                        row.label = r.message.assessment_name;
                        row.requires_enrolment = 'Auto';
                        frm.dirty();
                        render_grid_rows(frm, comp_name, $section, expected_marks);
                        d.hide();
                    }
                }
            });
        }
    });
    d.show();
}

// ═══════════════════════════════════════════════════════════════════
//  COMPONENT HELPERS
// ═══════════════════════════════════════════════════════════════════

function load_component_list(frm, $footer) {
    let $list = $footer.find('#component-list');
    $list.html('<div style="padding:8px; color:#8d99ae; font-size:12px;">Loading...</div>');

    frappe.call({
        method: 'frappe.client.get_list',
        args: { doctype: 'Exam Component', fields: ['name', 'component_name', 'component_type'], limit_page_length: 0, order_by: 'component_name asc' },
        async: false,
        callback: function (r) {
            $list.empty();
            let existing = (frm.doc.components || []).map(function (row) { return row.exam_component; });

            if (r.message && r.message.length) {
                r.message.forEach(function (comp) {
                    let added = existing.includes(comp.name);
                    let badge = get_badge_color(comp.component_type);
                    let $item = $('<div class="component-item" style="padding:7px 12px; cursor:' + (added ? 'default' : 'pointer') + '; border-radius:4px; font-size:13px; display:flex; align-items:center; gap:8px; ' + (added ? 'opacity:0.5;' : '') + '"></div>');
                    $item.html('<span style="color:' + badge + '; font-weight:500;">' + frappe.utils.escape_html(comp.component_name) + '</span> <span style="font-size:11px; color:#8d99ae;">(' + frappe.utils.escape_html(comp.component_type || 'Custom') + ')</span>' + (added ? '<span style="font-size:10px; color:#8d99ae; margin-left:auto;">Added</span>' : ''));

                    if (!added) {
                        $item.on('mouseenter', function () { $(this).css('background', '#f0f4ff'); });
                        $item.on('mouseleave', function () { $(this).css('background', 'transparent'); });
                        $item.on('click', function () {
                            add_component_row(frm, comp);
                            $footer.find('#component-dropdown').hide();
                        });
                    }
                    $list.append($item);
                });
            }

            $list.append('<hr style="margin:4px 0;">');
            let $create = $('<div class="component-item" style="padding:7px 12px; cursor:pointer; border-radius:4px; font-size:13px; color:#5e64ff; font-weight:600;">+ Create New Component</div>');
            $create.on('mouseenter', function () { $(this).css('background', '#f0f4ff'); });
            $create.on('mouseleave', function () { $(this).css('background', 'transparent'); });
            $create.on('click', function () {
                $footer.find('#component-dropdown').hide();
                create_new_component(frm);
            });
            $list.append($create);
        }
    });
}

function get_badge_color(type) {
    return { 'Custom': '#27ae60', 'Re Exam': '#e74c3c', 'Makeup': '#e67e22' }[type] || '#27ae60';
}

function add_component_row(frm, comp) {
    let row = frm.add_child('components');
    frappe.model.set_value(row.doctype, row.name, 'exam_component', comp.name);
    frappe.model.set_value(row.doctype, row.name, 'label', comp.component_name);
    frm.refresh_field('components');
    render_components_footer(frm);
    calculate_total_effective_marks(frm);
}

function add_all_components(frm, $footer) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: { doctype: 'Exam Component', fields: ['name', 'component_name', 'component_type'], limit_page_length: 0, order_by: 'component_name asc' },
        callback: function (r) {
            if (r.message) {
                let existing = (frm.doc.components || []).map(function (row) { return row.exam_component; });
                r.message.forEach(function (comp) {
                    if (!existing.includes(comp.name)) { add_component_row(frm, comp); }
                });
            }
            $footer.find('#component-dropdown').hide();
        }
    });
}

function create_new_component(frm) {
    let d = new frappe.ui.Dialog({
        title: 'Create New Exam Component',
        fields: [
            { label: 'Component Name', fieldname: 'component_name', fieldtype: 'Data', reqd: 1 },
            { label: 'Component Type', fieldname: 'component_type', fieldtype: 'Select', options: 'Custom\nRe Exam\nMakeup', default: 'Custom', reqd: 1 }
        ],
        primary_action_label: 'Create',
        primary_action: function (values) {
            frappe.call({
                method: 'frappe.client.insert',
                args: { doc: { doctype: 'Exam Component', component_name: values.component_name, component_type: values.component_type } },
                callback: function (r) {
                    if (r.message) {
                        frappe.show_alert({ message: __('Component "{0}" created', [values.component_name]), indicator: 'green' });
                        add_component_row(frm, { name: r.message.name, component_name: r.message.component_name, component_type: r.message.component_type });
                        d.hide();
                    }
                }
            });
        }
    });
    d.show();
}

// ─── Calculation ──────────────────────────────────────────────────
function calculate_total_effective_marks(frm) {
    let total = 0;
    (frm.doc.components || []).forEach(function (row) { total += flt(row.effective_max_marks) || 0; });
    frm.set_value('total_effective_marks', total);
    render_components_footer(frm);
}

// ─── Grid UI Hooks (badges + Re-Exam dashes) ────────────────────
function setup_components_grid(frm) {
    if (!frm.fields_dict.components || !frm.fields_dict.components.grid) return;

    let grid = frm.fields_dict.components.grid;
    let old_render = grid.render;

    grid.render = function () {
        old_render.call(this);
        (grid.grid_rows || []).forEach(function (row) {
            if (!row.doc || !row.doc.exam_component) return;
            frappe.db.get_value('Exam Component', row.doc.exam_component, 'component_type', function (r) {
                if (!r || !row.row) return;
                let type = r.component_type || 'Custom';
                if (type === 'Re Exam') {
                    disable_and_dash_field(row, 'effective_max_marks');
                    disable_and_dash_field(row, 'weightage');
                    disable_and_dash_field(row, 'passing_marks');
                    disable_and_dash_field(row, 'consider_for_pass_fail');
                }
                let $cell = $(row.row).find('[data-fieldname="exam_component"]');
                if ($cell.length && !$cell.find('.badge-comp-type').length) {
                    let html = '<div class="badge-comp-type" style="margin-top:2px; font-size:10px; color:#fff; background:' + get_badge_color(type) + '; border-radius:12px; padding:2px 8px; display:inline-block;">' + type + '</div>';
                    ($cell.find('.control-input-wrapper').length ? $cell.find('.control-input-wrapper') : $cell).append(html);
                }
            });
        });
    };
    grid.refresh();
}

function disable_and_dash_field(row, fieldname) {
    let $cell = $(row.row).find('[data-fieldname="' + fieldname + '"]');
    if (!$cell.length) return;
    $cell.find('.control-input, .grid-static-col').empty().html('<div style="text-align:left; color:#8d99ae; padding:4px 0px;">--</div>');
    $cell.find('.control-value').hide();
    $cell.css('pointer-events', 'none');
}

// ─── Child Table Events: Components ──────────────────────────────
frappe.ui.form.on('Exam Schema Component', {
    exam_component: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.exam_component) {
            frappe.db.get_value('Exam Component', row.exam_component, ['component_name', 'component_type'], function (r) {
                if (r) {
                    frappe.model.set_value(cdt, cdn, 'label', r.component_name);
                    render_components_footer(frm);
                }
            });
        }
    },
    effective_max_marks: function (frm) { calculate_total_effective_marks(frm); },
    weightage: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        if (row.weightage && frm.doc.total_marks) {
            frappe.model.set_value(cdt, cdn, 'effective_max_marks', flt(frm.doc.total_marks) * flt(row.weightage) / 100);
        }
    },
    components_remove: function (frm) {
        calculate_total_effective_marks(frm);
        render_components_footer(frm);
    }
});
