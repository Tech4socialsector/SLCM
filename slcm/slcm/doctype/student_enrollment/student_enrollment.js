frappe.ui.form.on("Student Enrollment", {
	refresh(frm) {
		// Lightweight only - just keep the Section link filtered to this
		// batch. The auto-fill of enrolled_courses must NOT re-run here,
		// otherwise simply opening an existing enrollment would wipe out
		// any manually edited rows (grades, status, faculty overrides).
		frm.set_query("section", function () {
			return { filters: { batch: frm.doc.batch } };
		});

		// Only students who have completed the registration workflow
		// should be selectable for enrollment.
		frm.set_query("student", function () {
			return { filters: { registration_status: "Completed" } };
		});

		if (frm.is_new() || !frm.doc.student) return;

		frappe.call({
			method: "slcm.slcm.doctype.student_enrollment.student_enrollment.get_other_terms",
			args: { student: frm.doc.student, exclude: frm.doc.name },
			callback(r) {
				const terms = r.message || [];
				terms.forEach((term) => {
					const label = `${term.academic_year || "—"} · ${term.term_name || "—"} (${term.status})`;
					frm.add_custom_button(label, () => {
						frappe.set_route("Form", "Student Enrollment", term.name);
					}, __("Other Terms"));
				});
			},
		});
	},

	batch(frm) {
		// Fires on real user-driven changes only (not on load), which is
		// exactly when we want to refill enrolled_courses for the new batch.
		frm.set_query("section", function () {
			return { filters: { batch: frm.doc.batch } };
		});

		// 1️⃣ Clear table if batch removed
		if (!frm.doc.batch) {
			frm.set_value("section", "");
			frm.clear_table("enrolled_courses");
			frm.refresh_field("enrolled_courses");
			return;
		}

		// 2️⃣ Clear existing rows before refilling
		frm.clear_table("enrolled_courses");

		const batch = frm.doc.batch;

		// 3️⃣ Fetch all Open Course Offerings for this batch directly
		frappe.db.get_list("Course Offering", {
			filters: [["batch", "=", batch], ["status", "=", "Open"]],
			fields: ["name", "course_title"],
		}).then((offerings) => {
			if (!offerings.length) {
				frm.refresh_field("enrolled_courses");
				return;
			}

			frappe.db.get_list("Course", {
				filters: [["name", "in", offerings.map(o => o.course_title)]],
				fields: ["name", "course_type"],
			}).then((courses) => {
				const course_type_map = {};
				courses.forEach(c => { course_type_map[c.name] = c.course_type; });

				offerings.forEach((offering) => {
					const row = frm.add_child("enrolled_courses");
					frappe.model.set_value(row.doctype, row.name, "course_offering", offering.name);
					frappe.model.set_value(row.doctype, row.name, "course", offering.course_title);
					frappe.model.set_value(row.doctype, row.name, "course_type", course_type_map[offering.course_title] || "");
					frappe.model.set_value(row.doctype, row.name, "status", "Enrolled");
				});

				frm.refresh_field("enrolled_courses");
			});
		});
	},
});
