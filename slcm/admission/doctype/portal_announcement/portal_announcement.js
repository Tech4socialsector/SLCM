frappe.ui.form.on("Portal Announcement", {
    refresh: function (frm) {
        // Status badge
        const colors = { "Draft": "gray", "Published": "green", "Archived": "red" };
        frm.dashboard.set_headline_alert(
            __(frm.doc.status),
            colors[frm.doc.status] || "gray"
        );

        // Publish now button
        if (frm.doc.status === "Draft" && !frm.is_new()) {
            frm.add_custom_button(__("Publish Now"), function () {
                frappe.confirm(__("Publish this announcement immediately?"), function () {
                    frappe.call({
                        method: "frappe.client.set_value",
                        args: {
                            doctype: "Portal Announcement",
                            name: frm.doc.name,
                            fieldname: { status: "Published", show_on_portal: 1 }
                        },
                        callback: function () {
                            frm.reload_doc();
                            frappe.show_alert({ message: __("Published successfully"), indicator: "green" }, 4);
                        }
                    });
                });
            }, __("Actions"));
        }

        // Archive button
        if (frm.doc.status === "Published") {
            frm.add_custom_button(__("Archive"), function () {
                frappe.confirm(__("Archive this announcement?"), function () {
                    frappe.call({
                        method: "frappe.client.set_value",
                        args: {
                            doctype: "Portal Announcement",
                            name: frm.doc.name,
                            fieldname: { status: "Archived", show_on_portal: 0 }
                        },
                        callback: function () { frm.reload_doc(); }
                    });
                });
            }, __("Actions"));
        }

        // Date constraints
        const today = new Date(frappe.datetime.get_today());

        if (frm.fields_dict.publish_date && frm.fields_dict.publish_date.datepicker) {
            frm.fields_dict.publish_date.datepicker.update({
                minDate: today,
            });
        }

        if (frm.fields_dict.expiry_date && frm.fields_dict.expiry_date.datepicker) {
            let until_min = frm.doc.publish_date ? new Date(frm.doc.publish_date) : today;
            frm.fields_dict.expiry_date.datepicker.update({
                minDate: until_min,
            });
        }
        if (frm.doc.publish_date && frm.fields_dict.event_date && frm.fields_dict.event_date.datepicker) {
            frm.fields_dict.event_date.datepicker.update({
                minDate: new Date(frm.doc.publish_date),
            });
        }
    },

    publish_date: function (frm) {
        if (frm.doc.publish_date && frm.fields_dict.expiry_date && frm.fields_dict.expiry_date.datepicker) {
            frm.fields_dict.expiry_date.datepicker.update({
                minDate: new Date(frm.doc.publish_date),
            });
        }
        if (frm.doc.publish_date && frm.fields_dict.event_date && frm.fields_dict.event_date.datepicker) {
            frm.fields_dict.event_date.datepicker.update({
                minDate: new Date(frm.doc.publish_date),
            });
        }
    },

    announcement_type: function (frm) {
        frm.toggle_display("event_date", frm.doc.announcement_type === "Event");
        frm.toggle_display("event_venue", frm.doc.announcement_type === "Event");
        frm.toggle_display("event_registration_url", frm.doc.announcement_type === "Event");
    }
});
