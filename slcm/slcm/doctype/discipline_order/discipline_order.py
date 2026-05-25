import frappe
from frappe.model.document import Document


class DisciplineOrder(Document):
	def on_submit(self):
		from slcm.slcm.fee.event_hooks import on_discipline_order_submit
		on_discipline_order_submit(self)

	def on_cancel(self):
		from slcm.slcm.fee.event_hooks import on_discipline_order_cancel
		on_discipline_order_cancel(self)
