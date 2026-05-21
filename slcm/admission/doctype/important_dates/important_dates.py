# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class ImportantDates(Document):
	pass


def update_important_dates_status():
	"""
	Scheduler event to update `is_active` status of 'Important Dates' documents.
	Sets `is_active` to 0 if the date is in the past, or 1 if it is today or in the future.
	"""
	current_today = getdate(today())
	
	important_dates = frappe.get_all("Important Dates", fields=["name", "date", "is_active"])
	for doc in important_dates:
		if not doc.date:
			continue
		
		doc_date = getdate(doc.date)
		is_active = 1 if doc_date >= current_today else 0
		
		if doc.is_active != is_active:
			frappe.db.set_value("Important Dates", doc.name, "is_active", is_active)
	
	frappe.db.commit()
