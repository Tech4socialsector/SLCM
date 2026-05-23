frappe.listview_settings['Venue Booking'] = {
    add_fields: ['swap_requested', 'swap_status'],

    onload: function (listview) {
        const canManage = frappe.user.has_role(['System Manager', 'Administrator', 'slcm_Registrar']);
        if (!canManage) return;

        function openUpdateDialog() {
            const selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__('Please select at least one booking to update.'));
                return;
            }
            const names = selected.map(r => r.name);
            const d = new frappe.ui.Dialog({
                title: __('Update Status — {0} booking(s)', [names.length]),
                fields: [
                    {
                        label: __('New Status'),
                        fieldname: 'status',
                        fieldtype: 'Select',
                        options: 'Approved\nRejected\nCancelled',
                        reqd: 1
                    },
                    {
                        label: __('Remarks'),
                        fieldname: 'admin_remarks',
                        fieldtype: 'Small Text'
                    }
                ],
                primary_action_label: __('Update'),
                primary_action: function (vals) {
                    frappe.call({
                        method: 'slcm.api.student_portal.bulk_update_venue_booking_status',
                        args: {
                            booking_names: names,
                            status: vals.status,
                            admin_remarks: vals.admin_remarks || ''
                        },
                        freeze: true,
                        freeze_message: __('Updating status…'),
                        callback: function (r) {
                            if (!r.exc) {
                                const res = r.message || {};
                                frappe.show_alert({
                                    message: __('{0} booking(s) updated to {1}', [res.updated || names.length, vals.status]),
                                    indicator: vals.status === 'Approved' ? 'green' : vals.status === 'Rejected' ? 'red' : 'orange'
                                });
                                d.hide();
                                listview.refresh();
                            }
                        }
                    });
                }
            });
            d.show();
        }

        // Inject directly into page_actions toolbar (before Actions button) — never cleared
        const $updateBtn = $(`
            <button class="btn btn-primary btn-sm vb-update-status-btn"
                style="margin-right:8px; white-space:nowrap; height:30px; padding:0 12px; font-size:12px; font-weight:600;">
                ✎ ${__('Update Status')}
            </button>
        `);
        $updateBtn.on('click', openUpdateDialog);

        // Wait for DOM to be ready then inject before the Actions button
        setTimeout(function () {
            if (!listview.page.wrapper.find('.vb-update-status-btn').length) {
                listview.page.actions_btn_group.before($updateBtn);
            }
        }, 300);
    },

    formatters: {
        swap_status: function (value, df, doc) {
            if (!value) return '';
            const cfg = {
                'Pending':  { bg: '#fef3c7', color: '#92400e', icon: '⇄' },
                'Approved': { bg: '#d1fae5', color: '#065f46', icon: '✓' },
                'Rejected': { bg: '#fee2e2', color: '#991b1b', icon: '✗' }
            };
            const s = cfg[value] || { bg: '#f3f4f6', color: '#374151', icon: '' };
            return `<span style="
                background:${s.bg};color:${s.color};
                padding:2px 8px;border-radius:10px;
                font-size:11px;font-weight:600;white-space:nowrap;">
                ${s.icon} ${value}
            </span>`;
        }
    },
    get_indicator: function (doc) {
        if (doc.swap_requested && doc.swap_status === 'Pending') {
            return [__('Swap Pending'), 'orange', 'swap_status,=,Pending'];
        }
    }
};

frappe.ui.form.on('Venue Booking', {
    onload: function (frm) {
        if (frm.is_new()) {
            _auto_fill_requester(frm);
        }
    },

    refresh: function (frm) {
        _toggle_student_field(frm);

        const canManage = frappe.user.has_role([
            'System Manager', 'Administrator', 'slcm_Registrar'
        ]);

        if (!frm.is_new() && canManage) {

            // ── Swap Request banner + actions ──────────────────────────
            if (frm.doc.swap_requested && frm.doc.swap_status === 'Pending') {
                const reqRoom = frm.doc.swap_requested_room || '—';
                const reqReason = frm.doc.swap_request_reason
                    ? `<br><span style="color:#555;font-size:12px;">Reason: ${frm.doc.swap_request_reason}</span>`
                    : '';
                frm.dashboard.add_comment(
                    `<span style="color:#92400e;">&#x21C4; Swap Request Pending</span> — wants to move to <strong>${reqRoom}</strong>${reqReason}`,
                    'yellow', true
                );

                frm.add_custom_button(__('Approve Swap'), function () {
                    frappe.prompt([{
                        label: __('Admin Remarks (optional)'),
                        fieldname: 'admin_remarks',
                        fieldtype: 'Small Text'
                    }], function (vals) {
                        frappe.call({
                            method: 'slcm.slcm.doctype.venue_booking.venue_booking.approve_venue_swap',
                            args: { booking_name: frm.doc.name, admin_remarks: vals.admin_remarks || '' },
                            freeze: true, freeze_message: __('Approving swap…'),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: __('Swap Approved — room updated'), indicator: 'green' });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Approve Swap Request'), __('Approve'));
                }, __('Swap Request'));

                frm.add_custom_button(__('Reject Swap'), function () {
                    frappe.prompt([{
                        label: __('Reason for Rejection'),
                        fieldname: 'admin_remarks',
                        fieldtype: 'Small Text',
                        reqd: 1
                    }], function (vals) {
                        frappe.call({
                            method: 'slcm.slcm.doctype.venue_booking.venue_booking.reject_venue_swap',
                            args: { booking_name: frm.doc.name, admin_remarks: vals.admin_remarks || '' },
                            freeze: true, freeze_message: __('Rejecting swap…'),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: __('Swap Request Rejected'), indicator: 'red' });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Reject Swap Request'), __('Reject'));
                }, __('Swap Request'));
            }

            // ── Approve (Pending only) ─────────────────────────────────
            if (frm.doc.status === 'Pending') {
                frm.add_custom_button(__('Approve'), function () {
                    frappe.prompt([
                        {
                            label: __('Remarks (optional)'),
                            fieldname: 'admin_remarks',
                            fieldtype: 'Small Text'
                        }
                    ], function (values) {
                        frappe.call({
                            method: 'slcm.slcm.doctype.venue_booking.venue_booking.approve_booking',
                            args: {
                                booking_name: frm.doc.name,
                                admin_remarks: values.admin_remarks || ''
                            },
                            freeze: true,
                            freeze_message: __('Approving…'),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: __('Booking Approved'), indicator: 'green' });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Approve Booking'), __('Approve'));
                }, __('Actions'));

                // ── Reject (Pending only) ──────────────────────────────
                frm.add_custom_button(__('Reject'), function () {
                    frappe.prompt([
                        {
                            label: __('Reason for Rejection'),
                            fieldname: 'admin_remarks',
                            fieldtype: 'Small Text',
                            reqd: 1
                        }
                    ], function (values) {
                        frappe.call({
                            method: 'slcm.slcm.doctype.venue_booking.venue_booking.reject_booking',
                            args: {
                                booking_name: frm.doc.name,
                                admin_remarks: values.admin_remarks || ''
                            },
                            freeze: true,
                            freeze_message: __('Rejecting…'),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: __('Booking Rejected'), indicator: 'red' });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Reject Booking'), __('Reject'));
                }, __('Actions'));
            }

            // ── Cancel (Pending or Approved) ───────────────────────────
            if (['Pending', 'Approved'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Cancel Booking'), function () {
                    frappe.prompt([
                        {
                            label: __('Reason for Cancellation'),
                            fieldname: 'admin_remarks',
                            fieldtype: 'Small Text'
                        }
                    ], function (values) {
                        frappe.call({
                            method: 'slcm.slcm.doctype.venue_booking.venue_booking.cancel_booking',
                            args: {
                                booking_name: frm.doc.name,
                                admin_remarks: values.admin_remarks || ''
                            },
                            freeze: true,
                            freeze_message: __('Cancelling…'),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({ message: __('Booking Cancelled'), indicator: 'orange' });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Cancel Booking'), __('Confirm Cancel'));
                }, __('Actions'));
            }

            // ── Swap Venue ─────────────────────────────────────────────
            if (frm.doc.docstatus < 2) {
                frm.add_custom_button(__('Swap Venue'), function () {
                    // Fetch all swappable bookings with their time details
                    frappe.call({
                        method: 'frappe.client.get_list',
                        args: {
                            doctype: 'Venue Booking',
                            filters: [
                                ['name', '!=', frm.doc.name],
                                ['docstatus', '<', 2],
                                ['status', '!=', 'Cancelled']
                            ],
                            fields: ['name', 'event_name', 'room', 'start_datetime', 'end_datetime', 'status'],
                            order_by: 'start_datetime asc',
                            limit: 200
                        },
                        callback: function (r) {
                            const bookings = r.message || [];
                            if (!bookings.length) {
                                frappe.msgprint(__('No other bookings available to swap with.'));
                                return;
                            }

                            function fmt_dt(dt) {
                                if (!dt) return '—';
                                const d = frappe.datetime.str_to_obj(dt);
                                return frappe.datetime.get_datetime_as_string(d)
                                    .replace(/:\d{2}$/, ''); // trim seconds
                            }

                            const options = bookings.map(b => {
                                const start = fmt_dt(b.start_datetime);
                                const end   = fmt_dt(b.end_datetime);
                                const label = `${b.name} | ${b.event_name || '—'} | ${b.room || '—'} | ${start} → ${end} [${b.status}]`;
                                return { value: b.name, label: label };
                            });

                            const d = new frappe.ui.Dialog({
                                title: __('Swap Venue'),
                                fields: [
                                    {
                                        label: __('Current Booking'),
                                        fieldname: 'current_info',
                                        fieldtype: 'HTML',
                                        options: `<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:10px 14px;margin-bottom:4px;font-size:12px;">
                                            <strong>${frm.doc.name}</strong> — ${frm.doc.event_name || '—'}<br>
                                            <span style="color:#0369a1;">
                                                📍 ${frm.doc.room || '—'} &nbsp;|&nbsp;
                                                🕐 ${fmt_dt(frm.doc.start_datetime)} → ${fmt_dt(frm.doc.end_datetime)}
                                            </span>
                                        </div>`
                                    },
                                    {
                                        label: __('Select Booking to Swap With'),
                                        fieldname: 'other_booking',
                                        fieldtype: 'Select',
                                        options: [''].concat(options.map(o => o.value)),
                                        reqd: 1,
                                        description: __('Showing: Booking ID | Event | Room | Start → End [Status]')
                                    },
                                    {
                                        label: __('Selected Booking Details'),
                                        fieldname: 'selected_info',
                                        fieldtype: 'HTML',
                                        options: '<div id="vb-swap-detail" style="min-height:20px;"></div>'
                                    }
                                ],
                                primary_action_label: __('Swap Venues'),
                                primary_action: function (vals) {
                                    if (!vals.other_booking) {
                                        frappe.msgprint(__('Please select a booking to swap with.'));
                                        return;
                                    }
                                    frappe.call({
                                        method: 'slcm.slcm.doctype.venue_booking.venue_booking.swap_venue',
                                        args: { booking_a: frm.doc.name, booking_b: vals.other_booking },
                                        freeze: true,
                                        freeze_message: __('Swapping venues…'),
                                        callback: function (r) {
                                            if (!r.exc) {
                                                frappe.show_alert({ message: __('Venues swapped successfully'), indicator: 'green' });
                                                d.hide();
                                                frm.reload_doc();
                                            }
                                        }
                                    });
                                }
                            });

                            // Replace select options with labelled display
                            d.show();
                            setTimeout(function () {
                                const $sel = d.get_field('other_booking').$input;
                                $sel.find('option').each(function () {
                                    const val = $(this).val();
                                    if (!val) return;
                                    const match = options.find(o => o.value === val);
                                    if (match) $(this).text(match.label);
                                });

                                // Show detail card on selection
                                $sel.on('change', function () {
                                    const val = $(this).val();
                                    const bk  = bookings.find(b => b.name === val);
                                    const $el  = d.wrapper.find('#vb-swap-detail');
                                    if (!bk) { $el.html(''); return; }
                                    $el.html(`<div style="background:#fefce8;border:1px solid #fde047;border-radius:6px;padding:10px 14px;font-size:12px;margin-top:4px;">
                                        <strong>${bk.name}</strong> — ${bk.event_name || '—'}<br>
                                        <span style="color:#854d0e;">
                                            📍 ${bk.room || '—'} &nbsp;|&nbsp;
                                            🕐 ${fmt_dt(bk.start_datetime)} → ${fmt_dt(bk.end_datetime)} &nbsp;|&nbsp;
                                            Status: <b>${bk.status}</b>
                                        </span>
                                    </div>`);
                                });
                            }, 200);
                        }
                    });
                }, __('Actions'));
            }
        }

        // ── Status colour banner ───────────────────────────────────────
        _set_status_banner(frm);
    },

    requester_type: function (frm) {
        _toggle_student_field(frm);
    }
});


// ─────────────────────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────────────────────

function _auto_fill_requester(frm) {
    // Set requester_name from current user's full name
    if (!frm.doc.requester_name) {
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'User',
                filters: { name: frappe.session.user },
                fieldname: 'full_name'
            },
            callback: function (r) {
                if (r.message && r.message.full_name) {
                    frm.set_value('requester_name', r.message.full_name);
                }
            }
        });
    }

    // Auto-detect requester_type from roles
    if (!frm.doc.requester_type) {
        const roles = frappe.user_roles || [];
        let rtype = 'Other';
        if (roles.includes('slcm_Student'))       rtype = 'Student';
        else if (roles.includes('slcm_Faculty'))  rtype = 'Faculty';
        else if (roles.includes('slcm_Staff'))    rtype = 'Staff';
        frm.set_value('requester_type', rtype);
    }
}

function _toggle_student_field(frm) {
    const isStudent = (frm.doc.requester_type === 'Student');
    frm.toggle_display('student', isStudent);
    frm.toggle_reqd('student', false); // student is always optional (auto-filled server-side)
}

function _set_status_banner(frm) {
    if (frm.is_new()) return;
    const colors = {
        'Pending':   'yellow',
        'Approved':  'green',
        'Rejected':  'red',
        'Cancelled': 'grey'
    };
    const indicator = colors[frm.doc.status] || 'blue';
    frm.set_indicator_formatter('status', function () { return indicator; });
}
