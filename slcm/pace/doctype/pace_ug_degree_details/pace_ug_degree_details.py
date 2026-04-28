# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class PACEUGDegreeDetails(Document):
	def validate(self):
		yp = self.year_of_passing
		if yp is None or yp == "":
			return
		y = cint(yp)
		if y < 1000 or y > 9999:
			frappe.throw(_("Year of Passing must be a 4-digit year (1000–9999)."))
