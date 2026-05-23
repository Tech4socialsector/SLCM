import frappe
from frappe.model.document import Document
from frappe.utils import flt, today, add_days

CONVOCATION_FEES = {
	"In-Person": 1500.0,
	"In-Absentia": 2000.0,
}


class ConvocationRegistration(Document):

	def validate(self):
		self._set_amount()

	def on_submit(self):
		demand_name = self._create_convocation_demand()
		if demand_name:
			self.db_set("convocation_fee_demand", demand_name)

	def on_cancel(self):
		if self.convocation_fee_demand:
			_cancel_demand(self.convocation_fee_demand)
			self.db_set("convocation_fee_demand", None)

	def _set_amount(self):
		if not self.convocation_type:
			return

		fee_component = frappe.get_value(
			"Fee Component", {"component_type": "Convocation Fee"}, ["name", "amount"], as_dict=True
		)
		if fee_component and flt(fee_component.amount) > 0:
			base = flt(fee_component.amount)
			if self.convocation_type == "In-Absentia":
				self.amount = base + 500
			else:
				self.amount = base
		else:
			self.amount = CONVOCATION_FEES.get(self.convocation_type, 1500.0)

	def _create_convocation_demand(self):
		fee_component = frappe.get_value(
			"Fee Component", {"component_type": "Convocation Fee"}, "name"
		)
		if not fee_component:
			frappe.log_error(
				"Fee Component with type 'Convocation Fee' not found. "
				"Please create one and re-submit.",
				"ConvocationRegistration"
			)
			frappe.throw(
				"Fee Component 'Convocation Fee' not found. "
				"Create a Fee Component with type 'Convocation Fee' first."
			)

		amount = flt(self.amount) or CONVOCATION_FEES.get(self.convocation_type, 1500.0)

		doc = frappe.get_doc({
			"doctype": "Fee Demand",
			"student": self.student,
			"academic_year": self.academic_year,
			"demand_type": "Examination",
			"fee_component": fee_component,
			"description": f"Convocation Fee — {self.convocation_type} ({self.convocation_year})",
			"demand_date": today(),
			"due_date": add_days(today(), 30),
			"original_amount": amount,
			"trigger_ref_doctype": "Convocation Registration",
			"trigger_ref_name": self.name,
		})
		doc.insert(ignore_permissions=True)
		return doc.name


def _cancel_demand(demand_name):
	demand = frappe.get_doc("Fee Demand", demand_name)
	if demand.status not in ("Paid", "Cancelled"):
		if flt(demand.paid_amount) > 0:
			frappe.log_error(
				f"Cannot cancel demand {demand_name} — partial payment exists.",
				"ConvocationRegistration"
			)
			return
		demand.status = "Cancelled"
		demand.save(ignore_permissions=True)
