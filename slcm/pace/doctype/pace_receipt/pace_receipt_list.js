frappe.listview_settings['PACE Receipt'] = {
	onload: function (listview) {
		frappe.realtime.on('bulk_pace_receipt_download_progress', (data) => {
			frappe.show_progress(data.title, data.progress[0], 100, data.description);
		});

		frappe.realtime.on('bulk_download_complete', (data) => {
			if (data.doctype === 'PACE Receipt') {
				frappe.hide_progress();
				if (data.file_url) {
					window.open(data.file_url);
				}
			}
		});

		listview.page.add_inner_button(__('Bulk Download'), function () {
			let dialog = new frappe.ui.Dialog({
				title: __('Bulk download PACE payment receipts'),
				fields: [
					{
						label: __('Programme'),
						fieldname: 'program',
						fieldtype: 'Link',
						options: 'PACE Programme',
					},
					{
						label: __('Fee Type'),
						fieldname: 'fee_type',
						fieldtype: 'Select',
						options: '\nApplication Fee\nAdmission Fee',
					},
					{
						label: __('From Payment Date'),
						fieldname: 'from_date',
						fieldtype: 'Date',
					},
					{
						label: __('To Payment Date'),
						fieldname: 'to_date',
						fieldtype: 'Date',
					},
					{
						label: __('Output Format'),
						fieldname: 'output_format',
						fieldtype: 'Select',
						options: 'ZIP Archive\nSingle Merged PDF',
						default: 'ZIP Archive',
					},
				],
				primary_action_label: __('Download'),
				primary_action: function (values) {
					dialog.hide();
					frappe.call({
						method: 'slcm.pace.doctype.pace_receipt.pace_receipt.get_bulk_pace_receipts_zip',
						args: { filters: values },
						callback: function (r) {
							if (!r.message) {
								return;
							}
							if (typeof r.message === 'string') {
								frappe.hide_progress();
								let w = window.open(r.message, '_blank');
								if (!w) {
									frappe.msgprint(__('Please allow popups to download the file.'));
								}
							} else if (r.message.status === 'enqueued') {
								frappe.msgprint({
									title: __('Background job started'),
									message: r.message.message,
									indicator: 'blue',
								});
							}
						},
					});
				},
			});
			dialog.show();
		});
	},
};
