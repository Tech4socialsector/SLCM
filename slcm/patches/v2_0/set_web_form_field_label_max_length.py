import frappe


def execute():
	frappe.make_property_setter({
		"doctype": "Web Form Field",
		"fieldname": "label",
		"property": "length",
		"value": "1000",
		"property_type": "Int"
	})
