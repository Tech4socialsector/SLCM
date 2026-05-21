import frappe
from frappe.utils import today, add_days, now_datetime
from datetime import date


def mark_overdue_demands():
	"""Daily job: mark all past-due Fee Demands as Overdue."""
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
		_append_payment_log(
			student=d.student,
			event_type="Status Changed",
			from_status=d.status,
			to_status="Overdue",
			remarks="Auto-marked overdue by scheduler",
			demand=d.name,
		)

	if demands:
		frappe.db.commit()
		frappe.logger().info(f"[fee.scheduler] Marked {len(demands)} demands as Overdue")


def send_due_reminders():
	"""Daily job: send due reminders at T-7, T-1, and T+3 days."""
	today_date = date.fromisoformat(today())

	reminder_configs = [
		{
			"offset": 7,
			"flag": "reminder_1_sent",
			"subject": "Fee Due Reminder — {fee_head} due in 7 days",
			"template": "fee_reminder_7_days",
		},
		{
			"offset": 1,
			"flag": "reminder_2_sent",
			"subject": "Final Reminder — {fee_head} due tomorrow",
			"template": "fee_reminder_1_day",
		},
		{
			"offset": -3,
			"flag": "overdue_notice_sent",
			"subject": "Overdue Notice — {fee_head} is now overdue",
			"template": "fee_overdue_notice",
		},
	]

	for config in reminder_configs:
		target_date = add_days(today(), -config["offset"])  # negative offset = past
		flag = config["flag"]

		demands = frappe.get_all(
			"Fee Demand",
			filters={
				"due_date": target_date,
				flag: 0,
				"status": ["not in", ["Paid", "Waived", "Cancelled"]],
			},
			fields=["name", "student", "fee_component", "outstanding_amount", "due_date", flag],
		)

		for d in demands:
			_send_fee_reminder(d, config)
			frappe.db.set_value("Fee Demand", d.name, flag, 1)

	frappe.db.commit()


def check_phd_year_transition():
	"""Daily job: create correct annual demand for PhD students based on year of study."""
	from frappe.utils import date_diff, getdate

	phd_students = frappe.get_all(
		"Student Master",
		filters={"program_type": "PhD", "status": "Active"},
		fields=["name", "admission_date", "programme", "program", "current_academic_year"],
	)

	current_year = frappe.get_value(
		"Academic Year", {"is_default": 1}, "name"
	)

	for student in phd_students:
		if not student.admission_date:
			continue

		years_elapsed = date_diff(today(), student.admission_date) // 365
		year_of_study = int(years_elapsed) + 1

		if year_of_study <= 3:
			component_type = "Annual Fee (PhD)"
		else:
			component_type = "Continuation Fee (PhD)"

		existing = frappe.db.exists(
			"Fee Demand",
			{
				"student": student.name,
				"demand_type": "Academic",
				"academic_year": current_year,
				"fee_component": ["like", f"%{component_type}%"],
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
			"phd_year_from": ["<=", year_of_study],
			"phd_year_to": [">=", year_of_study],
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
		"programme": student.programme,
		"program": student.program,
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
		return

	subject = config["subject"].format(fee_head=demand.fee_component)
	frappe.sendmail(
		recipients=[student_email],
		subject=subject,
		message=f"""
			<p>Dear Student,</p>
			<p>This is a reminder regarding your pending fee: <strong>{demand.fee_component}</strong></p>
			<p>Outstanding Amount: <strong>₹{demand.outstanding_amount:,.2f}</strong></p>
			<p>Due Date: <strong>{demand.due_date}</strong></p>
			<p>Please log in to the student portal to view and pay your dues.</p>
			<p>Regards,<br>Finance & Accounts Office</p>
		""",
		now=True,
	)


def _append_payment_log(student, event_type, from_status=None, to_status=None,
						remarks=None, demand=None, amount=None):
	try:
		frappe.get_doc({
			"doctype": "Student Fee Payment Log",
			"student": student,
			"event_type": event_type,
			"timestamp": now_datetime(),
			"from_status": from_status,
			"to_status": to_status,
			"remarks": remarks,
			"invoice": demand,
			"amount": amount,
			"triggered_by": frappe.session.user,
		}).insert(ignore_permissions=True)
	except Exception:
		pass
