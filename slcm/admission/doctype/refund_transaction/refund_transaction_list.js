frappe.listview_settings['Refund Transaction'] = {
	refresh: function(listview) {
		this.add_download_button(listview);
	},
	add_download_button: function(listview) {
		// Guard: avoid duplicate buttons
		if (listview.page.inner_toolbar.find(`button:contains('${__('Download Receipts')}')`).length) {
			return;
		}

		listview.page.add_inner_button(__('Download Receipts'), function() {
			const filter_dialog = new frappe.ui.Dialog({
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
					filter_dialog.hide();
					start_bulk_download(values);
				}
			});

			filter_dialog.show();
		});
	}
};

// ─────────────────────────────────────────────────────────────────────────────
// Bulk download — runs in background, shows live progress, no screen freeze
// ─────────────────────────────────────────────────────────────────────────────

function start_bulk_download(values) {

	// ── 1. Build progress dialog ─────────────────────────────────────
	const progress_dialog = new frappe.ui.Dialog({
		title: __('Generating Receipts'),
	});

	progress_dialog.$body.html(`
		<div style="padding: 8px 0 4px;">
			<p id="bulk-dl-message"
			   style="margin-bottom:12px; font-weight:500; font-size:13px;">
				${__('Queuing background job…')}
			</p>
			<div style="background:#e9ecef; border-radius:8px; overflow:hidden; height:20px;">
				<div id="bulk-dl-bar"
				     style="height:100%; width:0%;
				            background:linear-gradient(90deg,#2d8f6f,#4CAF50);
				            transition:width 0.4s ease;
				            border-radius:8px;">
				</div>
			</div>
			<p id="bulk-dl-pct"
			   style="text-align:right; margin-top:6px; font-size:12px; color:#6c757d;">
				0%
			</p>
			<p id="bulk-dl-note"
			   style="margin-top:8px; font-size:11px; color:#888; text-align:center;">
				${__('You can continue using the app while receipts are being generated.')}
			</p>
		</div>
	`);

	// Hide the submit footer — user closes dialog via the ✕ button if needed
	progress_dialog.footer.hide();
	progress_dialog.show();

	// ── 2. Helpers ───────────────────────────────────────────────────

	function set_progress(done, total, msg) {
		const pct = total > 0 ? Math.round((done / total) * 100) : 0;
		progress_dialog.$body.find('#bulk-dl-bar').css('width', pct + '%');
		progress_dialog.$body.find('#bulk-dl-pct').text(pct + '%');
		if (msg) progress_dialog.$body.find('#bulk-dl-message').text(msg);
	}

	function cleanup() {
		frappe.realtime.off('bulk_download_progress');
		frappe.realtime.off('bulk_download_complete');
	}

	// ── 3. Listen for realtime events from the background worker ─────

	frappe.realtime.on('bulk_download_progress', function(data) {
		if (data.doctype !== 'Refund Transaction') return;
		set_progress(data.progress, data.total, data.message);
	});

	frappe.realtime.on('bulk_download_complete', function(data) {
		if (data.doctype !== 'Refund Transaction') return;
		cleanup();
		progress_dialog.hide();

		if (data.error) {
			frappe.msgprint({ title: __('Error'), message: data.error, indicator: 'red' });
			return;
		}

		// Trigger browser file download
		const link = document.createElement('a');
		link.href  = data.file_url;
		link.download = data.file_name || 'Refund_Receipts.zip';
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);

		frappe.show_alert({
			message: __('Done! {0} receipt(s) downloaded.').replace('{0}', data.count),
			indicator: 'green'
		}, 6);
	});

	// ── 4. Fire the backend call (returns immediately — just enqueues) ─

	frappe.call({
		method: 'slcm.admission.doctype.refund_transaction.refund_transaction.bulk_download_receipts_by_filter',
		args: {
			admission_cycle: values.admission_cycle,
			status: values.status || ''
		},
		callback: function(r) {
			const msg = r && r.message;

			if (!msg || msg.status === 'NoRecords') {
				// No matching transactions — clean up immediately
				cleanup();
				progress_dialog.hide();
				frappe.msgprint(__('No receipts found for the selected criteria.'));
				return;
			}

			if (msg.status === 'Started') {
				// Backend has queued the job; update label with total count
				set_progress(
					0,
					msg.count || 1,
					__('Processing {0} receipt(s) in background…').replace('{0}', msg.count || '?')
				);
			}
		},
		error: function() {
			cleanup();
			progress_dialog.hide();
			frappe.show_alert({ message: __('Error starting download job.'), indicator: 'red' });
		}
	});
}
