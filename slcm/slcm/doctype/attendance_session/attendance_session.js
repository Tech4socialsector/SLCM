// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attendance Session", {


    session_start_time: function (frm) {
        frm.events.calculate_duration(frm);
    },

    session_end_time: function (frm) {
        frm.events.calculate_duration(frm);
    },

    calculate_duration: function (frm) {
        if (frm.doc.session_start_time && frm.doc.session_end_time) {
            // Parse time strings (format: HH:MM:SS)
            const start_parts = frm.doc.session_start_time.split(':');
            const end_parts = frm.doc.session_end_time.split(':');

            // Create Date objects for today with the specified times
            const start_date = new Date();
            start_date.setHours(parseInt(start_parts[0]), parseInt(start_parts[1]), parseInt(start_parts[2] || 0), 0);

            const end_date = new Date();
            end_date.setHours(parseInt(end_parts[0]), parseInt(end_parts[1]), parseInt(end_parts[2] || 0), 0);

            // Calculate difference in milliseconds and convert to hours
            const diff_ms = end_date - start_date;
            const duration_hours = diff_ms / (1000 * 60 * 60);

            // Set the duration field (rounded to 2 decimal places)
            frm.set_value('duration_hours', parseFloat(duration_hours.toFixed(2)));
        }
    },


});
