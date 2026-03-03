// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Interview Seat Allocation", {
    refresh(frm) {
        // show/hide reschedule tab depending on flag or status
        const is_rescheduled = frm.doc.is_rescheduled == 1 || frm.doc.interview_status === "Rescheduled";
        frm.set_df_property("tab_9_tab", "hidden", !is_rescheduled);
        frm.set_df_property("reschedule_section", "hidden", !is_rescheduled);

        // apply applicant restrictions
        if (frappe.user_roles.includes("Applicant")) {
            _apply_applicant_permissions(frm);
        }
    },
});

function _apply_applicant_permissions(frm) {
    // Reference section read-only
    const ref_fields = [
        "interview_list", "academic_year", "admission_cycle",
        "campus", "program_level"
    ];
    ref_fields.forEach(f => frm.set_df_property(f, "read_only", 1));

    // Applicant info read-only
    const info_fields = [
        "applicant", "candidate_name", "program", "reservation_category",
        "email", "gender"
    ];
    info_fields.forEach(f => frm.set_df_property(f, "read_only", 1));

    // Slot section read-only except interview_staff_member until assigned
    const slot_readonly = [
        "staff_name", "staff_email", "staff_contact",
        "interview_date", "interview_time", "interview_slot_status",
        "slot_assigned_by"
    ];
    slot_readonly.forEach(f => frm.set_df_property(f, "read_only", 1));

    // Allow staff selection until slot status changes
    const assigned_statuses = ["Slot Assigned", "Confirmed", "Cancelled", "Rescheduled"];
    const is_assigned = assigned_statuses.includes(frm.doc.interview_slot_status);
    frm.set_df_property("interview_staff_member", "read_only", is_assigned ? 1 : 0);

    // Reschedule tab hidden for applicants until flagged
    const resched = frm.doc.is_rescheduled == 1 || frm.doc.interview_status === "Rescheduled";
    frm.set_df_property("tab_9_tab", "hidden", !resched);
    frm.set_df_property("reschedule_section", "hidden", !resched);

    if (resched) {
        // make all re_ fields read-only
        const re_fields = [
            "re_interview_staff_member", "re_staff_name", "re_staff_email",
            "re_staff_contact", "re_interview_date", "re_interview_time",
            "re_interview_slot_status", "re_slot_assigned_by", "reschedule_reason"
        ];
        re_fields.forEach(f => frm.set_df_property(f, "read_only", 1));
    }
}
