frappe.listview_settings['Refund Transaction'] = {
	refresh: function(listview) {
		this.add_download_button(listview);
	},
	add_download_button: function(listview) {
		// Guard: check via DOM to avoid duplicate buttons (get_inner_button doesn't exist in Frappe 16)
		if (listview.page.inner_toolbar.find(`button:contains('${__('Download Receipts')}')`).length) {
			return;
		}

		console.log("Adding Download Receipts button to inner page");
		listview.page.add_inner_button(__('Download Receipts'), function() {
			const dialog = new frappe.ui.Dialog({
				title: __('Download Bulk Receipts'),
				fields: [
					{
						label: __('Admission Cycle'),
						fieldname: 'admission_cycle',
						fieldtype: 'Link',
						options: 'Admission Cycle',
						reqd: 1
					},
					{
						label: __('Status'),
						fieldname: 'status',
						fieldtype: 'Select',
						options: '\nInitiated\nPending\nProcessed\nFailed'
					}
				],
				primary_action_label: __('Download'),
				primary_action(values) {
					dialog.hide();
					frappe.dom.freeze(__('Generating receipts, please wait...'));
					
					frappe.call({
						method: 'slcm.admission.doctype.refund_transaction.refund_transaction.bulk_download_receipts_by_filter',
						args: {
							admission_cycle: values.admission_cycle,
							status: values.status
						},
						callback: function(r) {
							frappe.dom.unfreeze();
							if (r.message && r.message.file_url) {
								const link = document.createElement('a');
								link.href = r.message.file_url;
								link.download = r.message.file_name;
								document.body.appendChild(link);
								link.click();
								document.body.removeChild(link);
								
								frappe.show_alert({
									message: __('Receipts generated successfully: {0} files.').replace('{0}', r.message.count),
									indicator: 'green'
								});
							} else {
								frappe.msgprint(__('No receipts found for the selected criteria.'));
							}
						},
						error: function() {
							frappe.dom.unfreeze();
						}
					});
				}
			});

			dialog.show();
		});
	}
};
