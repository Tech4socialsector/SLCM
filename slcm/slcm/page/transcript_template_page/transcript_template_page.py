# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def get_templates(search=""):
	"""Return all Transcript Templates for the list view."""
	filters = {}
	or_filters = None
	if search:
		or_filters = {
			"template_name": ("like", f"%{search}%"),
			"template_type":  ("like", f"%{search}%"),
		}

	templates = frappe.get_all(
		"Transcript Template",
		fields=[
			"name",
			"template_name",
			"template_type",
			"page_size",
			"orientation",
			"is_default",
			"institute_logo",
			"institute_name",
			"modified",
			"modified_by",
		],
		filters=filters,
		or_filters=or_filters,
		order_by="is_default desc, modified desc",
		limit=200,
	)

	return {"templates": templates}


@frappe.whitelist()
def get_template(name):
	"""Return a single template's full data."""
	if not frappe.db.exists("Transcript Template", name):
		frappe.throw(frappe._("Template '{0}' not found.").format(name))

	doc = frappe.get_doc("Transcript Template", name)
	return doc.as_dict()


@frappe.whitelist()
def save_template(data):
	"""Create or update a Transcript Template document."""
	import json
	if isinstance(data, str):
		data = json.loads(data)

	name = data.get("name") or data.get("template_name", "").strip()
	if not name:
		frappe.throw(frappe._("Template Name is required."))

	if frappe.db.exists("Transcript Template", name):
		doc = frappe.get_doc("Transcript Template", name)
		doc.update(data)
		doc.save(ignore_permissions=False)
	else:
		doc = frappe.new_doc("Transcript Template")
		doc.update(data)
		doc.insert(ignore_permissions=False)

	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_template(name):
	"""Delete a Transcript Template. System templates cannot be deleted."""
	if not frappe.db.exists("Transcript Template", name):
		frappe.throw(frappe._("Template '{0}' not found.").format(name))

	ttype = frappe.db.get_value("Transcript Template", name, "template_type")
	if ttype == "System":
		frappe.throw(frappe._("System templates cannot be deleted."))

	frappe.delete_doc("Transcript Template", name, ignore_permissions=False)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def set_default(name):
	"""Mark a template as the default; clears the flag on all others."""
	if not frappe.db.exists("Transcript Template", name):
		frappe.throw(frappe._("Template '{0}' not found.").format(name))

	# Clear existing default
	frappe.db.set_value(
		"Transcript Template",
		{"is_default": 1},
		"is_default",
		0,
	)
	frappe.db.set_value("Transcript Template", name, "is_default", 1)
	frappe.db.commit()
	return {"success": True, "default": name}


@frappe.whitelist()
def seed_default_templates():
	"""
	Insert the two built-in system templates if they don't already exist.
	Safe to call multiple times (idempotent).
	"""
	defaults = [
		{
			"template_name":       "Default Transcript Template",
			"template_type":       "System",
			"page_size":           "A4",
			"orientation":         "Portrait",
			"is_default":          1,
			"show_institute_logo": 1,
			"logo_alignment":      "Center",
			"logo_width":          120,
			"show_institute_address": 1,
			"header_title":        "OFFICIAL TRANSCRIPT OF ACADEMIC RECORDS",
			"show_student_photo":  1,
			"show_registration_id": 1,
			"show_cgpa":           1,
			"show_credits":        1,
			"show_semester_wise":  1,
			"show_watermark":      0,
			"watermark_opacity":   15,
		},
		{
			"template_name":       "Landscape Transcript Template",
			"template_type":       "System",
			"page_size":           "A4",
			"orientation":         "Landscape",
			"is_default":          0,
			"show_institute_logo": 1,
			"logo_alignment":      "Left",
			"logo_width":          100,
			"show_institute_address": 1,
			"header_title":        "TRANSCRIPT OF ACADEMIC RECORDS",
			"show_student_photo":  0,
			"show_registration_id": 1,
			"show_cgpa":           1,
			"show_credits":        1,
			"show_semester_wise":  1,
			"show_watermark":      0,
			"watermark_opacity":   15,
		},
	]

	created = []
	for tmpl in defaults:
		if not frappe.db.exists("Transcript Template", tmpl["template_name"]):
			doc = frappe.new_doc("Transcript Template")
			doc.update(tmpl)
			doc.insert(ignore_permissions=True)
			created.append(tmpl["template_name"])

	if created:
		frappe.db.commit()

	return {"seeded": created}
