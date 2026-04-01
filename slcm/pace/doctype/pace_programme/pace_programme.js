// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("PACE Programme", {
	refresh(frm) {
        frm.set_query("course", () => {
            return {
                filters: {
                    "programme": frm.doc.name
                }
            }
        })
	},
});
