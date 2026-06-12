import frappe

def execute():
	"""Migrate existing PACE Applicant Fee Assignment and PACE Receipt records from 'Admission Fee' to 'Course Fee'."""
	# Check if PACE Applicant Fee Assignment DocType exists
	if frappe.db.exists("DocType", "PACE Applicant Fee Assignment"):
		frappe.db.sql("""
			UPDATE `tabPACE Applicant Fee Assignment`
			SET fee_type = 'Course Fee'
			WHERE fee_type = 'Admission Fee'
		""")

	# Check if PACE Receipt DocType exists
	if frappe.db.exists("DocType", "PACE Receipt"):
		frappe.db.sql("""
			UPDATE `tabPACE Receipt`
			SET fee_type = 'Course Fee'
			WHERE fee_type = 'Admission Fee'
		""")

	frappe.db.commit()
