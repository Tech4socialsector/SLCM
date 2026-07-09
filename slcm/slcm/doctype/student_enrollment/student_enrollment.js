frappe.ui.form.on("Student Enrollment", {
	refresh(frm) {
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

	program(frm) {
		// 1️⃣ Clear table if program removed
		if (!frm.doc.program) {
			frm.clear_table("enrolled_courses");
			frm.refresh_field("enrolled_courses");
			return;
		}

		// 2️⃣ Clear existing rows
		frm.clear_table("enrolled_courses");

		// 3️⃣ Need cohort to find Course Offerings
		const cohort = frm.doc.cohort;
		if (!cohort) {
			frappe.msgprint("Please select a Cohort first before the courses can be auto-filled.");
			frm.refresh_field("enrolled_courses");
			return;
		}

		// 4️⃣ Fetch all Open Course Offerings for this cohort/batch directly
		frappe.db.get_list("Course Offering", {
			filters: [["cohort", "=", cohort], ["status", "=", "Open"]],
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
