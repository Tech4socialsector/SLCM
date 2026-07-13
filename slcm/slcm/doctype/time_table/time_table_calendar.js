frappe.views.calendar["Time Table"] = {
    field_map: {
        start: "start",
        end: "end",
        id: "name",
        title: "title",
        allDay: "allDay",
        color: "color",
    },
    get_events_method: "slcm.slcm.doctype.time_table.time_table.get_events",
    update_event_method: "slcm.slcm.doctype.time_table.time_table.update_event",
    options: {
        editable: true,
        eventClick: function (info) {
            // Institutional Calendar markers (holidays, exams, etc.) aren't
            // Time Table records - clicking them shouldn't navigate anywhere.
            if (info.event.extendedProps && info.event.extendedProps.institutional_calendar) {
                return;
            }
            if (frappe.model.can_read("Time Table")) {
                frappe.set_route("Form", "Time Table", info.event.id);
            }
        },
        select: function (startDate, endDate, jsEvent, view) {
            // Prevent single day click in month view
            if (view.name === "month" && endDate - startDate === 86400000) {
                return;
            }

            // Create new Time Table document
            var new_doc = frappe.model.get_new_doc("Time Table");

            // Extract date and time from startDate
            var start_moment = moment(startDate);
            new_doc.schedule_date = start_moment.format("YYYY-MM-DD");
            new_doc.from_time = start_moment.format("HH:mm:ss");

            // Extract end time from endDate
            if (endDate) {
                var end_moment = moment(endDate);
                new_doc.to_time = end_moment.format("HH:mm:ss");
            }

            // Navigate to the new form
            frappe.set_route("Form", "Time Table", new_doc.name);
        }
    },
};