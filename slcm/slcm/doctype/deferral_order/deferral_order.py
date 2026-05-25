import frappe
from frappe.model.document import Document


class DeferralOrder(Document):
	def on_submit(self):
		from slcm.slcm.fee.event_hooks import on_deferral_order_submit
		on_deferral_order_submit(self)

	def on_cancel(self):
		from slcm.slcm.fee.event_hooks import on_deferral_order_cancel
		on_deferral_order_cancel(self)
