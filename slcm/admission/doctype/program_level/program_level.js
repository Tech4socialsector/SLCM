// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Program Level", {
    refresh(frm) {

    },
    validate: function (frm) {
        const regex = /^[A-Z]{2}$/;
        if (frm.doc.category_code && !regex.test(frm.doc.category_code)) {
            frappe.throw("Please enter a valid category code.");
        }
    },

    onload: function (frm) {
        if (!frm.doc.is_active) {
            frm.set_intro("Enable Active to make this program category active.", "blue")
        } else if (frm.doc.is_active == 1) {
            frm.set_intro(`${frm.doc.category_name} program is active.`, "green")
        }
    }
});
