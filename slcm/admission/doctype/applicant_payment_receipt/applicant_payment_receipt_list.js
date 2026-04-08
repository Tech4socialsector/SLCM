frappe.listview_settings['Applicant Payment Receipt'] = {
	onload: function(listview) {
		// Listen for bulk download progress
		frappe.realtime.on('bulk_receipt_download_progress', (data) => {
			frappe.show_progress(data.title, data.progress[0], 100, data.description);
		});

		// AUTO-DOWNLOAD ON COMPLETION
		frappe.realtime.on("bulk_download_complete", (data) => {
			if (data.doctype === "Applicant Payment Receipt") {
				frappe.hide_progress();
				if (data.file_url) {
					window.open(data.file_url);
				}
			}
		});

		listview.page.add_inner_button(__('Bulk Download ZIP'), function() {
			let dialog = new frappe.ui.Dialog({
				title: __('Bulk Download Fee Receipts'),
				fields: [
					{
						label: __('Programme'),
						fieldname: 'program',
						fieldtype: 'Link',
						options: 'Program'
					},
					{
						label: __('Academic Year'),
						fieldname: 'academic_year',
						fieldtype: 'Link',
						options: 'Academic Year'
					},
					{
						label: __('From Payment Date'),
						fieldname: 'from_date',
						fieldtype: 'Date'
					},
					{
						label: __('To Payment Date'),
						fieldname: 'to_date',
						fieldtype: 'Date'
					},
					{
						label: __('Payment Mode'),
						fieldname: 'payment_mode',
						fieldtype: 'Select',
						options: '\nOnline\nCash\nCheque\nUPI\nQR Code\nBank Transfer\nDemand Draft'
					},
					{
						label: __('Output Format'),
						fieldname: 'output_format',
						fieldtype: 'Select',
						options: 'ZIP Archive\nSingle Merged PDF',
						default: 'ZIP Archive'
					}
				],
				primary_action_label: __('Download'),
				primary_action: function(values) {
					dialog.hide();
					frappe.call({
						method: 'slcm.admission.doctype.applicant_payment_receipt.applicant_payment_receipt.get_bulk_receipts_zip',
						args: {
							filters: values
						},
						callback: function(r) {
							if (r.message) {
								if (typeof r.message === 'string') {
									// Sync response (URL)
									let file_url = r.message;
									let w = window.open(file_url, '_blank');
									if (!w) {
										frappe.msgprint(__('Please allow popups to download the file.'));
									}
								} else if (r.message.status === 'enqueued') {
									frappe.msgprint({
										title: __('Background Job Started'),
										message: r.message.message,
										indicator: 'blue'
									});
								}
							}
						}
					});
				}
			});
			dialog.show();
		});
	}
};
