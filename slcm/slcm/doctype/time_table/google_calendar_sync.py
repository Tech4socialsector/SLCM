# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_datetime


def get_active_google_calendar_account():
	"""Return the name of the Google Calendar account to push Time Table entries to.

	SLCM syncs every Time Table entry into a single shared Google Calendar
	account (the first enabled one with push turned on) rather than mapping
	per-instructor calendars.
	"""
	return frappe.db.get_value(
		"Google Calendar", {"enable": 1, "push_to_google_calendar": 1}, "name"
	)


def build_event_fields(doc):
	subject = doc.title or doc.course or "Class"
	if doc.venue:
		subject = f"{subject} ({doc.venue})"

	return {
		"subject": subject,
		"starts_on": get_datetime(f"{doc.schedule_date} {doc.from_time}"),
		"ends_on": get_datetime(f"{doc.schedule_date} {doc.to_time}"),
	}


def sync_time_table_to_google_calendar(doc, method=None):
	"""Create/update a linked Event so this Time Table entry pushes to Google
	Calendar via Frappe's existing Event -> Google Calendar sync hooks."""
	if not (doc.schedule_date and doc.from_time and doc.to_time):
		return

	account = get_active_google_calendar_account()
	if not account:
		return

	try:
		event_fields = build_event_fields(doc)

		if doc.linked_google_event and frappe.db.exists("Event", doc.linked_google_event):
			event = frappe.get_doc("Event", doc.linked_google_event)
			event.update(event_fields)
			event.save(ignore_permissions=True)
		else:
			event = frappe.get_doc(
				{
					"doctype": "Event",
					"event_type": "Private",
					"sync_with_google_calendar": 1,
					"google_calendar": account,
					"description": f"Synced from Time Table: {doc.name}",
					**event_fields,
				}
			)
			event.insert(ignore_permissions=True)
			frappe.db.set_value(
				"Time Table", doc.name, "linked_google_event", event.name, update_modified=False
			)
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(), title="Time Table Google Calendar Sync Failed"
		)


def _get_student_for_session_user():
	user = frappe.session.user
	name = (
		frappe.db.get_value("Student Master", {"user": user}, "name")
		or frappe.db.get_value("Student Master", {"email": user}, "name")
		or frappe.db.get_value("Student Master", {"official_email_id": user}, "name")
	)
	if not name:
		frappe.throw("No student record found for your account.")
	return frappe.get_doc("Student Master", name)


def _get_or_create_contact_for_email(email, full_name=None):
	existing = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	if existing:
		return existing

	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": full_name or email.split("@")[0],
			"email_ids": [{"email_id": email, "is_primary": 1}],
		}
	)
	contact.insert(ignore_permissions=True)
	return contact.name


def _get_enrolled_course_offerings(student_name):
	rows = frappe.get_all(
		"Attendance Summary",
		filters={"student": student_name},
		fields=["course_offering"],
		ignore_permissions=True,
	)
	return {r.course_offering for r in rows if r.course_offering}


@frappe.whitelist()
def sync_student_calendar(email):
	"""Add the requesting student as a Google Calendar attendee on every
	upcoming class in their timetable, using whichever email (personal or
	official) they choose. No per-student Google OAuth is needed — invites
	are sent from the single already-authorized Google Calendar account,
	so this scales to any number of students."""
	student = _get_student_for_session_user()

	allowed_emails = {
		e for e in [student.email, student.official_email_id, student.personal_email] if e
	}
	if email not in allowed_emails:
		frappe.throw("You can only sync using your own registered email address.")

	if not get_active_google_calendar_account():
		frappe.throw("Google Calendar sync is not configured yet. Contact the administrator.")

	full_name = " ".join(filter(None, [student.first_name, student.last_name]))
	contact_name = _get_or_create_contact_for_email(email, full_name)

	course_offerings = _get_enrolled_course_offerings(student.name)
	if not course_offerings:
		return {"synced": 0, "failed": 0, "message": "No enrolled courses found."}

	today = frappe.utils.getdate()
	schedule_names = frappe.get_all(
		"Time Table",
		filters=[
			["course_offering", "in", list(course_offerings)],
			["schedule_date", ">=", str(today)],
			["docstatus", "<", 2],
		],
		pluck="name",
		limit_page_length=0,
	)

	synced, failed = 0, 0
	for tt_name in schedule_names:
		try:
			tt = frappe.get_doc("Time Table", tt_name)

			if not tt.linked_google_event:
				sync_time_table_to_google_calendar(tt)
				tt.reload()

			if not tt.linked_google_event:
				failed += 1
				continue

			event = frappe.get_doc("Event", tt.linked_google_event)
			already_added = any(
				p.reference_doctype == "Contact" and p.reference_docname == contact_name
				for p in event.event_participants
			)
			if not already_added:
				event.add_participant("Contact", contact_name)
				event.set_participants_email()
				event.save(ignore_permissions=True)
			synced += 1
		except Exception:
			failed += 1
			frappe.log_error(message=frappe.get_traceback(), title="Student Calendar Sync Failed")

	return {"synced": synced, "failed": failed}


def delete_linked_google_event(doc, method=None):
	"""Remove the linked Event (and its Google Calendar entry) when the Time
	Table entry is deleted."""
	if not doc.linked_google_event or not frappe.db.exists("Event", doc.linked_google_event):
		return

	try:
		frappe.delete_doc("Event", doc.linked_google_event, ignore_permissions=True, force=True)
	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(), title="Time Table Google Calendar Event Deletion Failed"
		)
