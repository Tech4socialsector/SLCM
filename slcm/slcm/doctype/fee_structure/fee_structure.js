frappe.ui.form.on("Fee Structure", {
    refresh: function (frm) {
        // Only restrict the datepicker for BRAND NEW records
        if (frm.doc.__islocal) {
            const today = new Date(frappe.datetime.get_today());

            if (frm.fields_dict.valid_from && frm.fields_dict.valid_from.datepicker) {
                frm.fields_dict.valid_from.datepicker.update({
                    minDate: today,
                });
            }

            if (frm.fields_dict.valid_until && frm.fields_dict.valid_until.datepicker) {
                let until_min = frm.doc.valid_from ? new Date(frm.doc.valid_from) : today;
                frm.fields_dict.valid_until.datepicker.update({
                    minDate: until_min,
                });
            }
        }
    },

    valid_from: function (frm) {
        // When valid_from changes, update valid_until's picker range immediately
        if (frm.doc.valid_from && frm.fields_dict.valid_until && frm.fields_dict.valid_until.datepicker) {
            frm.fields_dict.valid_until.datepicker.update({
                minDate: new Date(frm.doc.valid_from),
            });

            // If valid_until is now before valid_from, clear it
            if (frm.doc.valid_until && frm.doc.valid_until < frm.doc.valid_from) {
                frm.set_value('valid_until', null);
            }
        }
    },

    status: function (frm) {
        if (frm.doc.status === "Inactive" && !frm.is_new()) {
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Fee Structure Child",
                    filters: {
                        fee_structure: frm.doc.name,
                        parenttype: "Offer Configuration"
                    },
                    fields: ["parent"],
                    limit: 1
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        const oc_name = r.message[0].parent;
                        frappe.msgprint({
                            title: __("Linked Configuration"),
                            message: __("This Fee Structure is used in Offer Configuration <b>. Please remove it from there before setting it to Inactive.", [oc_name]),
                            indicator: "red"
                        });
                        // Revert status
                        frm.set_value("status", "Active");
                    }
                }
            });
        }
    },

    validate: function (frm) {
        let today = frappe.datetime.get_today();

        // 1. Block past dates for Valid From ONLY when creating a NEW record
        // This ensures existing records with past dates remain editable.
        if (frm.doc.__islocal && frm.doc.valid_from && frm.doc.valid_from < today) {
            frappe.throw({
                title: __("Invalid Date"),
                message: __("Valid From date cannot be in the past ({0}).", [frappe.datetime.str_to_user(frm.doc.valid_from)])
            });
        }

        // 2. Ensure Valid Until is not before Valid From
        if (frm.doc.valid_from && frm.doc.valid_until) {
            if (frm.doc.valid_until < frm.doc.valid_from) {
                frappe.throw({
                    title: __("Invalid Range"),
                    message: __("Valid Until must be equal to or greater than Valid From.")
                });
            }
        }
    }
});
