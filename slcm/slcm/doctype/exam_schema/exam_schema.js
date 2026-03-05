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
//  ASSESSMENT SECTIONS — one Frappe-styled grid per Custom component
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
            if (r && r.component_type === 'Custom') {
                build_assessment_grid(frm, comp_row, section_id);
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

// ─── Dropdown: list of Exam Assessment master records ────────────
function load_assessment_dropdown(frm, comp_name, $section, expected_marks) {
    let $list = $section.find('.assess-list-items');
    $list.html('<div style="padding:8px; color:#8d99ae; font-size:12px;">Loading...</div>');

    frappe.call({
        method: 'frappe.client.get_list',
        args: { doctype: 'Exam Assessment', fields: ['name', 'assessment_name'], limit_page_length: 0 },
        callback: function (r) {
            $list.empty();
            let existing = (frm.doc.assessments || []).filter(function (a) { return a.exam_component === comp_name; }).map(function (a) { return a.assessment; });

            if (r.message && r.message.length) {
                r.message.forEach(function (assn) {
                    let already = existing.includes(assn.name);
                    let $item = $('<div class="assess-dd-item" style="padding:7px 12px; border-radius:4px; font-size:13px; display:flex; align-items:center; gap:8px; cursor:' + (already ? 'default' : 'pointer') + '; ' + (already ? 'opacity:0.5;' : '') + '"></div>');
                    $item.html('<span style="font-weight:500;">' + frappe.utils.escape_html(assn.assessment_name || assn.name) + '</span>' + (already ? '<span style="font-size:10px; color:#8d99ae; margin-left:auto;">Added</span>' : ''));

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
