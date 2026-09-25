const METHOD_BASE = "slcm.slcm.doctype.fee_certificate_request.fee_certificate_request";

function load_purpose_options(frm) {
	frappe.call({
		method: "slcm.slcm.doctype.fee_certificate_settings.fee_certificate_settings.get_purpose_options",
		callback(r) {
			frm._purpose_options = r.message || [];
			frm.set_df_property(
				"purpose",
				"options",
				frm._purpose_options.map((o) => o.purpose)
			);
		},
	});
}

function fetch_years(frm) {
	if (!frm.doc.student || !frm.doc.from_academic_year || !frm.doc.purpose) {
		frappe.msgprint(__("Set Student, Purpose and Academic Year first."));
		return;
	}

	frappe.call({
		method: `${METHOD_BASE}.preview_academic_years`,
		args: {
			student: frm.doc.student,
			from_academic_year: frm.doc.from_academic_year,
			purpose: frm.doc.purpose,
		},
		callback(r) {
			frm.clear_table("years");
			(r.message || []).forEach((row) => {
				const child = frm.add_child("years");
				child.academic_year = row.academic_year;
				child.year_label = row.year_label;
				child.programme_year = row.programme_year;
			});
			frm.refresh_field("years");
		},
	});
}

function download_certificate(frm) {
	const params = new URLSearchParams({
		doctype: frm.doc.doctype,
		name: frm.doc.name,
		format: "Fee Certificate",
		no_letterhead: 1,
	});
	window.open(`/api/method/frappe.utils.print_format.download_pdf?${params.toString()}`);
}

frappe.ui.form.on("Fee Certificate Request", {
	setup(frm) {
		load_purpose_options(frm);
	},

	purpose(frm) {
		const option = (frm._purpose_options || []).find((o) => o.purpose === frm.doc.purpose);
		if (!option) return;
		frm.set_value("certificate_type", option.certificate_type);
		frm.set_value("include_bank_details", option.include_bank_details);
		if (frm.doc.student && frm.doc.from_academic_year) fetch_years(frm);
	},

	from_academic_year(frm) {
		if (frm.doc.student && frm.doc.purpose && frm.doc.from_academic_year) fetch_years(frm);
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
			frm.add_custom_button(__("Download Certificate"), () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save your changes first — the certificate reflects the last saved version."));
					return;
				}
				download_certificate(frm);
				if (frm.doc.status !== "Generated") {
					frappe.call({
						method: `${METHOD_BASE}.mark_generated`,
						args: { name: frm.doc.name },
						callback: () => frm.reload_doc(),
					});
				}
			}).addClass("btn-primary");

			frm.add_custom_button(__("Mark as Generated"), () => {
				frappe.call({
					method: `${METHOD_BASE}.mark_generated`,
					args: { name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
