// Copyright (c) 2026, CU and contributors
// For license information, please see license.txt

frappe.ui.form.on('Class Schedule', {
    refresh: function (frm) {
        // Auto-generate title if not set
        if (!frm.doc.title && frm.doc.course) {
            frm.trigger('generate_title');
        }

        if (!frm.is_new()) {
            frm.add_custom_button(__('Mark Attendance'), function () {
                frappe.route_options = {
                    'based_on': 'Class Schedule',
                    'class_schedule': frm.doc.name,
                    'student_group': frm.doc.student_group,
                    'date': frm.doc.schedule_date
                };
                frappe.set_route('Form', 'Student Attendance Tool');
            });
        }
    },

    class_configuration: function (frm) {
        if (frm.doc.class_configuration) {
            // Fetch details from Class Configuration
            frappe.db.get_value('Class Configuration', frm.doc.class_configuration,
                ['course', 'faculty', 'programme', 'term', 'department'], (r) => {
                    if (r) {
                        frm.set_value('course', r.course);
                        frm.set_value('instructor', r.faculty);
                        frm.set_value('programme', r.programme);
                        frm.set_value('term', r.term);
                        frm.set_value('department', r.department);
                    }
                });
        }
    },

    course: function (frm) {
        frm.events.get_title(frm);
    },

    course_offering: function (frm) {
        if (frm.doc.course_offering) {
            frappe.db.get_value("Course Offering", frm.doc.course_offering, ["course_title", "program", "faculty"], (r) => {
                if (r) {
                    frm.set_value("course", r.course_title);
                    frm.set_value("programme", r.program);
                    if (r.faculty) frm.set_value("instructor", r.faculty);
                }
            });
        }
    },

    class_schedule_color: function (frm) {
        // Map color name to hex color
        const colorMap = {
            'Blue': '#3498db',
            'Green': '#2ecc71',
            'Red': '#e74c3c',
            'Yellow': '#f39c12',
            'Orange': '#e67e22',
            'Purple': '#9b59b6',
            'Pink': '#e91e63',
            'Gray': '#95a5a6'
        };

        if (frm.doc.class_schedule_color && colorMap[frm.doc.class_schedule_color]) {
            frm.set_value('color', colorMap[frm.doc.class_schedule_color]);
        }
    },

    generate_title: function (frm) {
        if (frm.doc.course) {
            let title = frm.doc.course;
            if (frm.doc.room) {
                title += ' - ' + frm.doc.room;
            }
            frm.set_value('title', title);
        }
    },

    repeat_frequency: function (frm) {
        if (frm.doc.repeat_frequency === 'Never' || !frm.doc.repeat_frequency) {
            frm.set_value('repeats_till', null);
        }
    },

    validate: function (frm) {
        // Validate repeat settings
        if (frm.doc.repeat_frequency && frm.doc.repeat_frequency !== 'Never') {
            if (!frm.doc.repeats_till) {
                frappe.msgprint(__('Please specify "Repeats Till" date for recurring schedules'));
                frappe.validated = false;
            }
            if (frm.doc.repeats_till && frm.doc.repeats_till < frm.doc.schedule_date) {
                frappe.msgprint(__('Repeats Till date cannot be before Schedule Date'));
                frappe.validated = false;
            }
        }

        // Validate time
        if (frm.doc.from_time && frm.doc.to_time && frm.doc.from_time >= frm.doc.to_time) {
            frappe.msgprint(__('To Time must be after From Time'));
            frappe.validated = false;
        }
    },

    from_time: function (frm) {
        frm.events.calculate_duration(frm);
        frm.events.sync_to_attendance_session(frm);
    },

    to_time: function (frm) {
        frm.events.calculate_duration(frm);
        frm.events.sync_to_attendance_session(frm);
    },

    calculate_duration: function (frm) {
        if (frm.doc.from_time && frm.doc.to_time) {
            // Parse time strings (format: HH:MM:SS)
            const from_parts = frm.doc.from_time.split(':');
            const to_parts = frm.doc.to_time.split(':');

            // Create Date objects for today with the specified times
            const from_date = new Date();
            from_date.setHours(parseInt(from_parts[0]), parseInt(from_parts[1]), parseInt(from_parts[2] || 0), 0);

            const to_date = new Date();
            to_date.setHours(parseInt(to_parts[0]), parseInt(to_parts[1]), parseInt(to_parts[2] || 0), 0);

            // Calculate difference in milliseconds and convert to hours
            const diff_ms = to_date - from_date;
            const duration_hours = diff_ms / (1000 * 60 * 60);

            // Set the duration field (rounded to 2 decimal places)
            frm.set_value('duration_hours', parseFloat(duration_hours.toFixed(2)));
        }
    },

    sync_to_attendance_session: function (frm) {
        // Only sync if the document is saved (has a name)
        if (!frm.doc.name || frm.is_new()) {
            return;
        }

        // Only sync if we have valid times
        if (!frm.doc.from_time || !frm.doc.to_time) {
            return;
        }

        // Call server method to update Attendance Session in real-time
        frappe.call({
            method: 'slcm.slcm.doctype.class_schedule.class_schedule.update_attendance_session_realtime',
            args: {
                class_schedule_name: frm.doc.name,
                from_time: frm.doc.from_time,
                to_time: frm.doc.to_time,
                schedule_date: frm.doc.schedule_date,
                duration_hours: frm.doc.duration_hours
            },
            callback: function (r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __('Attendance Session updated'),
                        indicator: 'green'
                    }, 3);
                }
            }
        });
    }
});
