import frappe
from frappe.utils import today, add_days, now_datetime, getdate


def mark_overdue_demands():
	"""Daily: mark all past-due Fee Demands as Overdue."""
	demands = frappe.get_all(
		"Fee Demand",
		filters={
			"status": ["in", ["Pending", "Partially Paid"]],
			"due_date": ["<", today()],
		},
		fields=["name", "student", "status"],
	)

	for d in demands:
		frappe.db.set_value("Fee Demand", d.name, "status", "Overdue")

	if demands:
		frappe.db.commit()
		frappe.logger().info(f"[fee.scheduler] Marked {len(demands)} demands as Overdue")


def send_due_reminders():
	"""Daily: send reminder emails at T-7, T-1, and T+3 (overdue notice)."""

	reminder_configs = [
		{
			"offset": 7,   # due_date = today + 7  → "due in 7 days"
			"flag": "reminder_1_sent",
			"subject": "Fee Due Reminder — {fee_head} due in 7 days",
		},
		{
			"offset": 1,   # due_date = today + 1  → "due tomorrow"
			"flag": "reminder_2_sent",
			"subject": "Final Reminder — {fee_head} due tomorrow",
		},
		{
			"offset": -3,  # due_date = today - 3  → "3 days overdue"
			"flag": "overdue_notice_sent",
			"subject": "Overdue Notice — {fee_head} is now overdue",
		},
	]

	for config in reminder_configs:
		target_date = add_days(today(), config["offset"])
		flag = config["flag"]

		demands = frappe.get_all(
			"Fee Demand",
			filters={
				"due_date": target_date,
				flag: 0,
				"status": ["not in", ["Paid", "Waived", "Cancelled"]],
			},
			fields=["name", "student", "fee_component", "outstanding_amount", "due_date"],
		)

		for d in demands:
			_send_fee_reminder(d, config)
			frappe.db.set_value("Fee Demand", d.name, flag, 1)

	frappe.db.commit()


def check_phd_year_transition():
	"""Daily: create correct annual demand for PhD students based on year of study."""
	from frappe.utils import date_diff

	phd_students = frappe.get_all(
		"Student Master",
		filters={"program_type": "PhD", "student_status": "Active"},
		fields=["name", "admission_date", "programme", "academic_year"],
	)

	current_year = frappe.get_value("Academic Year", {"is_default": 1}, "name")

	for student in phd_students:
		if not student.admission_date:
			continue

		years_elapsed = date_diff(today(), student.admission_date) // 365
		year_of_study = int(years_elapsed) + 1

		component_type = "Annual Fee (PhD)" if year_of_study <= 3 else "Continuation Fee (PhD)"

		existing = frappe.db.exists(
			"Fee Demand",
			{
				"student": student.name,
				"demand_type": "Academic",
				"academic_year": current_year,
				"fee_component": ["like", f"%PhD%"],
				"status": ["!=", "Cancelled"],
			},
		)

		if not existing:
			_create_phd_demand(student, component_type, year_of_study, current_year)

	frappe.db.commit()


def _create_phd_demand(student, component_type, year_of_study, academic_year):
	fee_component = frappe.get_value(
		"Fee Component", {"component_type": component_type}, "name"
	)
	if not fee_component:
		return

	fee_structure = frappe.get_value(
		"Fee Structure",
		{
			"demand_type": "Academic",
			"program_level": "PhD",
			"academic_year": academic_year,
			"status": "Active",
		},
		["name", "total_amount", "due_offset_days"],
		as_dict=True,
	)
	if not fee_structure:
		return

	due_date = add_days(today(), fee_structure.due_offset_days or 30)

	doc = frappe.get_doc({
		"doctype": "Fee Demand",
		"student": student.name,
		"academic_year": academic_year,
		"demand_type": "Academic",
		"fee_component": fee_component,
		"description": f"{component_type} — Year {year_of_study}",
		"demand_date": today(),
		"due_date": due_date,
		"original_amount": fee_structure.total_amount,
		"trigger_ref_doctype": "Fee Structure",
		"trigger_ref_name": fee_structure.name,
	})
	doc.insert(ignore_permissions=True)


def _send_fee_reminder(demand, config):
	student_email = frappe.get_value("Student Master", demand.student, "student_email_id")
	if not student_email:
		frappe.logger().warning(
			f"[fee.scheduler] No email for student {demand.student}, skipping reminder"
		)
		return

	subject = config["subject"].format(fee_head=demand.fee_component)

	if config["offset"] > 0:
		timing_text = f"due in <strong>{config['offset']} day(s)</strong> on <strong>{demand.due_date}</strong>"
	else:
		timing_text = f"<strong>overdue since {demand.due_date}</strong>"

	frappe.sendmail(
		recipients=[student_email],
		subject=subject,
		message=f"""
			<p>Dear Student,</p>
			<p>This is a reminder regarding your pending fee:</p>
			<table style="border-collapse:collapse; width:100%; max-width:500px;">
				<tr><td style="padding:6px; font-weight:bold;">Fee Head</td><td style="padding:6px;">{demand.fee_component}</td></tr>
				<tr><td style="padding:6px; font-weight:bold;">Outstanding Amount</td><td style="padding:6px;">₹{demand.outstanding_amount:,.2f}</td></tr>
				<tr><td style="padding:6px; font-weight:bold;">Due Date</td><td style="padding:6px;">{demand.due_date}</td></tr>
				<tr><td style="padding:6px; font-weight:bold;">Status</td><td style="padding:6px;">{timing_text}</td></tr>
			</table>
			<br>
			<p>Please log in to the student portal to view and pay your dues.</p>
			<p>If you have already paid, please ignore this message.</p>
			<br>
			<p>Regards,<br><strong>Finance & Accounts Office</strong><br>National Law School of India University</p>
		""",
		now=True,
	)
