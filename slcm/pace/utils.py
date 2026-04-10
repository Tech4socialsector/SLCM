import frappe
from frappe import _
from frappe.utils import flt, today

def create_pace_fee_assignment(application_name):
	"""
	Creates a PACE Applicant Fee Assignment record from a verified PACE Application.
	"""
	if frappe.db.exists("PACE Applicant Fee Assignment", {"applicant": application_name, "status": ["!=", "Cancelled"]}):
		return

	app = frappe.get_doc("PACE Application", application_name)
	
	# Determine nationality type for fee structure selection
	# PACE Application has 'nationality' field which seems to be a Data field
	# PACE Fee Structure has 'nationality_type' as 'Indian' or 'Foreign'
	nationality = (app.get("nationality") or "").strip().lower()
	nationality_type = "Indian" if nationality in ["indian", "india"] else "Foreign"

	# Find active fee structure for this program and nationality
	fee_structure_name = frappe.db.get_value("PACE Fee Structure", {
		"pace_program": app.programme,
		"nationality_type": nationality_type,
		"status": "Active"
	}, "name")

	if not fee_structure_name:
		frappe.msgprint(_("Active Fee Structure not found for program {0} and nationality {1}. Please create one to generate fee assignment.").format(app.programme, nationality_type))
		return

	fs_doc = frappe.get_doc("PACE Fee Structure", fee_structure_name)

	assignment = frappe.new_doc("PACE Applicant Fee Assignment")
	assignment.applicant = app.name
	assignment.applicant_name = app.applicant_name
	assignment.program = app.programme
	assignment.fee_structure = fs_doc.name
	assignment.currency = fs_doc.currency
	assignment.assignment_date = today()
	assignment.status = "Assigned"
	
	for row in fs_doc.fee_components:
		assignment.append("fee_components", {
			"fee_component": row.fee_component,
			"amount": row.amount,
			"tax_rate": row.tax_rate,
			"tax_amount": row.tax_amount,
			"total_amount": row.total_amount
		})

	assignment.total_amount = fs_doc.total_amount
	assignment.final_payable_amount = fs_doc.total_amount
	
	assignment.insert(ignore_permissions=True)
	# assignment.submit() # Assuming it should be submitted to be 'Assigned'
	
	return assignment.name
