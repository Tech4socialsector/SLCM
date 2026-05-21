frappe.ui.form.on("Shortlisting Merit List", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Run Shortlisting Merit List Logic"), function () {
                frappe.call({
                    method: "execute_shortlisting_logic",
                    doc: frm.doc,
                    freeze: true,
                    callback: function () {
                        frm.reload_doc();
                        frappe.show_alert(__("Shortlisting Merit List logic executed successfully."));
                    }
                });
            }, __("Actions"));

            frm.add_custom_button(__("Generate Final Admission Merit"), function () {
                frappe.confirm(__("This will generate the final Merit List (Entrance + Interview). Continue?"), function () {
                    frappe.call({
                        method: "generate_final_merit_list",
                        doc: frm.doc,
                        freeze: true,
                        callback: function (r) {
                            if (r.message) {
                                frappe.show_alert(__("Final Merit List generated: " + r.message));
                                frappe.set_route("Form", "Merit List", r.message);
                            }
                        }
                    });
                });
            }, __("Actions"));

            frm.add_custom_button(__("Download Merit List"), function () {
                let d = new frappe.ui.Dialog({
                    title: __('Download Shortlisting Merit List'),
                    fields: [
                        {
                            label: __('Download Type'),
                            fieldname: 'download_type',
                            fieldtype: 'Select',
                            options: [
                                { label: __('Overall Master List'), value: 'Overall' },
                                { label: __('Category Wise'), value: 'Category Wise' }
                            ],
                            default: 'Overall',
                            reqd: 1
                        },
                        {
                            label: __('Specific Category'),
                            fieldname: 'category',
                            fieldtype: 'Select',
                            options: [
                                { label: __('All Categories'), value: 'All' },
                                { label: __('General List'), value: 'General' },
                                { label: __('SC List'), value: 'SC' },
                                { label: __('ST List'), value: 'ST' },
                                { label: __('OBC List'), value: 'OBC' },
                                { label: __('EWS List'), value: 'EWS' },
                                { label: __('Karnataka Students'), value: 'Karnataka' },
                                { label: __('Women Merit List'), value: 'Women' },
                                { label: __('PWD Merit List'), value: 'PWD' }
                            ],
                            depends_on: "eval:doc.download_type == 'Category Wise'",
                            default: 'All'
                        }
                    ],
                    primary_action_label: __('Download'),
                    primary_action(values) {
                        let url = frappe.urllib.get_full_url(
                            "/api/method/slcm.admission.doctype.shortlisting_merit_list.shortlisting_merit_list.download_merit_list?" +
                            "name=" + encodeURIComponent(frm.doc.name) +
                            "&download_type=" + encodeURIComponent(values.download_type) +
                            "&category=" + encodeURIComponent(values.category || "")
                        );
                        window.open(url, '_blank');
                        d.hide();
                    }
                });
                d.show();
            }, __("Actions"));
        }
    }
});
