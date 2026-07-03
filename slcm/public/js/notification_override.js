const old_function = frappe.notification.setup_fieldname_select;

frappe.notification.setup_fieldname_select = function(frm) {

    old_function(frm);

    if (
        !frm.doc.document_type ||
        frm.doc.channel !== "System Notification"
    ) {
        return;
    }

    frappe.model.with_doctype(frm.doc.document_type, () => {

        const fields = frappe.get_meta(frm.doc.document_type).fields;

        let options = ["", "owner"];

        fields.forEach(df => {

            if (
                df.fieldtype === "Link" &&
                df.options === "User"
            ) {
                options.push(df.fieldname);
            }
        });

        frm.fields_dict.recipients.grid.update_docfield_property(
            "receiver_by_document_field",
            "options",
            options
        );

        frm.refresh_field("recipients");

    });

};