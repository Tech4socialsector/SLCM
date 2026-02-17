// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Campus", {
    validate: function (frm) {
        const regex = /^[1-9][0-9]{5}$/;
        if (frm.doc.zip_code && !regex.test(frm.doc.zip_code)) {
            frappe.throw("Please enter a valid 6-digit PIN code.");
        }
    },

    refresh: async function (frm) {
        if (!frm.doc.allow_admission) {
            frm.set_intro("If you want to participate in admission process, please enable the 'Allow Admission' checkbox.", "blue");
            return;
        }

        let r = await frappe.db.get_value(
            "Admission Year",
            { is_active: 1 },
            ["name", "allow_campus_enrollment", "application_start_date", "academic_year"]
        );

        if (!r || !r.message) {
            frm.set_intro("No Active Admission Year found", "red");
            return;
        }

        let admission_year = r.message;

        if (admission_year.allow_campus_enrollment) {
            let d = frappe.datetime.str_to_obj(admission_year.application_start_date);

            let formatted =
                ("0" + d.getDate()).slice(-2) + "-" +
                ("0" + (d.getMonth() + 1)).slice(-2) + "-" +
                d.getFullYear();

            frm.set_intro(
                `Admission is open for Academic Year ${admission_year.academic_year} from ${formatted}`,
                "green"
            );
            frm.add_custom_button(
                "Add Program Offering",
                function () {
                    frappe.new_doc("Program Offering", {
                        campus: frm.doc.name
                    });
                }
            );

        }
    }

});
