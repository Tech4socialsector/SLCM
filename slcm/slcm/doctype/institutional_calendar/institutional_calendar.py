# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InstitutionalCalendar(Document):
	def validate(self):
		if self.end_date < self.start_date:
			frappe.throw(_("End Date cannot be before Start Date"))


ENTRY_COLORS = {
	"Holiday": "#e74c3c",
	"Exam": "#9b59b6",
	"Semester Start": "#2ecc71",
	"Semester End": "#2ecc71",
	"Event": "#f39c12",
	"Orientation": "#1abc9c",
	"Other": "#95a5a6",
}


def get_calendar_entries(start, end):
	"""Institutional Calendar entries (holidays, exams, events, ...) overlapping
	the given date range, for use by other doctypes' calendar views."""
	return frappe.db.sql(
		"""
		SELECT name, name1, entry_type, start_date, end_date
		FROM `tabInstitutional Calendar`
		WHERE start_date <= %(end)s AND end_date >= %(start)s
		AND status != 'Inactive'
		AND docstatus < 2
		""",
		{"start": start, "end": end},
		as_dict=True,
	)


@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Merge core Event calendar events with Institutional Calendar entries,
	so holidays/exams/etc. show up on the Event Calendar view too."""
	from datetime import timedelta

	from frappe.desk.doctype.event.event import get_events as get_core_events

	events = get_core_events(start, end, filters=filters) or []

	from frappe.utils import getdate

	for entry in get_calendar_entries(getdate(start), getdate(end)):
		color = ENTRY_COLORS.get(entry.entry_type, "#95a5a6")
		events.append({
			"name": f"ic-{entry.name}",
			"subject": f"{entry.entry_type}: {entry.name1}",
			"starts_on": str(entry.start_date),
			"ends_on": str(entry.end_date + timedelta(days=1)),
			"all_day": 1,
			"event_type": "Public",
			"color": color,
			"backgroundColor": color,
			"borderColor": color,
			"textColor": "#ffffff",
			"editable": False,
			"extendedProps": {
				"institutional_calendar": entry.name,
				"entry_type": entry.entry_type,
			},
		})

	return events
