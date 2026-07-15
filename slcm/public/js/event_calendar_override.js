// Overlay Institutional Calendar entries (holidays, exams, events, ...) on
// the core Event Calendar view. Runs after event_calendar.js, so it can
// safely override the get_events_method registered there.
frappe.views.calendar["Event"].get_events_method =
    "slcm.slcm.doctype.institutional_calendar.institutional_calendar.get_events";

frappe.views.calendar["Event"].options = Object.assign(
    {},
    frappe.views.calendar["Event"].options,
    {
        eventClick: function (info) {
            // Institutional Calendar markers (holidays, exams, etc.) aren't
            // Event records - clicking them shouldn't navigate anywhere.
            if (info.event.extendedProps && info.event.extendedProps.institutional_calendar) {
                return;
            }
            if (frappe.model.can_read("Event")) {
                frappe.set_route("Form", "Event", info.event.id);
            }
        },
    }
);
