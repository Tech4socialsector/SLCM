# Copyright (c) 2026, Administrator and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from slcm.slcm.fee.fee_demand_utils import create_event_demand
from slcm.slcm.fee.event_hooks import _cancel_demand_for_trigger


class FineImposition(Document):
	def validate(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date."))

	@frappe.whitelist()
	def apply_fine(self):
		if self.status == "Applied":
			frappe.throw(_("This Fine Imposition has already been applied."))

		demands = self._get_outstanding_demands()
		if not demands:
			frappe.msgprint(_("No outstanding Fee Demands matched the selection criteria."))
			return {"total_demands_affected": 0, "total_fine_amount": 0}

		total_fine_amount = 0
		self.fine_log = []

		for demand in demands:
			fine_amount = self._compute_fine_amount(demand.outstanding_amount)
			if fine_amount <= 0:
				continue

			fine_demand_name = create_event_demand(
				student=demand.student,
				fee_component_name=self.fee_component,
				amount=fine_amount,
				demand_type="Fine",
				due_days=self.due_days,
				trigger_doctype="Fine Imposition",
				trigger_name=self.name,
				description=_("Fine for outstanding demand {0}").format(demand.name),
				academic_year=demand.academic_year,
			)

			self.append("fine_log", {
				"student": demand.student,
				"source_fee_demand": demand.name,
				"outstanding_amount": demand.outstanding_amount,
				"fine_amount": fine_amount,
				"fine_demand": fine_demand_name,
			})
			total_fine_amount += fine_amount

		self.status = "Applied"
		self.applied_on = now_datetime()
		self.applied_by = frappe.session.user
		self.total_demands_affected = len(self.fine_log)
		self.total_fine_amount = total_fine_amount
		self.save(ignore_permissions=True)

		return {
			"total_demands_affected": self.total_demands_affected,
			"total_fine_amount": self.total_fine_amount,
		}

	@frappe.whitelist()
	def reverse_fine(self):
		if self.status != "Applied":
			frappe.throw(_("Only an Applied Fine Imposition can be reversed."))

		_cancel_demand_for_trigger("Fine Imposition", self.name)

		self.status = "Reversed"
		self.reversed_on = now_datetime()
		self.reversed_by = frappe.session.user
		self.save(ignore_permissions=True)

		return {"status": self.status}

	def _compute_fine_amount(self, outstanding_amount):
		if self.fine_type == "Flat Amount":
			amount = flt(self.flat_amount)
		else:
			amount = flt(outstanding_amount) * flt(self.percentage) / 100

		if flt(self.max_fine_amount) > 0:
			amount = min(amount, flt(self.max_fine_amount))

		return flt(amount)

	def _get_outstanding_demands(self):
		filters = {
			"outstanding_amount": [">", 0],
			"status": ["not in", ["Paid", "Cancelled", "Waived"]],
			"demand_type": ["!=", "Fine"],
			"due_date": ["between", [self.from_date, self.to_date]],
		}
		if self.demand_type_filter:
			filters["demand_type"] = self.demand_type_filter
		if self.programme:
			filters["program"] = self.programme
		if self.academic_year:
			filters["academic_year"] = self.academic_year
		if flt(self.min_outstanding_amount) > 0:
			filters["outstanding_amount"] = [">=", flt(self.min_outstanding_amount)]

		return frappe.get_all(
			"Fee Demand",
			filters=filters,
			fields=["name", "student", "academic_year", "outstanding_amount"],
		)
