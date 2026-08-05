// Copyright (c) 2026, TFSS and contributors

frappe.ui.form.on('Applicant Payment Receipt', {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.name) return;

		frm.add_custom_button(__('Download'), function () {
			const fmt = (frm.doc.payment_receipt_template || '').trim();
			const params = new URLSearchParams({
				doctype: frm.doc.doctype,
				name: frm.doc.name,
			});
			if (fmt) params.set('format', fmt);
			const url =
				frappe.urllib.get_full_url('/api/method/frappe.utils.print_format.download_pdf') +
				'?' +
				params.toString();
			window.open(url, '_blank');
		}).addClass('btn-primary');
	},
});
