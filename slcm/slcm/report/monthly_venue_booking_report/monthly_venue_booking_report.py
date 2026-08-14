import frappe
from frappe import _
from frappe.utils import getdate, get_first_day, get_last_day, flt
from datetime import datetime, timedelta


def execute(filters=None):
    filters = filters or {}
    validate_filters(filters)
    columns = get_columns()
    data, summary = get_data(filters)
    chart  = get_chart(data, filters)
    return columns, data, None, chart, summary


# ─────────────────────────────────────────────────────────────────────────────

def validate_filters(filters):
    if not filters.get("month") or not filters.get("year"):
        frappe.throw(_("Please select both Month and Year."))


def get_date_range(filters):
    month = int(filters["month"])
    year  = int(filters["year"])
    from_date = get_first_day(datetime(year, month, 1).date())
    to_date   = get_last_day(from_date)
    return from_date, to_date


def get_columns():
    return [
        {"fieldname": "name",           "label": _("Booking ID"),      "fieldtype": "Link",     "options": "Venue Booking", "width": 160},
        {"fieldname": "event_name",     "label": _("Event / Purpose"), "fieldtype": "Data",     "width": 180},
        {"fieldname": "room",           "label": _("Room / Venue"),    "fieldtype": "Link",     "options": "Room",          "width": 140},
        {"fieldname": "venue_type",     "label": _("Venue Type"),      "fieldtype": "Data",     "width": 120},
        {"fieldname": "requester_name", "label": _("Requested By"),    "fieldtype": "Data",     "width": 140},
        {"fieldname": "requester_type", "label": _("Role"),            "fieldtype": "Data",     "width": 90},
        {"fieldname": "start_datetime", "label": _("Start"),           "fieldtype": "Datetime", "width": 155},
        {"fieldname": "end_datetime",   "label": _("End"),             "fieldtype": "Datetime", "width": 155},
        {"fieldname": "duration_hrs",   "label": _("Duration (hrs)"),  "fieldtype": "Float",    "width": 110},
        {"fieldname": "status",         "label": _("Status"),          "fieldtype": "Data",     "width": 100},
        {"fieldname": "admin_remarks",  "label": _("Admin Remarks"),   "fieldtype": "Data",     "width": 180},
    ]


def get_data(filters):
    from_date, to_date = get_date_range(filters)

    conditions = "WHERE DATE(start_datetime) BETWEEN %(from_date)s AND %(to_date)s"
    params = {"from_date": from_date, "to_date": to_date}

    if filters.get("status"):
        conditions += " AND status = %(status)s"
        params["status"] = filters["status"]

    if filters.get("requester_type"):
        conditions += " AND requester_type = %(requester_type)s"
        params["requester_type"] = filters["requester_type"]

    if filters.get("room"):
        conditions += " AND room = %(room)s"
        params["room"] = filters["room"]

    rows = frappe.db.sql(f"""
        SELECT
            name, event_name, room, venue_type,
            requester_name, requester_type,
            start_datetime, end_datetime, status,
            admin_remarks
        FROM `tabVenue Booking`
        {conditions}
        ORDER BY start_datetime ASC
    """, params, as_dict=True)

    data = []
    status_counts = {"Pending Allotment": 0, "Allotted": 0, "Rejected": 0, "Cancelled": 0}

    for row in rows:
        duration = 0
        if row.start_datetime and row.end_datetime:
            diff = (row.end_datetime - row.start_datetime).total_seconds()
            duration = round(flt(diff) / 3600, 2)

        data.append({
            "name":           row.name,
            "event_name":     row.event_name or "",
            "room":           row.room or "",
            "venue_type":     row.venue_type or "",
            "requester_name": row.requester_name or "",
            "requester_type": row.requester_type or "",
            "start_datetime": row.start_datetime,
            "end_datetime":   row.end_datetime,
            "duration_hrs":   duration,
            "status":         row.status or "Pending Allotment",
            "admin_remarks":  row.admin_remarks or "",
        })

        s = row.status or "Pending Allotment"
        if s in status_counts:
            status_counts[s] += 1

    # Summary cards
    summary = [
        {"label": _("Total Bookings"), "value": len(data),                       "indicator": "Blue"},
        {"label": _("Allotted"),       "value": status_counts["Allotted"],        "indicator": "Green"},
        {"label": _("Pending Allotment"),        "value": status_counts["Pending Allotment"],         "indicator": "Orange"},
        {"label": _("Rejected"),       "value": status_counts["Rejected"],        "indicator": "Red"},
        {"label": _("Cancelled"),      "value": status_counts["Cancelled"],       "indicator": "Grey"},
    ]

    return data, summary


def get_chart(data, filters):
    from_date, to_date = get_date_range(filters)

    # Build day buckets for the month
    day_map = {}
    current = from_date
    while current <= to_date:
        day_map[current.strftime("%d %b")] = {"Allotted": 0, "Pending Allotment": 0, "Rejected": 0, "Cancelled": 0}
        current += timedelta(days=1)

    for row in data:
        if row["start_datetime"]:
            day_key = getdate(row["start_datetime"]).strftime("%d %b")
            if day_key in day_map:
                s = row["status"] or "Pending Allotment"
                if s in day_map[day_key]:
                    day_map[day_key][s] += 1

    labels  = list(day_map.keys())
    approved  = [day_map[d]["Allotted"]  for d in labels]
    pending   = [day_map[d]["Pending Allotment"]   for d in labels]
    rejected  = [day_map[d]["Rejected"]  for d in labels]
    cancelled = [day_map[d]["Cancelled"] for d in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Allotted"),  "values": approved,  "chartType": "bar"},
                {"name": _("Pending Allotment"),   "values": pending,   "chartType": "bar"},
                {"name": _("Rejected"),  "values": rejected,  "chartType": "bar"},
                {"name": _("Cancelled"), "values": cancelled, "chartType": "bar"},
            ],
        },
        "type": "bar",
        "colors": ["#22c55e", "#f59e0b", "#ef4444", "#9ca3af"],
        "barOptions": {"stacked": True},
    }
