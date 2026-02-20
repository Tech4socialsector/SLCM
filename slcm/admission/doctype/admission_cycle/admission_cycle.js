// Copyright (c) 2026, TFSS and contributors
// Admission Cycle Client Script

const STAGE_CONFIG_FIELDS = [
    "enable_entrance_test", "enable_interview",
    "enable_document_verification", "enable_scholarship",
    "enable_group_discussion"
];

frappe.ui.form.on("Admission Cycle", {

    onload(frm) {
        // set_lock_state(frm);
        // show_override_warning(frm);
    },

    refresh(frm) {
        // set_lock_state(frm);
        // show_override_warning(frm);

        // // Filter: Admission Cycle should filter by admission_year if available
        // frm.set_query("admission_year", function () {
        //     return { filters: { is_active: 1 } };
        // });
    },

    admission_year(frm) {
        // if (!frm.doc.admission_year) return;
        // // Auto-populate stage config from Admission Year
        // frappe.db.get_value(
        //     "Admission Year",
        //     frm.doc.admission_year,
        //     STAGE_CONFIG_FIELDS,
        //     function (r) {
        //         if (r) {
        //             STAGE_CONFIG_FIELDS.forEach(f => frm.set_value(f, r[f]));
        //         }
        //     }
        // );
    },

    before_save(frm) {
        // if (!frm.doc.stage_locked) return;
        // // Detect if any stage config field changed
        // const changed = STAGE_CONFIG_FIELDS.filter(f => frm.doc[f] !== frm.doc.__onload?.[f]);
        // if (!changed.length) return;
        // // If user is System Manager, prompt for override reason
        // if (frappe.user.has_role("System Manager")) {
        //     frappe.prompt(
        //         [{ fieldname: "reason", fieldtype: "Small Text", label: "Lock Override Reason", reqd: 1 }],
        //         function (values) {
        //             frm.set_value("lock_override_reason", values.reason);
        //             frm.save();
        //         },
        //         __("Stage Config Override"),
        //         __("Submit Override")
        //     );
        //     frappe.validated = false;
        // }
    }
});

function set_lock_state(frm) {
    const readonly = frm.doc.stage_locked ? 1 : 0;
    [...STAGE_CONFIG_FIELDS, "stage_config_overridden"].forEach(f => {
        frm.set_df_property(f, "read_only", readonly);
    });
    if (frm.doc.stage_locked) {
        frm.set_df_property("lock_override_reason", "hidden", 1);
    }
}

function show_override_warning(frm) {
    if (frm.doc.stage_config_overridden) {
        frm.set_intro(
            __("⚠️ Stage configuration on this cycle differs from the Admission Year defaults."),
            "yellow"
        );
    }
}
