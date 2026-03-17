// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Interview Seat Allocation", {
    refresh(frm) {
        // Administrator can do everything — skip all restrictions
        if (frappe.user_roles.includes("Administrator")) {
            // Ensure all tabs/sections are visible and editable
            frm.set_df_property("tab_9_tab", "hidden", 0);
            frm.set_df_property("reschedule_section", "hidden", 0);
            return;
        }

        // show/hide reschedule tab depending on flag or status
        const is_rescheduled = frm.doc.is_rescheduled == 1 || frm.doc.interview_status === "Rescheduled";
        frm.set_df_property("tab_9_tab", "hidden", !is_rescheduled);
        frm.set_df_property("reschedule_section", "hidden", !is_rescheduled);

        // apply applicant restrictions
        if (frappe.user_roles.includes("Applicant")) {
            _apply_applicant_permissions(frm);
        }
    },

    // ── Applicant field change ───────────────────────────────────────────────
    applicant(frm) {
        if (!frm.doc.applicant) {
            frm.set_df_property("category", "hidden", 1);
            return;
        }

        // Fetch all needed Applicant information including categories
        frappe.call({
            method: "frappe.client.get",
            args: { doctype: "Applicant", name: frm.doc.applicant },
            callback: function (r) {
                if (!r.message) return;
                const app = r.message;

                // Populate standard fields
                frm.set_value("candidate_name", app.candidate_name);
                frm.set_value("program", app.program);
                frm.set_value("email", app.email);
                frm.set_value("gender", app.gender);

                // Source tracking fields (if present on the form)
                if (app.exempts_entrance_test !== undefined) {
                    frm.set_value("exempts_entrance_test", app.exempts_entrance_test);
                }
                if (app.exempts_interview !== undefined) {
                    frm.set_value("exempts_interview", app.exempts_interview);
                }

                // Show the category table and populate it from reservation fields
                frm.clear_table("category");
                if (app.whether_scstobc_ncl && app.whether_scstobc_ncl !== "NA") {
                    frm.add_child("category", { category: app.whether_scstobc_ncl });
                }
                if (app.pwd === "Yes") {
                    frm.add_child("category", { category: "PWD" });
                }
                if (app.karnataka_category === "Yes") {
                    frm.add_child("category", { category: "Karnataka category" });
                }
                if (app.ews === "Yes") {
                    frm.add_child("category", { category: "EWS" });
                }
                frm.refresh_field("category");
                frm.set_df_property("category", "hidden", 0);
            }
        });
    },

    interview_score: function (frm) {
        if (frm.doc.interview_score > 100) {
            frappe.msgprint({
                title: __("Invalid Score"),
                indicator: "red",
                message: __("Interview Score cannot be more than 100. The field has been cleared.")
            });
            frm.set_value("interview_score", "");
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

    // Applicant info read-only (including the category table)
    const info_fields = [
        "applicant", "candidate_name", "program",
        "email", "gender"
    ];
    info_fields.forEach(f => frm.set_df_property(f, "read_only", 1));

    // Make the category child table read-only for applicants
    frm.set_df_property("category", "read_only", 1);

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

    // Feedback field logic
    const results_ready = frm.doc.result_published == 1 || (frm.doc.rank && frm.doc.rank > 0);
    
    // Show feedback only when ranks/results are updated
    frm.set_df_property("feedback", "hidden", !results_ready);
    
    if (results_ready) {
        // Mandatory if empty, Read-only if already submitted (has value)
        const has_feedback = !!(frm.doc.feedback && frm.doc.feedback.trim());
        frm.set_df_property("feedback", "reqd", !has_feedback);
        frm.set_df_property("feedback", "read_only", has_feedback);
    }

    // Result section read-only for applicants
    const result_fields = [
        "interview_status", "attendance_marked_on", "interview_score",
        "interview_result_status", "rank", "result_published"
    ];
    result_fields.forEach(f => frm.set_df_property(f, "read_only", 1));
}
