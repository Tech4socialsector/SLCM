// Copyright (c) 2025, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Attendance", {
    student(frm) {
        if (frm.doc.student) {
            // Clear course offer and course to force re-selection
            frm.set_value('course_offer', '');
            frm.set_value('course', '');

            // Fetch enrolled batches
            frappe.call({
                method: "slcm.slcm.doctype.student_attendance.student_attendance.get_enrolled_batches",
                args: {
                    student: frm.doc.student
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        // Filter Course Offering by these batches
                        frm.set_query("course_offer", function () {
                            return {
                                filters: {
                                    batch: ["in", r.message]
                                }
                            };
                        });
                    } else {
                        // If no enrollments, show empty or all? Default to empty to prevent error
                        frm.set_query("course_offer", function () {
                            return {
                                filters: {
                                    name: ["in", []] // Force empty
                                }
                            };
                        });
                        frappe.msgprint(__("Selected student is not enrolled in any active batches."));
                    }
                }
            });
        }
    }
});
frappe.listview_settings["Student Attendance"] = {
    onload(listview) {
        // Exclude auto-created placeholder records from the list.
        // source="Auto" records are roster entries created by Attendance Session on insert —
        // they are NOT actual marked attendance and should not appear here.
        listview.filter_area.add([
            ["Student Attendance", "source", "!=", "Auto"]
        ]);

        const style = document.createElement("style");
        style.innerHTML = `
            /* Hide ONLY the heart icon */
            .list-row-like {
                display: none !important;
            }

            /* Hide ONLY the comment icon + count */
            .list-row-activity .comment-count,
            .list-row-activity .comments,
            .list-row-activity .comment-icon,
            .list-row-activity svg.icon-xs {
                display: none !important;
            }
        `;
        document.head.appendChild(style);
    },

    refresh(_listview) {
        $("span.sidebar-toggle-btn").hide();
        $(".col-lg-2.layout-side-section").hide();
    },
};
