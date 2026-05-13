frappe.ui.form.on('Venue Booking', {
    refresh: function (frm) {
        const canManage = frappe.user.has_role(['System Manager', 'Administrator', 'slcm_Faculty', 'slcm_Registrar']);

        if (!frm.is_new() && canManage) {
            // Approve — only for Pending bookings
            if (frm.doc.status === 'Pending') {
                frm.add_custom_button(__('Approve'), function () {
                    frappe.call({
                        method: 'slcm.slcm.doctype.venue_booking.venue_booking.approve_booking',
                        args: { booking_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __('Approving…'),
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.show_alert({ message: __('Booking Approved'), indicator: 'green' });
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('Actions'));

                // Reject — prompt for remarks
                frm.add_custom_button(__('Reject'), function () {
                    frappe.prompt([
                        {
                            label: __('Remarks (optional)'),
                            fieldname: 'admin_remarks',
                            fieldtype: 'Small Text'
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

            // Cancel — for Pending or Approved bookings
            if (['Pending', 'Approved'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Cancel Booking'), function () {
                    frappe.prompt([
                        {
                            label: __('Remarks (optional)'),
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
        }

        // Swap Venue — for any saved booking not hard-cancelled (docstatus < 2)
        if (!frm.is_new() && frm.doc.docstatus < 2 && canManage) {
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
                                frappe.show_alert({ message: __('Venues swapped successfully'), indicator: 'green' });
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('Swap Venue'), __('Swap'));
            }, __('Actions'));
        }
    }
});
