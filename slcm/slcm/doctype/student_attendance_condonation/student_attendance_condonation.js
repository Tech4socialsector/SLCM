// Copyright (c) 2026, Nishanth and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Attendance Condonation", {
	refresh(frm) {
		fix_private_file_link(frm, "proof_document");
	},
	proof_document(frm) {
		fix_private_file_link(frm, "proof_document");
	}
});

function fix_private_file_link(frm, fieldname) {
	const file_url = frm.doc[fieldname];
	if (!file_url || !file_url.startsWith("/private/")) return;

	const download_url = `/api/method/frappe.utils.file_manager.download_file?file_url=${encodeURIComponent(file_url)}`;
	frm.fields_dict[fieldname].$wrapper.find("a").attr("href", download_url);
}
