// Copyright (c) 2026, TFSS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Merit Rule", {
    refresh(frm) {
        // Strictly prevent non-numeric input in minimum_marks
        if (frm.fields_dict["minimum_marks"]) {
            frm.fields_dict["minimum_marks"].$input.on('input', function() {
                let value = this.value.replace(/[^0-9.]/g, '');
                if ((value.match(/\./g) || []).length > 1) {
                    value = value.replace(/\.+$/, "");
                }
                if (this.value !== value) {
                    this.value = value;
                }
            });
        }
    },
    effective_from(frm) {
        if (frm.doc.effective_from && frm.doc.effective_from < frappe.datetime.get_today()) {
            frappe.msgprint(__("Effective From date cannot be in the past"));
            frm.set_value("effective_from", "");
        }
    },
    onload:function(frm){
        frm.set_query("admission_cycle", function() {
            return {
                filters: {
                    status: "Active"
                }
            };
        });
    },
    effective_to(frm) {
        if (frm.doc.effective_from && frm.doc.effective_to && frm.doc.effective_to <= frm.doc.effective_from) {
            frappe.msgprint(__("Effective To date must be after Effective From date"));
            frm.set_value("effective_to", "");
        }
    }
});
