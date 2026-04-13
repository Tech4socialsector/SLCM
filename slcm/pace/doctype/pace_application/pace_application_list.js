frappe.listview_settings['PACE Application'] = {
    onload: function(listview) {
        // Original ZIP Actions
        listview.page.add_actions_menu_item(__('Download All Attachments (ZIP)'), function() {
            const selected_items = listview.get_checked_items();
            if (selected_items.length === 0) {
                frappe.msgprint(__('Please select at least one record to download.'));
                return;
            }
            const names = selected_items.map(item => item.name);
            frappe.show_alert({ message: __('Preparing Attachments...'), indicator: 'blue' });
            frappe.call({
                method: 'slcm.pace.doctype.pace_application.pace_application.bulk_download_attachments',
                args: { names: names },
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
                        frappe.show_alert({ message: __('Download started.'), indicator: 'green' });
                    }
                }
            });
        });
    }
};
