import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

def execute():
	"""Sets the max character length of Web Form Field label to 1000."""
	make_property_setter(
		doctype="Web Form Field",
		fieldname="label",
		property="length",
		value=1000,
		property_type="Int",
		validate_fields_for_doctype=False
	)
	frappe.db.commit()
