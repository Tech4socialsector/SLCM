frappe.ui.form.on('Venue Booking', {
    onload: function (frm) {
        if (frm.is_new()) {
            _auto_fill_requester(frm);
        }
    },

    refresh: function (frm) {
        _toggle_student_field(frm);

        const canManage = frappe.user.has_role([
            'System Manager', 'Administrator', 'slcm_Faculty', 'slcm_Registrar'
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
                    frappe.prompt({
                        label: __('Select Booking to Swap With'),
                        fieldname: 'other_booking',
                        fieldtype: 'Link',
                        options: 'Venue Booking',
                        get_query: function () {
                            return {
                                filters: {
                                    'name': ['!=', frm.doc.name],
                                    'docstatus': ['<', 2],
                                    'status': ['!=', 'Cancelled']
                                }
                            };
                        },
                        reqd: 1
                    }, function (values) {
                        frappe.call({
                            method: 'slcm.slcm.doctype.venue_booking.venue_booking.swap_venue',
                            args: {
                                booking_a: frm.doc.name,
                                booking_b: values.other_booking
                            },
                            freeze: true,
                            freeze_message: __('Swapping venues…'),
                            callback: function (r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __('Venues swapped successfully'),
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Swap Venue'), __('Swap'));
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
