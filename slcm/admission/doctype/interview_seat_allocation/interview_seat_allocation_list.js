
console.debug('Interview Seat Allocation list view script loaded');

frappe.listview_settings['Interview Seat Allocation'] = {
    refresh: function (listview) {
        // log roles so we can debug why buttons may be hidden
        const is_applicant = frappe.user_roles.includes("Applicant");
        const is_admin = frappe.user_roles.includes("Administrator") || frappe.user_roles.includes("System Manager");
        console.debug('Interview Seat Allocation refresh – roles:', frappe.user_roles,
            'is_applicant=', is_applicant, 'is_admin=', is_admin);

        // show buttons for anyone who is not a pure applicant or when the user is an admin
        if (!is_applicant || is_admin) {
            // Update Rank button (only once)
            if (!listview.page.wrapper.find('.btn-update-rank').length) {
                const ubtn = listview.page.add_inner_button(__("Update Rank"), function () {
                    let d = new frappe.ui.Dialog({
                        title: __("Update Rank"),
                        fields: [
                            {
                                label: __("Academic Year"),
                                fieldname: "academic_year",
                                fieldtype: "Link",
                                options: "Academic Year",
                                reqd: 1
                            },
                            {
                                label: __("Admission Cycle"),
                                fieldname: "admission_cycle",
                                fieldtype: "Link",
                                options: "Admission Cycle",
                                reqd: 1
                            },
                            {
                                label: __("Programme Level"),
                                fieldname: "program_level",
                                fieldtype: "Select",
                                options: "Undergraduate\nPostgraduate\nResearch Course",
                                default: "Research Course",
                                reqd: 1
                            },
                            {
                                label: __("Interview List"),
                                fieldname: "interview_list",
                                fieldtype: "Link",
                                options: "Interview List",
                                description: __("Optional - limit to this specific interview event")
                            }
                        ],
                        primary_action_label: __("Update Rank"),
                        primary_action(values) {
                            if (!values.academic_year || !values.admission_cycle || !values.program_level) {
                                frappe.msgprint(__("Academic Year, Admission Cycle and Programme Level are required."));
                                return;
                            }
                            
                            // Hide dialog immediately to show progress bar clearly
                            d.hide();

                            frappe.call({
                                method: "slcm.admission.doctype.interview_seat_allocation.interview_seat_allocation.update_ranks_by_category",
                                args: values,
                                callback: function (r) {
                                    if (r.message !== undefined) {
                                        // Show toast at the top center
                                        frappe.msgprint({
                                            message: __("Ranks updated and emails sent successfully for {0} applicants.", [r.message]),
                                            indicator: 'green',
                                            alert: true
                                        });
                                    }
                                    listview.refresh();
                                }
                            });
                        }
                    });
                    d.set_query("admission_cycle", function () {
                        return {
                            filters: {
                                "status": "Active"
                            }
                        };
                    });
                    d.show();
                });
                ubtn.addClass('btn-update-rank');
            }

            // Reschedule button (also only once)
            if (!listview.page.wrapper.find('.btn-reschedule').length) {
                const rbtn = listview.page.add_button(__('Reschedule'), function () {
                    try {
                        open_reschedule_dialog(listview);
                    } catch (e) {
                        console.error('Reschedule dialog error', e);
                        frappe.msgprint({ title: __('Error'), message: __('Unable to open Reschedule dialog. See browser console for details.'), indicator: 'red' });
                    }
                }, 'btn-primary');
                rbtn.addClass('btn-reschedule');
            }

            // Generate Offer Letters button (only once)
            if (!listview.page.wrapper.find('.btn-generate-offers').length) {
                const obtn = listview.page.add_button(__('Generate Offer Letters'), function () {
                    try {
                        open_generate_offer_dialog(listview);
                    } catch (e) {
                        console.error('Generate Offer dialog error', e);
                        frappe.msgprint({ title: __('Error'), message: __('Unable to open Generate Offer dialog.'), indicator: 'red' });
                    }
                }, 'btn-primary');
                obtn.addClass('btn-generate-offers');
            }
        }
    }
};


// -----------------------------------------------------------------------------
//  Interview rescheduling dialog
// -----------------------------------------------------------------------------
function open_reschedule_dialog(listview) {
    console.debug('Opening reschedule dialog');
    let d = new frappe.ui.Dialog({
        title: __('Reschedule Interview'),
        size: 'extra-large',
        fields: [
            { fieldtype: 'Section Break', label: __('Filters') },
            {
                label: __('Program Level'),
                fieldname: 'program_level',
                fieldtype: 'Select',
                options: 'Undergraduate\nPostgraduate\nResearch Course',
                on_change: () => fetch_absent_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Academic Year'),
                fieldname: 'academic_year',
                fieldtype: 'Link',
                options: 'Academic Year',
                on_change: () => fetch_absent_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Campus'),
                fieldname: 'campus',
                fieldtype: 'Link',
                options: 'Campus',
                on_change: () => fetch_absent_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Admission Cycle'),
                fieldname: 'admission_cycle',
                fieldtype: 'Link',
                options: 'Admission Cycle',
                on_change: () => fetch_absent_applicants(d)
            },

            { fieldtype: 'Section Break', label: __('Reschedule Settings') },
            {
                label: __('New Interview Date'),
                fieldname: 'interview_date',
                fieldtype: 'Datetime',
                reqd: 1,
                description: __('Must be today or a future date/time')
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Interview Staff Member'),
                fieldname: 'interview_staff_member',
                fieldtype: 'Link',
                options: 'Interview Staff Member',
                reqd: 1
            },
            { fieldtype: 'Section Break' },
            {
                label: __('Reason for Reschedule'),
                fieldname: 'reschedule_reason',
                fieldtype: 'Small Text',
                reqd: 1,
                description: __('This reason will be included in the email sent to applicants')
            },

            { fieldtype: 'Section Break', label: __('Select Absent Applicants') },
            {
                fieldtype: 'HTML',
                fieldname: 'applicants_html'
            }
        ],
        primary_action_label: __('Reschedule'),
        primary_action(values) {
            const selected_applicants = [];
            d.$wrapper.find('.applicant-checkbox:checked').each(function () {
                selected_applicants.push($(this).data('name'));
            });

            if (!selected_applicants.length) {
                frappe.msgprint({ message: __('Please select at least one applicant.'), indicator: 'orange' });
                return;
            }

            frappe.call({
                method: 'slcm.admission.doctype.interview_seat_allocation.interview_seat_allocation.reschedule_applicants',
                args: {
                    applicants: selected_applicants,
                    interview_staff: values.interview_staff_member,
                    interview_date: values.interview_date,
                    interview_time: values.interview_date ? frappe.datetime.get_time(values.interview_date) : null,
                    reschedule_reason: values.reschedule_reason
                },
                freeze: true,
                freeze_message: __('Rescheduling Applicants...'),
                callback: function (r) {
                    if (r.message !== undefined) {
                        frappe.msgprint(__('{0} record(s) updated.', [r.message]));
                    }
                    d.hide();
                    listview.refresh();
                }
            });
        }
    });

    d.show();
    d.set_query("admission_cycle", function () {
        return {
            filters: {
                "status": "Active"
            }
        };
    });
    fetch_absent_applicants(d);
}

function fetch_absent_applicants(d) {
    const filters = { interview_status: 'Absent', is_rescheduled: 0 };

    if (d.get_value('program_level')) filters.program_level = d.get_value('program_level');
    if (d.get_value('academic_year')) filters.academic_year = d.get_value('academic_year');
    if (d.get_value('campus')) filters.campus = d.get_value('campus');
    if (d.get_value('admission_cycle')) filters.admission_cycle = d.get_value('admission_cycle');

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Interview Seat Allocation',
            filters: filters,
            fields: ['name', 'candidate_name', 'applicant', 'program'],
            limit_page_length: 50
        },
        callback: function (r) {
            const applicants = r.message || [];
            let html = `
                <div style="margin-bottom:10px; display:flex; gap:12px; align-items:center;">
                    <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center;">
                        <input type="checkbox" id="select-all-applicants">
                        <span style="margin-left:8px;">Select All</span>
                    </label>
                    <span id="selected-count" style="color:#6c757d; font-size:12px;">0 of ${applicants.length} selected</span>
                </div>
                <div style="max-height:250px; overflow-y:auto; border:1px solid #d1d8dd; border-radius:4px;">
                    <table class="table table-bordered table-hover" style="margin:0; font-size:13px;">
                        <thead style="position:sticky; top:0; background:#f4f5f6; z-index:1;">
                            <tr>
                                <th style="width:40px;"></th>
                                <th>Candidate Name</th>
                                <th>Applicant ID</th>
                                <th>Program</th>
                            </tr>
                        </thead>
                        <tbody>`;

            if (applicants.length) {
                applicants.forEach(app => {
                    html += `
                        <tr>
                            <td><input type="checkbox" class="applicant-checkbox" data-name="${app.name}"></td>
                            <td>${app.candidate_name || ''}</td>
                            <td>${app.applicant || ''}</td>
                            <td>${app.program || ''}</td>
                        </tr>`;
                });
            } else {
                html += `<tr><td colspan="5" class="text-muted">No applicants found.</td></tr>`;
            }

            html += '</tbody></table></div>';
            d.get_field('applicants_html').$wrapper.html(html);

            // Select All
            d.$wrapper.find('#select-all-applicants').on('change', function () {
                d.$wrapper.find('.applicant-checkbox').prop('checked', $(this).is(':checked'));
                update_selected_count(d, applicants.length);
            });

            // Individual
            d.$wrapper.on('change', '.applicant-checkbox', function () {
                update_selected_count(d, applicants.length);
            });

            update_selected_count(d, applicants.length);
        }
    });
}

function update_selected_count(d, total) {
    const n = d.$wrapper.find('.applicant-checkbox:checked').length;
    const t = total !== undefined ? total : d.$wrapper.find('.applicant-checkbox').length;
    d.$wrapper.find('#selected-count').text(`${n} of ${t} selected`);
    d.$wrapper.find('#select-all-applicants').prop('checked', t > 0 && n === t);
}

// -----------------------------------------------------------------------------
//  Generate Offer Letters dialog
// -----------------------------------------------------------------------------
function open_generate_offer_dialog(listview) {
    let d = new frappe.ui.Dialog({
        title: __('Generate Offer Letters'),
        size: 'extra-large',
        fields: [
            { fieldtype: 'Section Break', label: __('Filters') },
            {
                label: __('Program Level'),
                fieldname: 'program_level',
                fieldtype: 'Select',
                options: 'Undergraduate\nPostgraduate\nResearch Course',
                on_change: () => fetch_pass_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Academic Year'),
                fieldname: 'academic_year',
                fieldtype: 'Link',
                options: 'Academic Year',
                on_change: () => fetch_pass_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Campus'),
                fieldname: 'campus',
                fieldtype: 'Link',
                options: 'Campus',
                on_change: () => fetch_pass_applicants(d)
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Admission Cycle'),
                fieldname: 'admission_cycle',
                fieldtype: 'Link',
                options: 'Admission Cycle',
                on_change: () => fetch_pass_applicants(d)
            },

            { fieldtype: 'Section Break', label: __('Select Passed Applicants') },
            {
                fieldtype: 'HTML',
                fieldname: 'applicants_html'
            }
        ],
        primary_action_label: __('Generate Offer Letters'),
        primary_action(values) {
            const selected_applicants = [];
            d.$wrapper.find('.applicant-checkbox:checked').each(function () {
                selected_applicants.push($(this).data('applicant'));
            });

            if (!selected_applicants.length) {
                frappe.msgprint({ message: __('Please select at least one applicant.'), indicator: 'orange' });
                return;
            }

            frappe.call({
                method: 'slcm.api.service.offer_service.OfferService.bulk_generate_offers',
                args: {
                    applicants: selected_applicants
                },
                freeze: true,
                freeze_message: __('Generating Offer Letters...'),
                callback: function (r) {
                    if (r.message) {
                        if (r.message.queued) {
                            frappe.msgprint({
                                message: r.message.message,
                                indicator: 'blue'
                            });
                        } else {
                            let s_count = r.message.success ? r.message.success.length : 0;
                            let e_count = r.message.errors ? r.message.errors.length : 0;
                            
                            let message = `
                                <div style="padding: 10px;">
                                    <div style="display: flex; gap: 15px; margin-bottom: 20px;">
                                        <div style="flex: 1; padding: 12px; background: #f0fff4; border: 1px solid #c6f6d5; border-radius: 8px; text-align: center;">
                                            <h3 style="margin: 0; color: #2f855a;">${s_count}</h3>
                                            <div style="font-size: 11px; color: #38a169; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Successful')}</div>
                                        </div>
                                        <div style="flex: 1; padding: 12px; background: ${e_count > 0 ? '#fff5f5' : '#f7fafc'}; border: 1px solid ${e_count > 0 ? '#fed7d7' : '#edf2f7'}; border-radius: 8px; text-align: center;">
                                            <h3 style="margin: 0; color: ${e_count > 0 ? '#c53030' : '#718096'};">${e_count}</h3>
                                            <div style="font-size: 11px; color: ${e_count > 0 ? '#e53e3e' : '#a0aec0'}; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">${__('Failed')}</div>
                                        </div>
                                    </div>
                            `;

                            if (e_count > 0) {
                                message += `
                                    <div style="margin-bottom: 8px; font-weight: 600; color: #4a5568;">${__('Generation Failures:')}</div>
                                    <div style="max-height: 250px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px;">
                                        <table class="table table-bordered table-condensed" style="margin:0; font-size: 12px; background: #fff;">
                                            <thead style="background: #f8fafc;">
                                                <tr>
                                                    <th style="width: 35%;">${__('Applicant')}</th>
                                                    <th>${__('Reason for Failure')}</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${r.message.errors.map(item => `
                                                    <tr>
                                                        <td style="font-weight: 600;">${item.applicant || item.name}</td>
                                                        <td style="color: #e53e3e; word-break: break-word;">${item.error}</td>
                                                    </tr>
                                                `).join('')}
                                            </tbody>
                                        </table>
                                    </div>
                                `;
                            }
                            message += `</div>`;

                            frappe.msgprint({
                                title: __('Offer Generation Report'),
                                message: message,
                                wide: true,
                                indicator: e_count === 0 ? 'green' : (s_count > 0 ? 'orange' : 'red'),
                                primary_action: {
                                    label: __('View Offer Letters'),
                                    action: () => frappe.set_route('List', 'Offer Letter')
                                }
                            });
                        }
                    }
                    d.hide();
                    listview.refresh();
                }
            });
        }
    });

    d.show();
    d.set_query("admission_cycle", function () {
        return {
            filters: {
                "status": "Active"
            }
        };
    });
    fetch_pass_applicants(d);
}

function fetch_pass_applicants(d) {
    const filters = { interview_result_status: 'Pass' };

    if (d.get_value('program_level')) filters.program_level = d.get_value('program_level');
    if (d.get_value('academic_year')) filters.academic_year = d.get_value('academic_year');
    if (d.get_value('campus')) filters.campus = d.get_value('campus');
    if (d.get_value('admission_cycle')) filters.admission_cycle = d.get_value('admission_cycle');

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Interview Seat Allocation',
            filters: filters,
            fields: ['name', 'candidate_name', 'applicant', 'program', 'interview_result_status'],
            limit_page_length: 100
        },
        callback: function (r) {
            const applicants = r.message || [];
            let html = `
                <div style="margin-bottom:10px; display:flex; gap:12px; align-items:center;">
                    <label style="font-weight:600; cursor:pointer; margin:0; display:flex; align-items:center;">
                        <input type="checkbox" id="select-all-offer-applicants">
                        <span style="margin-left:8px;">Select All</span>
                    </label>
                    <span id="selected-offer-count" style="color:#6c757d; font-size:12px;">0 of ${applicants.length} selected</span>
                </div>
                <div style="max-height:250px; overflow-y:auto; border:1px solid #d1d8dd; border-radius:4px;">
                    <table class="table table-bordered table-hover" style="margin:0; font-size:13px;">
                        <thead style="position:sticky; top:0; background:#f4f5f6; z-index:1;">
                            <tr>
                                <th style="width:40px;"></th>
                                <th>Candidate Name</th>
                                <th>Applicant ID</th>
                                <th>Program</th>
                                <th>Result</th>
                            </tr>
                        </thead>
                        <tbody>`;

            if (applicants.length) {
                applicants.forEach(app => {
                    html += `
                        <tr>
                            <td><input type="checkbox" class="applicant-checkbox" data-applicant="${app.applicant}" data-name="${app.name}"></td>
                            <td>${app.candidate_name || ''}</td>
                            <td>${app.applicant || ''}</td>
                            <td>${app.program || ''}</td>
                            <td><span class="badge badge-success">${app.interview_result_status}</span></td>
                        </tr>`;
                });
            } else {
                html += `<tr><td colspan="5" class="text-muted">No eligible applicants found.</td></tr>`;
            }

            html += '</tbody></table></div>';
            d.get_field('applicants_html').$wrapper.html(html);

            // Select All
            d.$wrapper.find('#select-all-offer-applicants').on('change', function () {
                d.$wrapper.find('.applicant-checkbox').prop('checked', $(this).is(':checked'));
                update_offer_selected_count(d, applicants.length);
            });

            // Individual
            d.$wrapper.on('change', '.applicant-checkbox', function () {
                update_offer_selected_count(d, applicants.length);
            });

            update_offer_selected_count(d, applicants.length);
        }
    });
}

function update_offer_selected_count(d, total) {
    const n = d.$wrapper.find('.applicant-checkbox:checked').length;
    const t = total !== undefined ? total : d.$wrapper.find('.applicant-checkbox').length;
    d.$wrapper.find('#selected-offer-count').text(`${n} of ${t} selected`);
    d.$wrapper.find('#select-all-offer-applicants').prop('checked', t > 0 && n === t);
}
