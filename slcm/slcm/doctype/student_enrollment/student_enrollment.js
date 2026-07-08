frappe.ui.form.on("Student Enrollment", {
	refresh(frm) {
		// Add quick links to related records
		if (!frm.is_new() && frm.doc.student) {
			frm.set_df_property("html_links", "options", get_quick_links_html(frm));
		}
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

		// 4️⃣ Fetch Program curriculum then match each course to a Course Offering
		frappe.db.get_doc("Programme", frm.doc.program).then((program_doc) => {
			if (!program_doc.table_fela || program_doc.table_fela.length === 0) {
				frm.refresh_field("enrolled_courses");
				return;
			}

			const courses = program_doc.table_fela.map(pc => pc.course).filter(Boolean);

			frappe.db.get_list("Course Offering", {
				filters: [["cohort", "=", cohort], ["course_title", "in", courses]],
				fields: ["name", "course_title", "course_name"],
			}).then((offerings) => {
				const offering_map = {};
				offerings.forEach(o => { offering_map[o.course_title] = o.name; });

				program_doc.table_fela.forEach((pc) => {
					const offering = offering_map[pc.course];
					if (!offering) return;
					const row = frm.add_child("enrolled_courses");
					frappe.model.set_value(row.doctype, row.name, "course_offering", offering);
					frappe.model.set_value(row.doctype, row.name, "course_type", pc.course_type || "");
					frappe.model.set_value(row.doctype, row.name, "status", "Enrolled");
				});

				frm.refresh_field("enrolled_courses");
			});
		});
	},
});

function get_quick_links_html(frm) {
	const student = frm.doc.student;
	const enrollment = frm.doc.name;

	return `
		<div style="padding: 10px;">
			<h6>Quick Links</h6>
			<div style="display: flex; gap: 10px; flex-wrap: wrap;">
				<button class="btn btn-sm btn-default" onclick="frappe.set_route('List', 'Student Attendance', {'student': '${student}'})">
					View Attendance
				</button>
				<button class="btn btn-sm btn-default" onclick="frappe.set_route('List', 'Student Fee Assignment', {'student': '${student}'})">
					View Fees
				</button>
				<button class="btn btn-sm btn-default" onclick="frappe.set_route('List', 'Course Schedule', {'student_group': '${
					frm.doc.cohort || ""
				}'})">
					View Schedule
				</button>
			</div>
		</div>
	`;
}
