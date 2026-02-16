// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Campus", {
    refresh(frm) {

    },

    onload: function (frm) {
        frm.set_intro("Campus is a physical location where the institution operates. It can be a main campus or a satellite campus.");
    }
});
