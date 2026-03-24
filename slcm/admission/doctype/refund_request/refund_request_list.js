frappe.listview_settings['Refund Request'] = {
	onload: function(listview) {
		listview.page.add_action_item(__('Bulk Process Refunds'), function() {
			const selected = listview.get_checked_items();
			if (!selected.length) return;

			// Filter only 'Approved' requests
			const to_process = selected.filter(d => d.status === 'Approved').map(d => d.name);
			const not_approved = selected.filter(d => d.status !== 'Approved').map(d => d.name);

			if (!to_process.length) {
				frappe.msgprint(__('Only "Approved" refund requests can be processed. Please select valid records.'));
				return;
			}

			let confirm_msg = __('Are you sure you want to process {0} selected refunds via Razorpay?', [to_process.length]);
			if (not_approved.length > 0) {
				confirm_msg += '<br><br><small class="text-muted">' + __('Note: {0} selected records will be skipped as they are not "Approved".', [not_approved.length]) + '</small>';
			}

			frappe.confirm(confirm_msg, function() {
				frappe.call({
					method: 'slcm.admission_cancel_api.process_bulk_refunds',
					args: { names: to_process },
					callback: function(r) {
						if (r.message) {
							show_bulk_results_dialog(r.message);
							listview.refresh();
						}
					}
				});
			});
		});
	}
};

function show_bulk_results_dialog(results) {
	let success = results.filter(res => res.status === 'Success').length;
	let failed = results.filter(res => res.status === 'Error').length;
	
	let detail_html = `<div style="max-height: 300px; overflow-y: auto; margin-top: 15px;">
		<table class="table table-bordered table-sm" style="font-size: 12px;">
			<thead><tr><th>ID</th><th>Status</th><th>Result</th></tr></thead>
			<tbody>`;
	
	results.forEach(res => {
		let icon = res.status === 'Success' ? '🟢' : '🔴';
		detail_html += `<tr>
			<td><strong>${res.name}</strong></td>
			<td>${icon} ${res.status}</td>
			<td class="text-muted"><small>${res.message || ''}</small></td>
		</tr>`;
	});
	
	detail_html += `</tbody></table></div>`;

	frappe.msgprint({
		title: __('Bulk Refund Summary'),
		message: `
			<div class="text-center mb-3">
				<div class="d-inline-block p-3 rounded" style="background: #f0fdf4; margin-right: 15px;">
					<div style="font-size: 24px; font-weight: 800; color: #16a34a;">${success}</div>
					<div style="font-size: 11px; font-weight: 700; color: #15803d; text-transform: uppercase;">Success</div>
				</div>
				<div class="d-inline-block p-3 rounded" style="background: #fef2f2;">
					<div style="font-size: 24px; font-weight: 800; color: #dc2626;">${failed}</div>
					<div style="font-size: 11px; font-weight: 700; color: #991b1b; text-transform: uppercase;">Failed</div>
				</div>
			</div>
			${detail_html}
		`,
		indicator: failed > 0 ? 'orange' : 'green',
		wide: true
	});
}
