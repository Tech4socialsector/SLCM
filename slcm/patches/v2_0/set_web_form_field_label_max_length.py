import frappe


def execute():
	frappe.db.sql("ALTER TABLE `tabWeb Form Field` MODIFY `label` TEXT")
	
	frappe.make_property_setter({
		"doctype": "Web Form Field",
		"fieldname": "label",
		"property": "length",
		"value": "1000",
		"property_type": "Int"
	})
	
	frappe.clear_cache(doctype="Web Form Field")
