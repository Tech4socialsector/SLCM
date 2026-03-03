// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Examination Plan", {
    refresh(frm) {
        if (!frm.is_new()) {
            render_dashboard(frm);
        }
    },
});

function render_dashboard(frm) {
    let html = `
		<div style="display: flex; gap: 15px; margin-bottom: 20px; padding: 10px; background-color: #f7f7f7; border-radius: 4px; justify-content: center;">
			<div class="exam-dashboard-btn" id="btn-master-data" style="cursor: pointer; padding: 20px; border: 1px solid #d1d8dd; border-radius: 8px; text-align: center; background-color: white; width: 120px;">
				<div style="font-size: 24px; color: #5e64ff; margin-bottom: 10px;">
					<i class="fa fa-database"></i>
				</div>
				<div style="font-size: 11px; font-weight: bold; color: #36414c;">Master Data</div>
			</div>
			
			<div class="exam-dashboard-btn" id="btn-exam" style="cursor: pointer; padding: 20px; border: 1px solid #d1d8dd; border-radius: 8px; text-align: center; background-color: white; width: 120px;">
				<div style="font-size: 24px; color: #5e64ff; margin-bottom: 10px;">
					<i class="fa fa-file-text-o"></i>
				</div>
				<div style="font-size: 11px; font-weight: bold; color: #36414c;">Exam</div>
			</div>
			
			<div class="exam-dashboard-btn" id="btn-exam-enrollment" style="cursor: pointer; padding: 20px; border: 1px solid #d1d8dd; border-radius: 8px; text-align: center; background-color: white; width: 120px;">
				<div style="font-size: 24px; color: #5e64ff; margin-bottom: 10px;">
					<i class="fa fa-user-plus"></i>
				</div>
				<div style="font-size: 11px; font-weight: bold; color: #36414c;">Exam Enrollment</div>
			</div>
			
			<div class="exam-dashboard-btn" id="btn-results" style="cursor: pointer; padding: 20px; border: 1px solid #d1d8dd; border-radius: 8px; text-align: center; background-color: white; width: 120px;">
				<div style="font-size: 24px; color: #5e64ff; margin-bottom: 10px;">
					<i class="fa fa-file-excel-o"></i>
				</div>
				<div style="font-size: 11px; font-weight: bold; color: #36414c;">Results</div>
			</div>
			
			<div class="exam-dashboard-btn" id="btn-reports" style="cursor: pointer; padding: 20px; border: 1px solid #d1d8dd; border-radius: 8px; text-align: center; background-color: white; width: 120px;">
				<div style="font-size: 24px; color: #5e64ff; margin-bottom: 10px;">
					<i class="fa fa-line-chart"></i>
				</div>
				<div style="font-size: 11px; font-weight: bold; color: #36414c;">Reports & Analytics</div>
			</div>
		</div>
	`;

    if (frm.fields_dict.dashboard_html) {
        frm.fields_dict.dashboard_html.$wrapper.html(html);

        frm.fields_dict.dashboard_html.$wrapper.find('.exam-dashboard-btn').css('transition', 'box-shadow 0.2s')
        frm.fields_dict.dashboard_html.$wrapper.find('.exam-dashboard-btn').hover(
            function () { $(this).css('box-shadow', '0 0 10px rgba(0,0,0,0.1)'); },
            function () { $(this).css('box-shadow', 'none'); }
        );

        frm.fields_dict.dashboard_html.$wrapper.find('#btn-master-data').on('click', function () {
            show_master_data_dialog(frm);
        });
    }
}

function show_master_data_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Master Data'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'master_html'
            }
        ]
    });

    dialog.$wrapper.find('.modal-dialog').css('min-width', '80%');

    let render_master_data = function () {
        frappe.call({
            method: 'slcm.slcm.doctype.examination_plan.examination_plan.get_exam_courses',
            args: {
                exam_plan_name: frm.doc.name
            },
            callback: function (r) {
                let html = `
					<div class="master-data-container" style="padding: 5px;">
						
						<!-- Tabs -->
						<ul class="nav nav-tabs" style="margin-bottom: 15px; border-bottom: 2px solid #ddd;">
							<li class="nav-item">
								<a class="nav-link active" id="tab-courses" data-toggle="tab" href="#content-courses" style="font-weight: bold; color: #ff5252; border-bottom: 2px solid #ff5252; border-top: none; border-left: none; border-right: none; background: transparent;">Courses</a>
							</li>
							<li class="nav-item">
								<a class="nav-link" id="tab-students" data-toggle="tab" href="#content-students" style="font-weight: bold; color: #555; border: none; background: transparent;">Students</a>
							</li>
						</ul>

						<div class="tab-content mt-3">
							<!-- Courses Tab Content -->
							<div class="tab-pane fade show active" id="content-courses">
								<div class="row align-items-center mb-3">
									<div class="col-sm-4">
										<input type="text" class="form-control" id="search-course" placeholder="Search by Course Name or Course Code">
									</div>
									<div class="col-sm-8 text-right">
										<button class="btn btn-default btn-sm text-danger border-danger" id="btn-apply-schema" style="border-radius: 20px;">Apply Schema</button>
										<button class="btn btn-default btn-sm ml-2" id="btn-unmap-schema" style="border-radius: 20px;">Unmap Schema</button>
									</div>
								</div>
								
								<div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
									<table class="table table-bordered table-hover">
										<thead style="background-color: #f3f3f3; position: sticky; top: 0; z-index: 1;">
											<tr style="font-size: 12px; color: #6c757d;">
												<th style="width: 40px;"><input type="checkbox" id="check-all-courses"></th>
												<th>Course Name</th>
												<th>All Type</th>
												<th>Credits</th>
												<th>Department</th>
												<th>Enrolled Students</th>
												<th>Exam Schema</th>
											</tr>
										</thead>
										<tbody id="courses-table-body" style="font-size: 13px;">
				`;

                if (r.message) {
                    window.exam_plan_courses = r.message;
                    r.message.forEach(row => {
                        html += `
							<tr class="course-row" data-name="${row.name}" style="cursor: pointer;">
								<td onclick="event.stopPropagation();"><input type="checkbox" class="course-check" data-name="${row.name}"></td>
								<td>
									<div><i class="fa fa-check-square-o text-success mr-1"></i> ${row.course_name}</div>
									<div class="text-muted" style="font-size: 11px;">(${row.course_code})</div>
								</td>
								<td>${row.course_type || '-'}</td>
								<td>${row.credit_value || '-'}</td>
								<td>${row.department_name || '-'}</td>
								<td>${row.enrolled_students || 0}</td>
								<td class="exam-schema-cell">${row.exam_schema || '-'}</td>
							</tr>
						`;
                    });
                }

                html += `
										</tbody>
									</table>
								</div>
							</div>

							<!-- Students Tab Content -->
							<div class="tab-pane fade" id="content-students">
								<div id="students-loading" style="display: none; padding: 20px; text-align: center;" class="text-muted">
									<i class="fa fa-spinner fa-spin"></i> Loading students...
								</div>
								<div id="students-empty" style="padding: 20px; text-align: center;" class="text-muted">
									Please click on a Course row in the Courses tab to view registered students.
								</div>
								<div id="students-content" style="display: none;">
									<div class="mb-3">
										<strong id="selected-course-title" class="text-primary"></strong>
									</div>
									<div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
										<table class="table table-bordered table-hover">
											<thead style="background-color: #f3f3f3; position: sticky; top: 0; z-index: 1;">
												<tr style="font-size: 12px; color: #6c757d;">
													<th>Student ID</th>
													<th>Student Name</th>
													<th>Status</th>
												</tr>
											</thead>
											<tbody id="students-table-body" style="font-size: 13px;">
											</tbody>
										</table>
									</div>
								</div>
							</div>
						</div>
					</div>
				`;

                dialog.fields_dict.master_html.$wrapper.html(html);

                // Tab Switching Logic
                dialog.fields_dict.master_html.$wrapper.find('.nav-link').on('click', function (e) {
                    e.preventDefault();
                    let target = $(this).attr('href');

                    dialog.fields_dict.master_html.$wrapper.find('.nav-link').css({
                        'color': '#555',
                        'border-bottom': 'none',
                        'font-weight': 'normal'
                    });
                    $(this).css({
                        'color': '#ff5252',
                        'border-bottom': '2px solid #ff5252',
                        'font-weight': 'bold'
                    });

                    dialog.fields_dict.master_html.$wrapper.find('.tab-pane').removeClass('show active');
                    dialog.fields_dict.master_html.$wrapper.find(target).addClass('show active');
                });

                // Course Row Click -> Load Students
                dialog.fields_dict.master_html.$wrapper.find('.course-row').on('click', function () {
                    let course_name = $(this).data('name');
                    let course_title = $(this).find('td:nth-child(2) div:first').text().trim();

                    // Switch to students tab visually
                    dialog.fields_dict.master_html.$wrapper.find('#tab-students').trigger('click');

                    dialog.fields_dict.master_html.$wrapper.find('#students-empty').hide();
                    dialog.fields_dict.master_html.$wrapper.find('#students-content').hide();
                    dialog.fields_dict.master_html.$wrapper.find('#students-loading').show();

                    dialog.fields_dict.master_html.$wrapper.find('#selected-course-title').text('Students enrolled for: ' + course_title);

                    frappe.call({
                        method: 'slcm.slcm.doctype.examination_plan.examination_plan.get_course_students',
                        args: {
                            exam_plan_name: frm.doc.name,
                            course_name: course_name
                        },
                        callback: function (r2) {
                            dialog.fields_dict.master_html.$wrapper.find('#students-loading').hide();
                            dialog.fields_dict.master_html.$wrapper.find('#students-content').show();

                            let st_html = '';
                            if (r2.message && r2.message.length > 0) {
                                r2.message.forEach(st => {
                                    st_html += `
										<tr>
											<td>${st.student}</td>
											<td>${st.student_name}</td>
											<td><span class="badge badge-success">${st.status || 'Active'}</span></td>
										</tr>
									`;
                                });
                            } else {
                                st_html = '<tr><td colspan="3" class="text-center text-muted">No students found for this course in the selected term.</td></tr>';
                            }
                            dialog.fields_dict.master_html.$wrapper.find('#students-table-body').html(st_html);
                        }
                    });
                });

                dialog.fields_dict.master_html.$wrapper.find('#search-course').on('keyup', function () {
                    let value = $(this).val().toLowerCase();
                    dialog.fields_dict.master_html.$wrapper.find("#courses-table-body tr").filter(function () {
                        $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1)
                    });
                });

                dialog.fields_dict.master_html.$wrapper.find('#check-all-courses').on('change', function () {
                    dialog.fields_dict.master_html.$wrapper.find('.course-check').prop('checked', $(this).prop('checked'));
                });

                dialog.fields_dict.master_html.$wrapper.find('#btn-unmap-schema').on('click', function () {
                    let selected = [];
                    dialog.fields_dict.master_html.$wrapper.find('.course-check:checked').each(function () {
                        selected.push($(this).data('name'));
                    });

                    if (selected.length === 0) {
                        frappe.msgprint("Please select at least one course.");
                        return;
                    }

                    frappe.call({
                        method: 'slcm.slcm.doctype.examination_plan.examination_plan.unmap_schema_from_courses',
                        args: {
                            exam_plan: frm.doc.name,
                            courses: selected
                        },
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.show_alert("Schema Unmapped successfully.");
                                render_master_data();
                            }
                        }
                    });
                });

                dialog.fields_dict.master_html.$wrapper.find('#btn-apply-schema').on('click', function () {
                    let selected = [];
                    dialog.fields_dict.master_html.$wrapper.find('.course-check:checked').each(function () {
                        selected.push($(this).data('name'));
                    });

                    if (selected.length === 0) {
                        frappe.msgprint("Please select at least one course.");
                        return;
                    }

                    show_apply_schema_dialog(frm, selected, render_master_data);
                });
            }
        });
    };

    render_master_data();
    dialog.show();
}

function show_apply_schema_dialog(frm, selected_courses, parent_refresh_callback) {
    let apply_dialog = new frappe.ui.Dialog({
        title: __('Apply Schema'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'info_html',
                options: `< div style = "margin-bottom: 15px;" > Selected Courses: <b>${selected_courses.length}</b></div > `
            },
            {
                fieldtype: 'Link',
                fieldname: 'schema',
                label: __('Select Schema'),
                options: 'Exam Schema',
                reqd: 1
            },
            {
                fieldtype: 'HTML',
                fieldname: 'create_new_html',
                options: `< div class="text-right" style = "margin-top: -30px; margin-bottom: 20px;" > <a href="#" id="create-new-schema" class="text-danger border-danger" style="border: 1px solid; padding: 5px 10px; border-radius: 4px; text-decoration: none;">+ Create New Schema</a></div > `
            },
            {
                fieldtype: 'HTML',
                fieldname: 'warning_html',
                options: `< div class="text-muted" style = "font-size: 11px; margin-top: 10px;" > <i class="fa fa-info-circle"></i> Updating schema for this course will erase marks for all the assessments.Class Work Assessment(Faculty Grade Book) marks will remain unaffected.</div > `
            }
        ],
        primary_action_label: __('Apply'),
        primary_action: function (values) {
            if (!values.schema) {
                frappe.msgprint("Please select a schema.");
                return;
            }

            frappe.call({
                method: 'slcm.slcm.doctype.examination_plan.examination_plan.apply_schema_to_courses',
                args: {
                    exam_plan: frm.doc.name,
                    schema_name: values.schema,
                    courses: selected_courses
                },
                callback: function (r) {
                    if (!r.exc) {
                        frappe.show_alert("Schema applied successfully.");
                        apply_dialog.hide();
                        if (parent_refresh_callback) {
                            parent_refresh_callback();
                        }
                    }
                }
            });
        }
    });

    apply_dialog.$wrapper.find('#create-new-schema').on('click', function (e) {
        e.preventDefault();
        frappe.new_doc('Exam Schema');
    });

    apply_dialog.show();
}
