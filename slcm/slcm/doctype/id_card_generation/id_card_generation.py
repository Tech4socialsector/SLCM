import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname

from slcm.slcm.utils.id_card_shared import IDCardCommonMixin


class IDCardGeneration(IDCardCommonMixin, Document):
	_print_log_linkfield = "id_card_generation"

	def autoname(self):
		series_map = {
			"Student": "STU-.#####",
			"Faculty": "FAC-.#####",
			"Driver": "DRV-.#####",
			"Visitor": "VIS-.#####",
			"Non-Faculty": "STF-.#####",
		}
		self.naming_series = series_map.get(self.card_type, "IDC-.#####")
		self.name = make_autoname(self.naming_series)

	# ------------------------------------------------------------------
	# Post-insert background generation
	# ------------------------------------------------------------------

	def after_insert(self):
		frappe.enqueue(
			"slcm.slcm.doctype.id_card_generation.tasks.generate_id_card_images",
			queue="short",
			docname=self.name,
		)


@frappe.whitelist()
def create_or_update_template(template_data):
	"""Create or update an ID Card Template from a JS template definition."""
	if isinstance(template_data, str):
		data = json.loads(template_data)
	else:
		data = template_data

	template_name = data.get("template_name")
	if not template_name:
		frappe.throw(_("Template Name is missing."))

	if not frappe.db.exists("ID Card Template", {"template_name": template_name}):
		doc = frappe.new_doc("ID Card Template")
		doc.template_name = template_name
	else:
		existing = frappe.db.get_value("ID Card Template", {"template_name": template_name}, "name")
		doc = frappe.get_doc("ID Card Template", existing)

	doc.template_creation_mode = "Jinja Template"
	doc.front_html = data.get("front_template_html")
	doc.back_html = data.get("back_template_html")
	doc.card_size = data.get("card_size")
	doc.orientation = data.get("orientation")

	doc.save(ignore_permissions=True)
	return doc.name
