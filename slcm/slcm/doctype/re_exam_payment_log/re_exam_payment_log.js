// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Re Exam Payment Log", {
    refresh(frm) {
        if (frm.doc.re_exam_registration) {
            frm.add_custom_button(__("Open Registration"), function () {
                frappe.set_route("Form", "Re Exam Registration", frm.doc.re_exam_registration);
            });
        }
    },
});
