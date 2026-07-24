# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InstitutionalCalendar(Document):
	def validate(self):
		if self.end_date < self.start_date:
			frappe.throw(_("End Date cannot be before Start Date"))
		if self.entry_type == "Weekly Off" and not self.weekly_off_days:
			frappe.throw(_("Please select at least one Weekly Off Day"))


ENTRY_COLORS = {
	"Holiday": "#e74c3c",
	"Exam": "#9b59b6",
	"Semester Start": "#2ecc71",
	"Semester End": "#2ecc71",
	"Event": "#f39c12",
	"Orientation": "#1abc9c",
	"Weekly Off": "#c0392b",
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


def get_non_teaching_reason(check_date):
	"""Single source of truth for "is this date teachable?".

	Returns a dict {reason, entry_type, name1, name} if `check_date` is a
	Holiday or falls on a configured Weekly Off day (per an Institutional
	Calendar "Weekly Off" entry covering that date), else None.

	Any code that schedules or validates a Time Table entry — or any other
	doctype that needs to know whether a date is a working day — should call
	this instead of re-querying Institutional Calendar directly, so holiday
	and weekly-off rules only ever need to change in one place.
	"""
	from frappe.utils import getdate

	check_date = getdate(check_date)
	weekday_name = check_date.strftime("%A")

	holiday = frappe.db.get_value(
		"Institutional Calendar",
		{
			"entry_type": "Holiday",
			"start_date": ["<=", check_date],
			"end_date": [">=", check_date],
			"status": ["!=", "Inactive"],
			"docstatus": ["<", 2],
		},
		["name", "name1"],
		as_dict=True,
	)
	if holiday:
		return {"reason": "Holiday", "entry_type": "Holiday", "name1": holiday.name1, "name": holiday.name}

	weekly_off_entries = frappe.get_all(
		"Institutional Calendar",
		filters={
			"entry_type": "Weekly Off",
			"start_date": ["<=", check_date],
			"end_date": [">=", check_date],
			"status": ["!=", "Inactive"],
			"docstatus": ["<", 2],
		},
		fields=["name", "name1"],
	)
	for entry in weekly_off_entries:
		days = frappe.get_all(
			"Institutional Calendar Weekly Off Day",
			filters={"parent": entry.name, "parenttype": "Institutional Calendar"},
			pluck="day",
		)
		if weekday_name in days:
			return {
				"reason": f"Weekly Off ({weekday_name})",
				"entry_type": "Weekly Off",
				"name1": entry.name1,
				"name": entry.name,
			}

	return None


def is_teaching_day(check_date):
	"""True if `check_date` is neither a Holiday nor a configured Weekly Off day."""
	return get_non_teaching_reason(check_date) is None


def get_non_teaching_dates_in_range(start_date, end_date):
	"""Batched version of get_non_teaching_reason for a whole date range.

	Returns {date: reason_string} for every date between start_date and
	end_date (inclusive) that is a Holiday or a configured Weekly Off day.
	Runs a small constant number of queries regardless of range length, so
	callers generating recurring schedules over months/years don't pay one
	query per day.
	"""
	from datetime import timedelta

	from frappe.utils import getdate

	start_date = getdate(start_date)
	end_date = getdate(end_date)
	non_teaching = {}

	holidays = frappe.get_all(
		"Institutional Calendar",
		filters={
			"entry_type": "Holiday",
			"start_date": ["<=", end_date],
			"end_date": [">=", start_date],
			"status": ["!=", "Inactive"],
			"docstatus": ["<", 2],
		},
		fields=["name1", "start_date", "end_date"],
	)
	for holiday in holidays:
		day = max(holiday.start_date, start_date)
		last = min(holiday.end_date, end_date)
		while day <= last:
			non_teaching.setdefault(day, f"Holiday ({holiday.name1})")
			day += timedelta(days=1)

	weekly_off_entries = frappe.get_all(
		"Institutional Calendar",
		filters={
			"entry_type": "Weekly Off",
			"start_date": ["<=", end_date],
			"end_date": [">=", start_date],
			"status": ["!=", "Inactive"],
			"docstatus": ["<", 2],
		},
		fields=["name", "name1", "start_date", "end_date"],
	)
	if weekly_off_entries:
		days_by_entry = {}
		entry_names = [e.name for e in weekly_off_entries]
		rows = frappe.get_all(
			"Institutional Calendar Weekly Off Day",
			filters={"parent": ["in", entry_names], "parenttype": "Institutional Calendar"},
			fields=["parent", "day"],
		)
		for row in rows:
			days_by_entry.setdefault(row.parent, set()).add(row.day)

		for entry in weekly_off_entries:
			off_days = days_by_entry.get(entry.name, set())
			if not off_days:
				continue
			day = max(entry.start_date, start_date)
			last = min(entry.end_date, end_date)
			while day <= last:
				if day.strftime("%A") in off_days:
					non_teaching.setdefault(day, f"Weekly Off ({day.strftime('%A')})")
				day += timedelta(days=1)

	return non_teaching
