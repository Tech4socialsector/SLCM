import frappe
from frappe import _
from frappe.utils import get_datetime


def execute(filters=None):
    filters = filters or {}
    validate_filters(filters)
    columns = get_columns()
    data, summary = get_data(filters)
    return columns, data, None, None, summary


def validate_filters(filters):
    if not filters.get("from_datetime"):
        frappe.throw(_("Please select From Date & Time."))
    if not filters.get("to_datetime"):
        frappe.throw(_("To Date & Time is required."))
    if get_datetime(filters["from_datetime"]) >= get_datetime(filters["to_datetime"]):
        frappe.throw(_("To Date & Time must be after From Date & Time."))


def get_columns():
    return [
        {
            "fieldname": "availability",
            "label": _("Availability"),
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "fieldname": "room",
            "label": _("Room"),
            "fieldtype": "Link",
            "options": "Room",
            "width": 160,
        },
        {
            "fieldname": "room_name",
            "label": _("Room Name"),
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "fieldname": "venue_type",
            "label": _("Venue Type"),
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "fieldname": "seating_capacity",
            "label": _("Capacity"),
            "fieldtype": "Int",
            "width": 90,
        },
        {
            "fieldname": "floor",
            "label": _("Floor"),
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "fieldname": "booked_by",
            "label": _("Booked By"),
            "fieldtype": "Data",
            "width": 160,
        },
        {
            "fieldname": "booking_ref",
            "label": _("Booking Ref"),
            "fieldtype": "Link",
            "options": "Venue Booking",
            "width": 150,
        },
        {
            "fieldname": "booking_status",
            "label": _("Booking Status"),
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "fieldname": "event_name",
            "label": _("Event / Purpose"),
            "fieldtype": "Data",
            "width": 180,
        },
    ]


def get_data(filters):
    from_dt = get_datetime(filters["from_datetime"])
    to_dt   = get_datetime(filters["to_datetime"])

    room_filters = {"is_booking_allowed": 1}
    if filters.get("venue_type"):
        room_filters["room_type"] = filters["venue_type"]
    if filters.get("room"):
        room_filters["name"] = filters["room"]
    if filters.get("block"):
        room_filters["block"] = filters["block"]
    if filters.get("min_capacity"):
        room_filters["seating_capacity"] = [">=", int(filters["min_capacity"])]
    if filters.get("floor"):
        room_filters["floor"] = ["like", "%{0}%".format(filters["floor"])]
    if filters.get("facilities"):
        room_filters["facilities"] = ["like", "%{0}%".format(filters["facilities"])]

    rooms = frappe.get_all(
        "Room",
        filters=room_filters,
        fields=["name", "room_name", "room_type", "seating_capacity", "floor"],
        order_by="room_type, room_name",
    )

    # Fetch all overlapping approved/pending bookings for the time window
    overlapping = frappe.db.sql("""
        SELECT
            room, name, event_name, requester_name, status,
            start_datetime, end_datetime
        FROM `tabVenue Booking`
        WHERE
            status IN ('Allotted', 'Pending Allotment')
            AND start_datetime < %(to_dt)s
            AND end_datetime   > %(from_dt)s
    """, {"from_dt": from_dt, "to_dt": to_dt}, as_dict=True)

    booked_map = {}
    for bk in overlapping:
        booked_map.setdefault(bk.room, []).append(bk)

    data = []
    available_count = 0
    booked_count = 0

    for room in rooms:
        conflicts = booked_map.get(room.name, [])
        if conflicts:
            booked_count += 1
            for bk in conflicts:
                data.append({
                    "availability":    "Booked",
                    "room":            room.name,
                    "room_name":       room.room_name or room.name,
                    "venue_type":      room.room_type or "",
                    "seating_capacity": room.seating_capacity or 0,
                    "floor":           room.floor or "",
                    "booked_by":       bk.requester_name or "",
                    "booking_ref":     bk.name,
                    "booking_status":  bk.status,
                    "event_name":      bk.event_name or "",
                })
        else:
            available_count += 1
            data.append({
                "availability":    "Available",
                "room":            room.name,
                "room_name":       room.room_name or room.name,
                "venue_type":      room.room_type or "",
                "seating_capacity": room.seating_capacity or 0,
                "floor":           room.floor or "",
                "booked_by":       "",
                "booking_ref":     "",
                "booking_status":  "",
                "event_name":      "",
            })

    if filters.get("booked_by"):
        booked_by = filters["booked_by"].lower()
        data = [
            r for r in data
            if r["availability"] == "Booked" and booked_by in (r["booked_by"] or "").lower()
        ]

    if filters.get("availability_status"):
        data = [r for r in data if r["availability"] == filters["availability_status"]]

    if filters.get("booked_by") or filters.get("availability_status"):
        available_count = sum(1 for r in data if r["availability"] == "Available")
        booked_count = len({r["room"] for r in data if r["availability"] == "Booked"})

    # Sort: Available first, then Booked
    data.sort(key=lambda r: (0 if r["availability"] == "Available" else 1, r["venue_type"], r["room_name"]))

    summary = [
        {"label": _("Total Rooms Checked"), "value": len(rooms),        "indicator": "Blue"},
        {"label": _("Available"),           "value": available_count,   "indicator": "Green"},
        {"label": _("Booked / Conflict"),   "value": booked_count,      "indicator": "Red"},
    ]

    return data, summary
