"""
Validate the "Preferred Visit Date/Time" fields students fill in on Facilities
tickets raised from the Student Portal (see helpdesk's HD Ticket Template for
the "Facilities" category, and the custom_preferred_visit_date/time fields on
HD Ticket).

Rules (values configurable on HD Settings > Ticket Settings > Facility Visit
Scheduling — see hd_settings_custom_fields.json in the helpdesk app):
  - The requested slot must fall within facility_visit_window_hours of now
    (default 24h) — students can't book a visit far in the future.
  - The requested time must fall within [facility_visit_hours_start,
    facility_visit_hours_end] (default 09:00-20:00).

Runs on HD Ticket's validate (after core's own validate), so it only ever
sees a ticket that has already been through set_ticket_type etc.
"""

import frappe
from frappe import _
from frappe.utils import (
    add_to_date,
    get_datetime,
    get_time,
    now_datetime,
)

FACILITY_TICKET_TYPE = "Facilities"

DEFAULT_VISIT_HOURS_START = "09:00:00"
DEFAULT_VISIT_HOURS_END = "20:00:00"
DEFAULT_VISIT_WINDOW_HOURS = 24


def validate_preferred_visit_slot(doc, method=None):
    """Hook: HD Ticket validate."""
    if doc.get("ticket_type") != FACILITY_TICKET_TYPE:
        return

    visit_date = doc.get("custom_preferred_visit_date")
    visit_time = doc.get("custom_preferred_visit_time")

    if not visit_date or not visit_time:
        frappe.throw(
            _("Preferred Visit Date and Time are mandatory for Facilities tickets.")
        )

    visit_datetime = get_datetime(f"{visit_date} {visit_time}")

    _validate_within_booking_window(visit_datetime)
    _validate_within_working_hours(visit_time)


def _get_settings():
    return frappe.get_cached_value(
        "HD Settings",
        "HD Settings",
        [
            "facility_visit_hours_start",
            "facility_visit_hours_end",
            "facility_visit_window_hours",
        ],
        as_dict=True,
    ) or {}


def _validate_within_booking_window(visit_datetime):
    settings = _get_settings()
    window_hours = settings.get("facility_visit_window_hours") or DEFAULT_VISIT_WINDOW_HOURS

    now = now_datetime()
    earliest = now
    latest = add_to_date(now, hours=window_hours)

    if visit_datetime < earliest or visit_datetime > latest:
        frappe.throw(
            _(
                "Preferred Visit Date/Time must be within the next {0} hours "
                "from now."
            ).format(window_hours)
        )


def _validate_within_working_hours(visit_time):
    settings = _get_settings()
    start = get_time(settings.get("facility_visit_hours_start") or DEFAULT_VISIT_HOURS_START)
    end = get_time(settings.get("facility_visit_hours_end") or DEFAULT_VISIT_HOURS_END)
    requested = get_time(visit_time)

    if requested < start or requested > end:
        frappe.throw(
            _(
                "Preferred Visit Time must be between {0} and {1}."
            ).format(start.strftime("%I:%M %p"), end.strftime("%I:%M %p"))
        )
