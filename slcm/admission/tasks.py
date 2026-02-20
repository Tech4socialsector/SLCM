import frappe
from frappe.utils import today, getdate


def auto_lock_started_rounds():
	"""
	Scheduled daily job: Lock all Admission Round records where:
	- is_locked = 0
	- start_date <= today
	- status = Active
	"""
	rounds_to_lock = frappe.db.get_all(
		"Admission Round",
		filters={
			"is_locked": 0,
			"start_date": ["<=", today()],
			"status": "Active",
			"docstatus": 1,
		},
		fields=["name"]
	)

	for row in rounds_to_lock:
		frappe.db.set_value("Admission Round", row.name, "is_locked", 1)

	if rounds_to_lock:
		frappe.db.commit()
		frappe.log_error(
			title="Auto-Lock Admission Rounds",
			message="Automatically locked {0} Admission Round(s): {1}".format(
				len(rounds_to_lock),
				[r.name for r in rounds_to_lock]
			)
		)
