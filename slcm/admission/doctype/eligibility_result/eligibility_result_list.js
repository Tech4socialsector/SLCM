frappe.listview_settings['Eligibility Result'] = {
    onload: function(listview) {
        // Add to the 'Actions' menu that appears when records are selected
        listview.page.add_actions_menu_item(__('Download Result'), function() {
            const selected_items = listview.get_checked_items();
            
            if (selected_items.length === 0) {
                frappe.msgprint(__('Please select at least one record to download.'));
                return;
            }

            const names = selected_items.map(item => item.name);
            
            // Show a progress indicator for bulk generation
            frappe.show_alert({
                message: __('Preparing Eligibility Cards...'),
                indicator: 'blue'
            });

            frappe.call({
                method: 'slcm.admission.doctype.eligibility_result.eligibility_result.bulk_download_cards',
                args: {
                    names: names
                },
                freeze: true,
                freeze_message: __('Generating ZIP Archive...'),
                callback: function(r) {
                    if (r.message) {
                        const file_url = r.message;
                        const link = document.createElement('a');
                        link.href = file_url;
                        link.download = file_url.split('/').pop();
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        
                        frappe.show_alert({
                            message: __('Download started successfully.'),
                            indicator: 'green'
                        });
                    }
                }
            });
        });
    }
};
