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
	
	# Determine nationality type to select the right child table
	nationality = (app.get("nationality") or "").strip().lower()
	nationality_type = "Indian" if nationality in ["indian", "india"] else "Foreign"

	# Find active fee structure for this program
	filters = {
		"pace_program": app.programme,
		"status": "Active"
	}
	if app.academic_year:
		filters["academic_year"] = app.academic_year

	fee_structure_name = frappe.db.get_value("PACE Fee Structure", filters, "name")

	if not fee_structure_name:
		frappe.msgprint(_("Active Fee Structure not found for program {0}. Please create one to generate fee assignment.").format(app.programme))
		return

	fs_doc = frappe.get_doc("PACE Fee Structure", fee_structure_name)

	assignment = frappe.new_doc("PACE Applicant Fee Assignment")
	assignment.applicant = app.name
	assignment.applicant_name = app.applicant_name
	assignment.program = app.programme
	assignment.fee_structure = fs_doc.name
	assignment.currency = fs_doc.currency
	assignment.academic_year = app.academic_year
	assignment.assignment_date = today()
	assignment.status = "Assigned"
	
	if nationality_type == "Indian":
		components = fs_doc.fee_components_for_indians
		total_amount = fs_doc.total_amount
	else:
		components = fs_doc.fee_components_for_foreign
		total_amount = fs_doc.total_amount_for_foreign

	for row in components:
		assignment.append("fee_components", {
			"fee_component": row.fee_component,
			"amount": row.amount,
			"tax_rate": row.tax_rate,
			"tax_amount": row.tax_amount,
			"total_amount": row.total_amount
		})

	assignment.total_amount = total_amount
	assignment.final_payable_amount = total_amount
	
	assignment.insert(ignore_permissions=True)
	# assignment.submit() # Assuming it should be submitted to be 'Assigned'
	
	return assignment.name
