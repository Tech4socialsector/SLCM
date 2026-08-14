import frappe
from frappe import _
from frappe.utils import getdate, flt
from datetime import timedelta


def execute(filters=None):
    filters = filters or {}
    validate_filters(filters)
    columns  = get_columns()
    data, summary = get_data(filters)
    chart    = get_chart(data, filters)
    return columns, data, None, chart, summary


# ─────────────────────────────────────────────────────────────────────────────

def validate_filters(filters):
    if not filters.get("week_start"):
        frappe.throw(_("Please select a Week Start Date."))


def get_week_range(filters):
    """Return Monday–Sunday for the week containing week_start."""
    d = getdate(filters["week_start"])
    monday = d - timedelta(days=d.weekday())   # go back to Monday
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_columns():
    return [
        {"fieldname": "day_label",      "label": _("Day"),             "fieldtype": "Data",     "width": 100},
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
    monday, sunday = get_week_range(filters)

    conditions = "WHERE DATE(start_datetime) BETWEEN %(from_date)s AND %(to_date)s"
    params = {"from_date": monday, "to_date": sunday}

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

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    status_counts = {"Pending Allotment": 0, "Allotted": 0, "Rejected": 0, "Cancelled": 0}
    data = []

    for row in rows:
        duration = 0
        if row.start_datetime and row.end_datetime:
            diff = (row.end_datetime - row.start_datetime).total_seconds()
            duration = round(flt(diff) / 3600, 2)

        bk_date = getdate(row.start_datetime)
        day_idx  = bk_date.weekday()   # 0=Mon … 6=Sun
        day_label = day_names[day_idx] + " " + bk_date.strftime("%d %b")

        data.append({
            "day_label":      day_label,
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

    summary = [
        {"label": _("Total Bookings"), "value": len(data),                "indicator": "Blue"},
        {"label": _("Allotted"),       "value": status_counts["Allotted"], "indicator": "Green"},
        {"label": _("Pending Allotment"),        "value": status_counts["Pending Allotment"],  "indicator": "Orange"},
        {"label": _("Rejected"),       "value": status_counts["Rejected"], "indicator": "Red"},
        {"label": _("Cancelled"),      "value": status_counts["Cancelled"],"indicator": "Grey"},
    ]

    return data, summary


def get_chart(data, filters):
    monday, sunday = get_week_range(filters)
    day_names  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # One bucket per day of the week (Mon–Sun)
    buckets = {i: {"Allotted": 0, "Pending Allotment": 0, "Rejected": 0, "Cancelled": 0} for i in range(7)}

    for row in data:
        if row["start_datetime"]:
            idx = getdate(row["start_datetime"]).weekday()
            s   = row["status"] or "Pending Allotment"
            if s in buckets[idx]:
                buckets[idx][s] += 1

    # Labels: "Mon 12 May" style
    labels = []
    for i in range(7):
        d = monday + timedelta(days=i)
        labels.append(day_names[i] + " " + d.strftime("%d %b"))

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Allotted"),  "values": [buckets[i]["Allotted"]  for i in range(7)], "chartType": "bar"},
                {"name": _("Pending Allotment"),   "values": [buckets[i]["Pending Allotment"]   for i in range(7)], "chartType": "bar"},
                {"name": _("Rejected"),  "values": [buckets[i]["Rejected"]  for i in range(7)], "chartType": "bar"},
                {"name": _("Cancelled"), "values": [buckets[i]["Cancelled"] for i in range(7)], "chartType": "bar"},
            ],
        },
        "type": "bar",
        "colors": ["#22c55e", "#f59e0b", "#ef4444", "#9ca3af"],
        "barOptions": {"stacked": True},
    }
