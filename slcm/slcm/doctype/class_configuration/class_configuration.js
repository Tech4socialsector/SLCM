// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Class Configuration', {
    refresh: function (frm) {
        // Set filters for links
        set_link_filters(frm);
    },

    add_students_by_filter: function (frm) {
        add_students_by_filter(frm);
    },

    clear_all_students: function (frm) {
        clear_all_students(frm);
    },

    programme: function (frm) {
        set_link_filters(frm);
    },

    batch: function (frm) {
        set_link_filters(frm);
    },

    section: function (frm) {
        set_link_filters(frm);
    },

    term: function (frm) {
        if (frm.doc.term) {
            // Fetch term details
            frappe.db.get_value('Term Configuration', frm.doc.term,
                ['academic_year', 'system'], (r) => {
                    if (r) {
                        frm.set_df_property('term', 'description',
                            `Academic Year: ${r.academic_year}, System: ${r.system}`);
                    }
                });
        }
    },

    course: function (frm) {
        if (frm.doc.course && !frm.doc.class_name) {
            // Auto-generate class name suggestion
            generate_class_name(frm);
        }
    },

    type: function (frm) {
        if (!frm.doc.class_name) {
            generate_class_name(frm);
        }
    }
});

frappe.ui.form.on('Class Student', {
    student: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.student) {
            // Fetch student details
            frappe.db.get_value('Student Master', row.student,
                ['first_name', 'middle_name', 'last_name', 'registration_id', 'email'], (r) => {
                    if (r) {
                        let student_name = [r.first_name, r.middle_name, r.last_name].filter(Boolean).join(" ");
                        frappe.model.set_value(cdt, cdn, 'student_name', student_name);
                        frappe.model.set_value(cdt, cdn, 'registration_id', r.registration_id);
                        frappe.model.set_value(cdt, cdn, 'email', r.email);
                    }
                });
        }
    }
});

function set_link_filters(frm) {
    // Only show students actually enrolled (via Student Enrollment) in this
    // class's programme/batch/section - Student Master has no batch/section
    // field of its own, so this goes through a custom server-side query.
    if (frm.doc.batch) {
        frm.set_query('student', 'students', function () {
            return {
                query: 'slcm.slcm.doctype.class_configuration.class_configuration.student_query',
                filters: {
                    programme: frm.doc.programme,
                    batch: frm.doc.batch,
                    section: frm.doc.section,
                },
            };
        });
    }
}

function generate_class_name(frm) {
    let parts = [];
    if (frm.doc.course) {
        parts.push(frm.doc.course);
    }
    if (frm.doc.type) {
        parts.push(frm.doc.type);
    }
    if (frm.doc.batch) {
        parts.push(frm.doc.batch);
    }
    if (frm.doc.section) {
        parts.push(frm.doc.section);
    }

    if (parts.length > 0) {
        frm.set_value('class_name', parts.join(' - '));
    }
}

function add_students_by_filter(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Add Students by Filter'),
        fields: [
            {
                fieldname: 'programme',
                fieldtype: 'Link',
                label: __('Programme'),
                options: 'Programme',
                default: frm.doc.programme
            },
            {
                fieldname: 'batch',
                fieldtype: 'Link',
                options: 'Batch',
                label: __('Batch'),
                default: frm.doc.batch
            },
            {
                fieldname: 'section',
                fieldtype: 'Link',
                options: 'Section',
                label: __('Section'),
                default: frm.doc.section
            }
        ],
        primary_action_label: __('Add Students'),
        primary_action: function (values) {
            frappe.call({
                method: 'slcm.slcm.doctype.class_configuration.class_configuration.get_students_by_filter',
                args: {
                    programme: values.programme,
                    batch: values.batch,
                    section: values.section
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        r.message.forEach(function (student) {
                            // Check if student already exists
                            let exists = frm.doc.students.find(
                                row => row.student === student.name
                            );

                            if (!exists) {
                                let row = frm.add_child('students');
                                row.student = student.name;
                                row.student_name = [student.first_name, student.middle_name, student.last_name].filter(Boolean).join(" ");
                                row.registration_id = student.registration_id;
                                row.email = student.email;
                            }
                        });
                        frm.refresh_field('students');
                        frappe.msgprint(__(`${r.message.length} students added successfully`));
                    } else {
                        frappe.msgprint(__('No students found with the given filters'));
                    }
                }
            });
            d.hide();
        }
    });
    d.show();
}

function clear_all_students(frm) {
    frappe.confirm(
        __('Are you sure you want to clear all students?'),
        function () {
            frm.clear_table('students');
            frm.refresh_field('students');
            frappe.msgprint(__('All students cleared'));
        }
    );
}
