import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RevaluationRequest(Document):
	def validate(self):
		self.total_fee = flt(self.number_of_papers) * flt(self.fee_per_paper)

	def on_submit(self):
		from slcm.slcm.fee.event_hooks import on_revaluation_request_submit
		on_revaluation_request_submit(self)

	def on_cancel(self):
		from slcm.slcm.fee.event_hooks import on_revaluation_request_cancel
		on_revaluation_request_cancel(self)
