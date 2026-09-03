frappe.listview_settings['Student Course Marks'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__('Bulk Import Marks'), function () {
            open_marks_import_dialog();
        });
    }
};

function open_marks_import_dialog() {
    let current_step = 1;
    let import_log = null;
    let missing_student_count = 0;
    let missing_course_count = 0;
    let missing_off_count = 0;
    let preview_page = 1;
    let is_importing = false;

    // Step 1 values
    let selected_file_url = null;
    let selected_exam_plan = null;
    let selected_eval_schema = null;
    let selected_exam_component = null;
    let selected_assessment_type = null;
    let selected_re_exam_component = null;
    let selected_re_exam_assessment_type = null;

    let d = new frappe.ui.Dialog({
        title: __('Bulk Import Student Marks'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'stepper_html',
                options: `
                    <style>
                        .import-stepper { display: flex; justify-content: space-between; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #d1d8dd; padding-left: 50px; padding-right: 50px; }
                        .step-item { display: flex; align-items: center; cursor: pointer; color: #8D99A6; transition: all 0.2s; }
                        .step-item.active { color: #1F272E; font-weight: bold; }
                        .step-item.completed { color: #28a745; }
                        .step-item.failed { color: #dc3545; }
                        .step-item.disabled { cursor: not-allowed; opacity: 0.6; }
                        .step-circle { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 8px; background: #F3F3F3; font-size: 12px; }
                        .step-item.active .step-circle { background: #1F272E; color: white; }
                        .step-item.completed .step-circle { background: #28a745; color: white; }
                        .step-item.failed .step-circle { background: #dc3545; color: white; }
                    </style>
                    <div class="import-stepper" id="dialog-stepper">
                        <div class="step-item active" data-step="1"><div class="step-circle">1</div> Upload</div>
                        <div class="step-item disabled" data-step="2"><div class="step-circle">2</div> Preview</div>
                        <div class="step-item disabled" data-step="3"><div class="step-circle">3</div> Validate</div>
                        <div class="step-item disabled" data-step="4"><div class="step-circle">4</div> Import</div>
                    </div>
                `
            },
            {
                fieldtype: 'HTML',
                fieldname: 'step_container',
                options: `<div id="step-render-area"></div>`
            }
        ],
        primary_action_label: __('Next'),
        primary_action: function () {
            handle_next();
        },
        secondary_action_label: __('Previous'),
        secondary_action: function () {
            if (current_step > 1 && !is_importing) {
                render_step(current_step - 1);
            } else if (current_step === 1) {
                d.hide();
            }
        }
    });

    let step_1_controls = {};

    function update_stepper(step) {
        let stepper = d.wrapper.find('#dialog-stepper');
        for (let i = 1; i <= 4; i++) {
            let el = stepper.find(`[data-step="${i}"]`);
            el.removeClass('active completed failed disabled');

            if (i < step) {
                el.addClass('completed');
                el.find('.step-circle').html('&#10003;'); // checkmark
            } else if (i === step) {
                el.addClass('active');
                el.find('.step-circle').html(i);
            } else {
                el.addClass('disabled');
                el.find('.step-circle').html(i);
            }
        }
    }

    function bind_stepper_clicks() {
        d.wrapper.find('.step-item').on('click', function () {
            if (is_importing) return;
            let target_step = parseInt($(this).attr('data-step'));
            if (target_step < current_step) {
                render_step(target_step);
            }
        });
    }

    function render_step(step) {
        current_step = step;
        update_stepper(step);
        let container = $(d.fields_dict.step_container.wrapper).find('#step-render-area');
        container.empty();

        if (step === 1) {
            d.set_primary_action(__('Next'));
            d.get_secondary_btn().hide();
            d.get_close_btn().show();

            let wrapper = $(`
                <div>
                    <h4>Step 1: Upload File & Select Schema</h4>
                    <p class="text-muted">The file must have exactly matching columns.</p>
                    <p><button id="download-template" class="btn btn-primary btn-sm">Download Sample Template</button></p>
                    <div id="step1-fields"></div>
                </div>
            `);
            container.append(wrapper);

            wrapper.find('#download-template').on('click', function (e) {
                e.preventDefault();
                window.open(frappe.urllib.get_full_url('/api/method/slcm.slcm.doctype.student_course_marks.marks_bulk_import.download_sample_template'));
            });

            let fields_wrapper = wrapper.find('#step1-fields');

            let row1 = $('<div class="row"></div>').appendTo(fields_wrapper);
            let col1 = $('<div class="col-sm-4"></div>').appendTo(row1);
            let col2 = $('<div class="col-sm-4"></div>').appendTo(row1);
            let col3 = $('<div class="col-sm-4"></div>').appendTo(row1);

            step_1_controls.import_file = frappe.ui.form.make_control({
                df: { fieldtype: 'Attach', fieldname: 'import_file', label: 'Import File', reqd: 1 },
                parent: col1,
                render_input: true
            });
            if (selected_file_url) step_1_controls.import_file.set_input(selected_file_url);

            step_1_controls.exam_plan = frappe.ui.form.make_control({
                df: { fieldtype: 'Link', fieldname: 'exam_plan', label: 'Exam Plan', options: 'Exam Plan', reqd: 1 },
                parent: col2,
                render_input: true
            });
            if (selected_exam_plan) step_1_controls.exam_plan.set_input(selected_exam_plan);

            step_1_controls.eval_schema = frappe.ui.form.make_control({
                df: { fieldtype: 'Link', fieldname: 'evaluation_schema', label: 'Evaluation Schema', options: 'Evaluation Schema', reqd: 1 },
                parent: col3,
                render_input: true
            });
            if (selected_eval_schema) step_1_controls.eval_schema.set_input(selected_eval_schema);

            let exam_wrapper = $('<div class="exam-section" style="margin-top: 15px; border-top: 1px solid #d1d8dd; padding-top: 15px;"><h5>Exam</h5></div>').appendTo(fields_wrapper);
            let row2 = $('<div class="row"></div>').appendTo(exam_wrapper);
            let col4 = $('<div class="col-sm-6"></div>').appendTo(row2);
            let col5 = $('<div class="col-sm-6"></div>').appendTo(row2);

            step_1_controls.exam_component = frappe.ui.form.make_control({
                parent: col4,
                df: { fieldname: 'exam_component', fieldtype: 'Link', options: 'Exam Component', label: 'Exam Component', reqd: 1 },
                render_input: true
            });
            if (selected_exam_component) step_1_controls.exam_component.set_input(selected_exam_component);

            step_1_controls.assessment_type = frappe.ui.form.make_control({
                parent: col5,
                df: { fieldname: 'assessment_type', fieldtype: 'Link', options: 'Exam Assessment Type', label: 'Assessment Type', reqd: 1 },
                render_input: true
            });
            if (selected_assessment_type) step_1_controls.assessment_type.set_input(selected_assessment_type);

            let re_exam_wrapper = $('<div class="re-exam-section" style="margin-top: 15px; border-top: 1px solid #d1d8dd; padding-top: 15px;"><h5>Re Exam</h5></div>').appendTo(fields_wrapper);
            let row3 = $('<div class="row"></div>').appendTo(re_exam_wrapper);
            let col6 = $('<div class="col-sm-6"></div>').appendTo(row3);
            let col7 = $('<div class="col-sm-6"></div>').appendTo(row3);

            step_1_controls.re_exam_component = frappe.ui.form.make_control({
                parent: col6,
                df: { fieldname: 're_exam_component', fieldtype: 'Link', options: 'Exam Component', label: 'Exam Component', reqd: 1 },
                render_input: true
            });
            step_1_controls.re_exam_component.get_query = function () { return { filters: { component_type: 'Re Exam' } }; };
            if (selected_re_exam_component) step_1_controls.re_exam_component.set_input(selected_re_exam_component);

            step_1_controls.re_exam_assessment_type = frappe.ui.form.make_control({
                parent: col7,
                df: { fieldname: 're_exam_assessment_type', fieldtype: 'Link', options: 'Exam Assessment Type', label: 'Assessment Type', reqd: 1 },
                render_input: true
            });
            step_1_controls.re_exam_assessment_type.get_query = function () { return { filters: { assessment_type: 'ReExam/Makeup Assessment' } }; };
            if (selected_re_exam_assessment_type) step_1_controls.re_exam_assessment_type.set_input(selected_re_exam_assessment_type);

        } else if (step === 2) {
            d.set_primary_action(__('Validate'));
            d.get_secondary_btn().show().text(__('Previous'));
            d.get_close_btn().show();

            let wrapper = $(`
                <div>
                    <h4>Step 2: Preview & Mapping</h4>
                    <div style="margin-bottom: 15px;">
                        <button id="view-full-sheet" class="btn btn-default btn-sm">View Full Sheet</button>
                    </div>
                    <p>Mapped logic overview:</p>
                    <ul>
                        <li><b>student</b>: resolved from Registration ID</li>
                        <li><b>course_offering</b>: resolved from Course Code + Batch Year + Term Name</li>
                        <li><b>exam_plan / evaluation_schema</b>: <span id="schema-display-text"></span> (applied to all rows)</li>
                        <li><b>improvement_marks/grade</b>: computed via clearance & improvement rules</li>
                    </ul>
                    <h5>Parsed Rows</h5>
                    <div id="preview-table-wrapper" style="max-height: 250px; overflow: auto; border: 1px solid #d1d8dd; margin-bottom: 10px;">
                        <span class="text-muted">Loading preview...</span>
                    </div>
                    <div>
                        <button id="preview-prev" class="btn btn-default btn-sm" disabled>Prev</button>
                        <span id="preview-page-info" style="margin: 0 10px;">Page 1</span>
                        <button id="preview-next" class="btn btn-default btn-sm" disabled>Next</button>
                    </div>
                </div>
            `);
            container.append(wrapper);
            wrapper.find('#schema-display-text').text(`${selected_exam_plan} / ${selected_eval_schema}`);

            wrapper.find('#view-full-sheet').on('click', function (e) {
                e.preventDefault();
                window.open('/app/marks-import-log-detail?import_log=' + import_log);
            });

            wrapper.find('#preview-prev').on('click', function (e) {
                e.preventDefault();
                if (preview_page > 1) load_preview_page(preview_page - 1);
            });
            wrapper.find('#preview-next').on('click', function (e) {
                e.preventDefault();
                load_preview_page(preview_page + 1);
            });

            load_preview_page(1);

        } else if (step === 3) {
            d.set_primary_action(__('Start Import'));
            d.get_secondary_btn().show().text(__('Previous'));
            d.get_close_btn().show();

            let wrapper = $(`
                <div>
                    <h4>Step 3: Validation Results</h4>
                    <div id="validation-loading" class="text-muted">
                        <i class="fa fa-spinner fa-spin"></i> Running validation rules...
                    </div>
                    <div id="validation-content" style="display: none;">
                        <div id="validation-summary"></div>
                        <div style="margin-top: 15px;" id="csv-download-buttons">
                            <button id="dl-missing-courses" class="btn btn-danger btn-sm" style="display:none;">Missing Courses</button>
                            <button id="dl-missing-offerings" class="btn btn-warning btn-sm" style="display:none;">Missing Course Offerings</button>
                            <button id="dl-missing-students" class="btn btn-danger btn-sm" style="display:none;">Missing Students</button>
                        </div>
                        <div id="missing-offerings" style="display: none; margin-top: 15px;">
                            <h5><span class="text-danger">Blocked</span>: Missing Course Offerings</h5>
                            <div id="missing-offerings-table" style="max-height: 150px; overflow: auto; border: 1px solid #d1d8dd;"></div>
                        </div>
                        <div id="validation-errors" style="display: none; margin-top: 15px;">
                            <h5>Error Details</h5>
                            <div style="margin-bottom: 10px;">
                                <select id="error-status-filter" class="form-control input-sm" style="width: 200px; display: inline-block;">
                                    <option value="">All Errors</option>
                                    <option value="Failed">Failed</option>
                                    <option value="Missing Student">Missing Student</option>
                                    <option value="Missing Course">Missing Course</option>
                                    <option value="Missing Course Offering">Missing Course Offering</option>
                                    <option value="Duplicate (Skip)">Duplicate (Skip)</option>
                                </select>
                            </div>
                            <div id="errors-table-wrapper" style="max-height: 250px; overflow: auto; border: 1px solid #d1d8dd; margin-bottom: 10px;"></div>
                            <div>
                                <button id="errors-prev" class="btn btn-default btn-sm" disabled>Prev</button>
                                <span id="errors-page-info" style="margin: 0 10px;">Page 1</span>
                                <button id="errors-next" class="btn btn-default btn-sm" disabled>Next</button>
                            </div>
                        </div>
                        <div style="margin-top: 20px;" id="proceed-checkbox-wrapper"></div>
                    </div>
                </div>
            `);
            container.append(wrapper);
            d.get_primary_btn().prop('disabled', true);

            frappe.call({
                method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.validate_staged_rows",
                args: { import_log: import_log },
                callback: function (r) {
                    wrapper.find('#validation-loading').hide();
                    wrapper.find('#validation-content').show();
                    if (r.message) render_validation_results(r.message, wrapper);
                }
            });

        } else if (step === 4) {
            d.get_primary_btn().hide();
            d.get_secondary_btn().show().text(__('Close'));

            let wrapper = $(`
                <div>
                    <h4>Step 4: Live Progress</h4>
                    <div class="progress" style="height: 20px; margin-top: 20px;">
                        <div id="import-progress-bar" class="progress-bar progress-bar-success" role="progressbar" style="width: 0%;">0%</div>
                    </div>
                    <div id="import-result-summary" style="margin-top: 20px; display: none;">
                        <h5 id="import-final-title">Import Completed</h5>
                        <p id="import-final-message"></p>
                        <button id="view-log-btn" class="btn btn-default btn-sm">View Log</button>
                        <button id="retry-failed-btn" class="btn btn-primary btn-sm" style="display:none;">Retry Failed Rows</button>
                        
                        <div id="step4-errors-section" style="display: none; margin-top: 20px;">
                            <h5>Error Details</h5>
                            <div id="step4-errors-table-wrapper" style="max-height: 250px; overflow: auto; border: 1px solid #d1d8dd; margin-bottom: 10px;"></div>
                            <div>
                                <button id="step4-errors-prev" class="btn btn-default btn-sm" disabled>Prev</button>
                                <span id="step4-errors-page-info" style="margin: 0 10px;">Page 1</span>
                                <button id="step4-errors-next" class="btn btn-default btn-sm" disabled>Next</button>
                            </div>
                        </div>
                    </div>
                </div>
            `);
            container.append(wrapper);

            if (is_importing) {
                d.get_secondary_btn().prop('disabled', true);
                d.get_close_btn().hide();
            } else {
                d.get_secondary_btn().prop('disabled', false);
                d.get_close_btn().show();
            }
        }
    }

    function handle_next() {
        if (current_step === 1) {
            let file = step_1_controls.import_file.get_value();
            let plan = step_1_controls.exam_plan.get_value();
            let eval_sch = step_1_controls.eval_schema.get_value();
            let exam_comp = step_1_controls.exam_component.get_value();
            let asst_type = step_1_controls.assessment_type.get_value();
            let re_exam_comp = step_1_controls.re_exam_component.get_value();
            let re_exam_asst_type = step_1_controls.re_exam_assessment_type.get_value();

            if (!file || !plan || !eval_sch || !exam_comp || !asst_type) {
                frappe.msgprint("Please provide the file, exam plan, evaluation schema, exam component, and assessment type.");
                return;
            }

            d.get_primary_btn().prop('disabled', true);
            let proceed = () => {
                selected_file_url = file;
                selected_exam_plan = plan;
                selected_eval_schema = eval_sch;
                selected_exam_component = exam_comp;
                selected_assessment_type = asst_type;
                selected_re_exam_component = re_exam_comp;
                selected_re_exam_assessment_type = re_exam_asst_type;

                frappe.call({
                    method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.parse_import_file",
                    args: { file_url: file, exam_plan: plan, evaluation_schema: eval_sch, exam_component: exam_comp, assessment_type: asst_type, re_exam_component: re_exam_comp, re_exam_assessment_type: re_exam_asst_type },
                    callback: function (r) {
                        d.get_primary_btn().prop('disabled', false);
                        if (r.message && r.message.import_log) {
                            import_log = r.message.import_log;
                            render_step(2);
                        }
                    },
                    error: function () {
                        d.get_primary_btn().prop('disabled', false);
                    }
                });
            };

            if (import_log && selected_file_url !== file) {
                // new file selected, delete old log
                frappe.call({
                    method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.delete_import_log",
                    args: { import_log: import_log },
                    callback: function () {
                        import_log = null;
                        proceed();
                    },
                    error: function () {
                        d.get_primary_btn().prop('disabled', false);
                    }
                });
            } else {
                proceed();
            }

        } else if (current_step === 2) {
            render_step(3);
        } else if (current_step === 3) {
            let container = $(d.fields_dict.step_container.wrapper).find('#step-render-area');
            let cb = container.find('#proceed_checkbox');
            if (cb.length > 0 && !cb.prop('checked') && !cb.prop('disabled')) {
                frappe.msgprint("You must check the confirmation box to proceed.");
                return;
            }

            d.get_primary_btn().prop('disabled', true);
            is_importing = true;
            render_step(4);

            function handle_progress_update(data) {
                if (data.import_log === import_log) {
                    let pct = data.total > 0 ? parseInt((data.progress / data.total) * 100) : 100;
                    let step_container = $(d.fields_dict.step_container.wrapper).find('#step-render-area');
                    let pbar = step_container.find('#import-progress-bar');
                    pbar.css('width', pct + '%').text(pct + '%');

                    if (data.progress >= data.total) {
                        is_importing = false;
                        d.get_secondary_btn().prop('disabled', false).text(__('Close'));
                        d.get_close_btn().show();

                        step_container.find('#import-result-summary').show();
                        step_container.find('#view-log-btn').off('click').on('click', function () {
                            window.open('/app/marks-import-log/' + import_log);
                        });

                        // Check status for retry button
                        frappe.db.get_value('Marks Import Log', import_log, 'status', function (v) {
                            if (v && (v.status === 'Completed with Errors' || v.status === 'Failed')) {
                                d.wrapper.find('.step-item[data-step="4"]').removeClass('active').addClass('failed').find('.step-circle').html('X');
                                step_container.find('#import-final-title').html('<span class="text-danger">Completed with Errors</span>');
                                step_container.find('#import-final-message').text('The import finished, but some rows failed to process.');

                                let rbtn = step_container.find('#retry-failed-btn');
                                rbtn.show().off('click').on('click', function () {
                                    d.get_secondary_btn().prop('disabled', true);
                                    frappe.call({
                                        method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.retry_failed_rows",
                                        args: { import_log: import_log },
                                        callback: function (r2) {
                                            d.get_secondary_btn().prop('disabled', false);
                                            if (!r2.exc) {
                                                is_importing = true;
                                                render_step(4);
                                            }
                                        }
                                    });
                                });

                                // Load error table
                                step_container.find('#step4-errors-section').show();
                                bind_error_pagination(step_container, '#step4-errors-prev', '#step4-errors-next', '#step4-errors-page-info', '#step4-errors-table-wrapper', 'Failed');

                            } else {
                                d.wrapper.find('.step-item[data-step="4"]').removeClass('active').addClass('completed').find('.step-circle').html('&#10003;');
                                step_container.find('#import-final-title').html('<span class="text-success">Import Completed Successfully</span>');
                                step_container.find('#import-final-message').text('All rows were imported without errors.');
                            }
                        });
                    }
                }
            }

            frappe.realtime.off("marks_import_progress");
            frappe.realtime.on("marks_import_progress", handle_progress_update);

            // Fallback polling for very fast imports that might miss the socket event
            let check_interval = setInterval(function() {
                if (!is_importing) {
                    clearInterval(check_interval);
                    return;
                }
                frappe.db.get_value('Marks Import Log', import_log, ['status', 'total_rows'], function(v) {
                    if (v && ['Completed', 'Completed with Errors', 'Failed'].includes(v.status)) {
                        clearInterval(check_interval);
                        if (is_importing) {
                            handle_progress_update({
                                import_log: import_log,
                                progress: v.total_rows || 100,
                                total: v.total_rows || 100
                            });
                        }
                    }
                });
            }, 3000);

            frappe.call({
                method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.start_bulk_import",
                args: { import_log: import_log, skip_blocked: 1 },
                callback: function (r) {
                    if (r.exc) {
                        is_importing = false;
                        d.get_primary_btn().prop('disabled', false);
                    }
                },
                error: function() {
                    is_importing = false;
                    d.get_primary_btn().prop('disabled', false);
                }
            });
        }
    }

    function load_preview_page(page) {
        frappe.call({
            method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.get_preview_page",
            args: { import_log: import_log, page: page, page_size: 50 },
            callback: function (r) {
                if (r.message) {
                    preview_page = r.message.page;
                    let container = $(d.fields_dict.step_container.wrapper).find('#step-render-area');
                    container.find('#preview-page-info').text('Page ' + preview_page);

                    let has_more = (preview_page * r.message.page_size) < r.message.total;
                    container.find('#preview-next').prop('disabled', !has_more);
                    container.find('#preview-prev').prop('disabled', preview_page <= 1);

                    render_preview_table(r.message.rows, container);
                }
            }
        });
    }

    function load_errors_page(page, filter, container, info_el, wrapper_el, prev_btn, next_btn) {
        frappe.call({
            method: "slcm.slcm.doctype.student_course_marks.marks_bulk_import.get_errors_page",
            args: { import_log: import_log, page: page, page_size: 20, status_filter: filter },
            callback: function (r) {
                if (r.message) {
                    container.find(info_el).text('Page ' + r.message.page);
                    let has_more = (r.message.page * r.message.page_size) < r.message.total;
                    container.find(next_btn).prop('disabled', !has_more).data('page', r.message.page + 1);
                    container.find(prev_btn).prop('disabled', r.message.page <= 1).data('page', r.message.page - 1);

                    if (r.message.rows.length === 0) {
                        container.find(wrapper_el).html('<div style="padding:10px;" class="text-muted">No errors found.</div>');
                    } else {
                        let html = '<table class="table table-bordered table-condensed" style="font-size: 11px;"><thead><tr><th style="width:20%;">Detail ID</th><th style="width:20%;">Status</th><th>Error Message</th></tr></thead><tbody>';
                        r.message.rows.forEach(row => {
                            html += `<tr>
                                <td><a href="/app/marks-import-log-detail/${row.name}" target="_blank">${row.name}</a></td>
                                <td>${row.status}</td>
                                <td class="text-danger">${row.error_reason || ''}</td>
                            </tr>`;
                        });
                        html += '</tbody></table>';
                        container.find(wrapper_el).html(html);
                    }
                }
            }
        });
    }

    function bind_error_pagination(container, prev_btn, next_btn, info_el, wrapper_el, default_filter) {
        let filter_val = default_filter || '';

        container.find(prev_btn).off('click').on('click', function (e) {
            e.preventDefault();
            load_errors_page($(this).data('page'), filter_val, container, info_el, wrapper_el, prev_btn, next_btn);
        });

        container.find(next_btn).off('click').on('click', function (e) {
            e.preventDefault();
            load_errors_page($(this).data('page'), filter_val, container, info_el, wrapper_el, prev_btn, next_btn);
        });

        if (container.find('#error-status-filter').length > 0) {
            container.find('#error-status-filter').off('change').on('change', function () {
                filter_val = $(this).val();
                load_errors_page(1, filter_val, container, info_el, wrapper_el, prev_btn, next_btn);
            });
        }

        load_errors_page(1, filter_val, container, info_el, wrapper_el, prev_btn, next_btn);
    }

    function render_preview_table(rows, container) {
        if (!rows || rows.length === 0) return;
        let html = '<table class="table table-bordered table-condensed" style="font-size: 11px;"><thead><tr>';
        let keys = Object.keys(rows[0].raw_data || {});
        html += '<th>Row #</th>';
        keys.forEach(k => { html += `<th>${k}</th>`; });
        html += '</tr></thead><tbody>';
        rows.forEach(r => {
            html += '<tr>';
            html += `<td>${r.row_number}</td>`;
            let raw = r.raw_data || {};
            keys.forEach(k => { html += `<td>${raw[k] !== undefined && raw[k] !== null ? raw[k] : ''}</td>`; });
            html += '</tr>';
        });
        html += '</tbody></table>';
        container.find('#preview-table-wrapper').html(html);
    }

    function render_validation_results(res, wrapper) {
        let summary = `<p>
            <span class="badge" style="background-color: #28a745;">Valid: ${res.valid_count}</span>
            <span class="badge" style="background-color: #ffc107; color: black;">Duplicates: ${res.skip_count}</span>
            <span class="badge" style="background-color: #dc3545;">Errors/Missing: ${res.error_count}</span>
            <br/><br/>
            Missing Details: Students (${res.missing_student_count}) | Courses (${res.missing_course_count}) | Offerings (${res.missing_offering_count})
        </p>`;
        wrapper.find('#validation-summary').html(summary);

        if (res.missing_course_count > 0) {
            wrapper.find('#dl-missing-courses').show().on('click', () => window.open(frappe.urllib.get_full_url('/api/method/slcm.slcm.doctype.student_course_marks.marks_bulk_import.download_missing_courses?import_log=' + import_log)));
        }
        if (res.missing_offering_count > 0) {
            wrapper.find('#dl-missing-offerings').show().on('click', () => window.open(frappe.urllib.get_full_url('/api/method/slcm.slcm.doctype.student_course_marks.marks_bulk_import.download_missing_course_offerings?import_log=' + import_log)));
        }
        if (res.missing_student_count > 0) {
            wrapper.find('#dl-missing-students').show().on('click', () => window.open(frappe.urllib.get_full_url('/api/method/slcm.slcm.doctype.student_course_marks.marks_bulk_import.download_missing_students?import_log=' + import_log)));
        }

        if (res.missing_offering_groups && res.missing_offering_groups.length > 0) {
            let mhtml = '<table class="table table-bordered table-condensed" style="font-size: 11px;"><thead><tr><th>Course Code</th><th>Batch</th><th>Term Name</th><th>Affected Rows</th></tr></thead><tbody>';
            res.missing_offering_groups.forEach(g => {
                mhtml += `<tr><td>${g.course_code}</td><td>${g.batch}</td><td>${g.term_name}</td><td>${g.affected_row_count}</td></tr>`;
            });
            mhtml += '</tbody></table>';
            wrapper.find('#missing-offerings-table').html(mhtml);
            wrapper.find('#missing-offerings').show();
        }

        if (res.error_count > 0 || res.missing_student_count > 0 || res.missing_course_count > 0 || res.missing_offering_count > 0 || res.skip_count > 0) {
            wrapper.find('#validation-errors').show();
            bind_error_pagination(wrapper, '#errors-prev', '#errors-next', '#errors-page-info', '#errors-table-wrapper', '');
        }

        let issues = res.error_count + res.missing_student_count + res.missing_course_count + res.missing_offering_count + res.skip_count;

        let cb_html = `<label><input type="checkbox" id="proceed_checkbox" ${issues === 0 ? 'checked disabled' : ''}> 
            Import ${res.valid_count} valid rows now, skip ${issues} rows with issues
        </label>`;
        wrapper.find('#proceed-checkbox-wrapper').html(cb_html);

        if (issues > 0) {
            d.get_primary_btn().prop('disabled', true);
            wrapper.find('#proceed_checkbox').on('change', function () {
                d.get_primary_btn().prop('disabled', !$(this).prop('checked'));
            });
        } else {
            d.get_primary_btn().prop('disabled', false);
        }
    }

    d.show();
    render_step(1);
    bind_stepper_clicks();
}
