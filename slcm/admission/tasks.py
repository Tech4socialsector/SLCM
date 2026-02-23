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


def auto_update_cycle_status():
	"""
	Scheduled daily job: Update Admission Cycle status based on dates.
	Upcoming: today < start_date
	Active: start_date <= today <= end_date
	Closed: today > end_date
	"""
	current_today = today()
	
	cycles = frappe.db.get_all(
		"Admission Cycle",
		filters={"docstatus": ["<", 2]},
		fields=["name", "start_date", "end_date", "status", "is_active"]
	)

	updated_count = 0
	for c in cycles:
		new_status = c.status
		new_is_active = c.is_active
		
		# Skip if explicitly closed by admin earlier? 
		# For now, follow the date rules strictly
		
		if getdate(current_today) < getdate(c.start_date):
			new_status = "Upcoming"
			new_is_active = 0
		elif getdate(c.start_date) <= getdate(current_today) <= getdate(c.end_date):
			new_status = "Active"
			new_is_active = 1
		elif getdate(current_today) > getdate(c.end_date):
			new_status = "Closed"
			new_is_active = 0
			
		if new_status != c.status or new_is_active != c.is_active:
			frappe.db.set_value("Admission Cycle", c.name, {
				"status": new_status,
				"is_active": new_is_active
			}, update_modified=False)
			updated_count += 1

	if updated_count:
		frappe.db.commit()
		frappe.log_error(
			title="Auto-Update Admission Cycle Status",
			message="Automatically updated status for {0} Admission Cycle(s)".format(updated_count)
		)
