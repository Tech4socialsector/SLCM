frappe.listview_settings['Examination Plan'] = {
    onload: function (listview) {
        listview.page.add_inner_button(__('Settings'), function () {
            show_exam_settings_dialog(listview);
        });
    }
};

function show_exam_settings_dialog(listview) {
    let dialog = new frappe.ui.Dialog({
        title: __('Settings'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'settings_html'
            }
        ],
        primary_action_label: __('Save'),
        primary_action: function () {
            let updates = [];
            dialog.$wrapper.find('.exam-type-row').each(function () {
                let row = $(this);
                updates.push({
                    name: row.data('name'),
                    belongs_in_re_exam_component: row.find('.re-exam-check').prop('checked') ? 1 : 0
                });
            });

            frappe.call({
                method: 'slcm.slcm.doctype.examination_plan.examination_plan.update_exam_types',
                args: {
                    updates: updates
                },
                freeze: true,
                freeze_message: __('Saving settings...'),
                callback: function (r) {
                    if (!r.exc) {
                        frappe.show_alert({ message: __('Settings Saved'), indicator: 'green' });
                        dialog.hide();
                    }
                }
            });
        }
    });

    dialog.$wrapper.find('.modal-dialog').css('min-width', '600px');

    let render_html = function () {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Exam Type',
                fields: ['name', 'exam_type', 'belongs_in_re_exam_component'],
                limit_page_length: 0
            },
            callback: function (r) {
                let html = `
					<div class="exam-settings-container" style="padding: 10px;">
						<div class="text-muted" style="background-color: #e2e2e2; padding: 10px; margin-bottom: 15px; font-weight: bold;">
							Manage Exam Types
						</div>
						<div class="text-right mb-3" style="margin-bottom: 15px;">
							<button class="btn btn-default btn-sm" id="add-new-exam-type" style="color: red; border: 1px solid red; background-color: white;">Add New Exam Type</button>
						</div>
						<div style="max-height: 300px; overflow-y: auto;">
							<table class="table table-bordered">
								<thead style="background-color: #f9f9f9; position: sticky; top: 0; z-index: 1;">
									<tr>
										<th class="text-center">Exam Type</th>
										<th class="text-center">Belongs In Re Exam Component</th>
									</tr>
								</thead>
								<tbody id="exam-type-table-body">
				`;
                if (r.message) {
                    r.message.forEach(row => {
                        let checked = row.belongs_in_re_exam_component ? 'checked' : '';
                        html += `
							<tr class="exam-type-row" data-name="${row.name}">
								<td class="text-center">${row.exam_type}</td>
								<td class="text-center"><input type="checkbox" class="re-exam-check" ${checked}></td>
							</tr>
						`;
                    });
                }
                html += `
								</tbody>
							</table>
						</div>
						<div class="text-muted" style="margin-top: 15px; font-size: 13px;">
							The ones which are selected (tick) are meant to be for re-exam, supplementary.<br>
							The unchecked ones are for normal exams.<br>
							After creating the exam type, click on the "save" button.
						</div>
					</div>
				`;

                dialog.fields_dict.settings_html.$wrapper.html(html);

                dialog.fields_dict.settings_html.$wrapper.find('#add-new-exam-type').on('click', function () {
                    dialog.hide();
                    frappe.new_doc('Exam Type');
                });

            }
        });
    };

    render_html();
    dialog.show();
}
