frappe.ui.form.on('Venue Booking', {
    refresh: function (frm) {
        // Add status action buttons for Pending bookings
        if (!frm.is_new() && frm.doc.status === 'Pending' && frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Approve'), function () {
                frappe.call({
                    method: 'frappe.client.set_value',
                    args: {
                        doctype: 'Venue Booking',
                        name: frm.doc.name,
                        fieldname: 'status',
                        value: 'Approved'
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('Booking Approved'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Actions'));

            frm.add_custom_button(__('Reject'), function () {
                frappe.call({
                    method: 'frappe.client.set_value',
                    args: {
                        doctype: 'Venue Booking',
                        name: frm.doc.name,
                        fieldname: 'status',
                        value: 'Rejected'
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('Booking Rejected'),
                                indicator: 'red'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Actions'));
        }

        // Add "Swap Venue" button only for saved bookings
        if (!frm.is_new() && frm.doc.docstatus < 2) {
            frm.add_custom_button(__('Swap Venue'), function () {
                // Prompt user to select another booking to swap with
                frappe.prompt({
                    label: __('Select Booking to Swap With'),
                    fieldname: 'other_booking',
                    fieldtype: 'Link',
                    options: 'Venue Booking',
                    get_query: function () {
                        return {
                            filters: {
                                'name': ['!=', frm.doc.name],
                                'docstatus': ['<', 2]
                            }
                        };
                    },
                    reqd: 1
                }, function (values) {
                    // Call the swap_venue method
                    frappe.call({
                        method: 'slcm.slcm.doctype.venue_booking.venue_booking.swap_venue',
                        args: {
                            booking_a: frm.doc.name,
                            booking_b: values.other_booking
                        },
                        freeze: true,
                        freeze_message: __('Swapping venues...'),
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
});
