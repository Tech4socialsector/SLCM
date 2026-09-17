const PURPOSE_DEFAULTS = {
	Scholarship: { certificate_mode: "Single Year", include_bank_details: 0 },
	"Bank Loan": { certificate_mode: "Single Year", include_bank_details: 1 },
	"Education Loan": { certificate_mode: "Multi Year", include_bank_details: 1 },
	"Detained Student Fee Structure": { certificate_mode: "Multi Year", include_bank_details: 1 },
};

function fetch_years(frm) {
	if (!frm.doc.student || !frm.doc.from_academic_year) {
		frappe.msgprint(__("Set Student and Academic Year first."));
		return;
	}
	if (frm.doc.certificate_mode === "Multi Year" && !frm.doc.to_academic_year) {
		frappe.msgprint(__("Set To Academic Year first."));
		return;
	}

	frappe.call({
		method: "slcm.slcm.doctype.fee_certificate_request.fee_certificate_request.preview_academic_years",
		args: {
			student: frm.doc.student,
			from_academic_year: frm.doc.from_academic_year,
			to_academic_year: frm.doc.certificate_mode === "Multi Year" ? frm.doc.to_academic_year : null,
		},
		callback(r) {
			const rows = r.message || [];
			frm.clear_table("years");
			rows.forEach((row) => {
				const child = frm.add_child("years");
				child.academic_year = row.academic_year;
				child.year_label = row.year_label;
			});
			frm.refresh_field("years");
		},
	});
}

frappe.ui.form.on("Fee Certificate Request", {
	purpose(frm) {
		const defaults = PURPOSE_DEFAULTS[frm.doc.purpose];
		if (!defaults) return;
		frm.set_value("certificate_mode", defaults.certificate_mode);
		frm.set_value("include_bank_details", defaults.include_bank_details);
	},

	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Fetch Academic Years"), () => fetch_years(frm));

		frm.add_custom_button(__("Preview Certificate"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Save your changes first — the preview reflects the last saved version."));
				return;
			}
			frappe.set_route("print", "Fee Certificate Request", frm.doc.name);
		});

		if (frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Mark as Generated"), () => {
				frappe.call({
					method: "slcm.slcm.doctype.fee_certificate_request.fee_certificate_request.mark_generated",
					args: { name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
