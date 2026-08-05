# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


from frappe.utils import to_timedelta

class TimeTable(Document):
    def validate(self):
        """Validate the Time Table entry"""
        self.validate_time()
        self.validate_repeat_settings()
        self.check_holiday_conflict()
        self.check_conflicts()
        self.check_venue_conflict()
        self.calculate_duration()

    def check_holiday_conflict(self):
        """Block scheduling a class on a date that Institutional Calendar marks
        as a Holiday or a configured Weekly Off day (e.g. Sunday)."""
        if not self.schedule_date:
            return

        from slcm.slcm.doctype.institutional_calendar.institutional_calendar import (
            get_non_teaching_reason,
        )

        non_teaching = get_non_teaching_reason(self.schedule_date)
        if non_teaching:
            frappe.throw(
                f"Cannot schedule a class on {self.schedule_date} — it is marked as "
                f"{non_teaching['reason']} ({non_teaching['name1']}) in the Institutional Calendar.",
                title="Non-Teaching Day",
            )

    def on_update(self):
        """Update the corresponding Attendance Session when the Time Table entry is updated"""
        self.update_attendance_session()

    def validate_time(self):
        """Validate that to_time is after from_time"""
        if self.from_time and self.to_time:
            if to_timedelta(self.from_time) >= to_timedelta(self.to_time):
                frappe.throw("To Time must be after From Time")

    def calculate_duration(self):
        """Keep duration_hours in sync with from_time/to_time (it's a plain
        read-only field with no fetch_from, so nothing else sets it)."""
        if self.from_time and self.to_time:
            duration_seconds = (to_timedelta(self.to_time) - to_timedelta(self.from_time)).total_seconds()
            self.duration_hours = round(duration_seconds / 3600, 2)

    def validate_repeat_settings(self):
        """Validate repeat frequency and repeats_till"""
        if self.repeat_frequency and self.repeat_frequency != "Never":
            if not self.repeats_till:
                frappe.throw("Please specify 'Repeats Till' date for recurring schedules")
            if self.repeats_till < self.schedule_date:
                frappe.throw("Repeats Till date cannot be before Schedule Date")

    def check_conflicts(self):
        """Check for scheduling conflicts"""
        if not self.schedule_date or not self.from_time or not self.to_time:
            return

        # 1. Check for Duplicate Time Table entry (Same Course Offering, Same Date, Overlapping Time)
        if self.course_offering:
            filters = {
                "name": ["!=", self.name],
                "course_offering": self.course_offering,
                "schedule_date": self.schedule_date,
                "docstatus": ["<", 2] # Exclude cancelled
            }

            conflicts = frappe.get_all(
                "Time Table",
                filters=filters,
                fields=["name", "from_time", "to_time", "course", "course_offering"],
            )

            for conflict in conflicts:
                if self.times_overlap(self.from_time, self.to_time, conflict.from_time, conflict.to_time):
                    frappe.throw(
                        f"Already scheduled same time class {conflict.course} for this Course Offering ({conflict.from_time} - {conflict.to_time})",
                        title="Duplicate Schedule"
                    )

        # 2. Check Instructor Conflict
        if self.instructor:
            conflicts = frappe.get_all(
                "Time Table",
                filters={
                    "name": ["!=", self.name],
                    "instructor": self.instructor,
                    "schedule_date": self.schedule_date,
                    "docstatus": ["<", 2]
                },
                fields=["name", "from_time", "to_time", "course"],
            )

            for conflict in conflicts:
                if self.times_overlap(self.from_time, self.to_time, conflict.from_time, conflict.to_time):
                    frappe.msgprint(
                        f"Warning: Instructor {self.instructor} has another class ({conflict.course}) "
                        f"from {conflict.from_time} to {conflict.to_time} on {self.schedule_date}",
                        indicator="orange",
                        alert=True,
                    )

    def check_venue_conflict(self):
        """Block double-booking a Venue Master for overlapping times on the
        same date. Venue used to be a Link to Venue Booking, which had its own
        availability check; now that venue links directly to Venue Master
        (which has no such check of its own), Time Table must guard against
        double-booking itself."""
        if not self.schedule_date or not self.from_time or not self.to_time or not self.venue:
            return

        conflicts = frappe.get_all(
            "Time Table",
            filters={
                "name": ["!=", self.name],
                "venue": self.venue,
                "schedule_date": self.schedule_date,
                "docstatus": ["<", 2],
            },
            fields=["name", "from_time", "to_time", "course"],
        )

        for conflict in conflicts:
            if self.times_overlap(self.from_time, self.to_time, conflict.from_time, conflict.to_time):
                frappe.throw(
                    _("Venue {0} is already booked for {1} from {2} to {3} on {4}.").format(
                        self.venue, conflict.course, conflict.from_time, conflict.to_time, self.schedule_date
                    ),
                    title=_("Venue Conflict"),
                )

    def times_overlap(self, start1, end1, start2, end2):
        """Check if two time ranges overlap"""
        return to_timedelta(start1) < to_timedelta(end2) and to_timedelta(end1) > to_timedelta(start2)

    def after_insert(self):
        """Create recurring schedules if repeat is enabled"""
        if self.repeat_frequency and self.repeat_frequency != "Never":
            self.create_recurring_schedules()
        
        # Create attendance session for this schedule
        self.create_attendance_session()

    def create_attendance_session(self):
        """Create an attendance session for this schedule"""
        from frappe.utils import getdate

        if not self.schedule_date or not self.from_time or not self.to_time:
            return

        # Check if session already exists
        exists = frappe.db.exists("Attendance Session", {
            "class_schedule": self.name,
            "session_date": self.schedule_date,
            "session_start_time": self.from_time
        })

        if exists:
            return

        based_on = self.based_on or "Time Table"

        doc = frappe.get_doc({
            "doctype": "Attendance Session",
            "based_on": based_on,
            "class_schedule": self.name,
            "course_schedule": self.course_schedule if based_on == "Course Schedule" else None,
            "office_hours_group": self.office_hours_group if based_on == "Office Hours" else None,
            "course_offering": self.course_offering,
            "course": self.course,
            "instructor": self.instructor,
            "session_date": self.schedule_date,
            "session_start_time": self.from_time,
            "session_end_time": self.to_time,
            "session_type": "Office Hour" if based_on == "Office Hours" else "Lecture",
            "session_status": "Scheduled"
        })
        # NOTE: Student Attendance records are intentionally NOT created here.
        # The session's roster is shown live (computed from Student Enrollment)
        # by update_attendance_summary() — real Student Attendance documents
        # only get created when attendance is actually taken (manual mark,
        # bulk mark, or RFID swipe).
        doc.insert(ignore_permissions=True)

    def update_attendance_session(self):
        """Update the corresponding Attendance Session when the Time Table entry is updated"""
        frappe.logger().info(f"update_attendance_session called for {self.name}")
        
        if not self.schedule_date or not self.from_time or not self.to_time:
            frappe.logger().info(f"Missing required fields: schedule_date={self.schedule_date}, from_time={self.from_time}, to_time={self.to_time}")
            return

        # Find the Attendance Session linked to this Time Table entry
        session_name = frappe.db.get_value("Attendance Session", {
            "class_schedule": self.name
        })

        if not session_name:
            frappe.logger().info(f"No Attendance Session found for Time Table entry {self.name}")
            frappe.msgprint(
                f"No Attendance Session found for this Time Table entry. "
                "Please create an Attendance Session first.",
                indicator="orange",
                alert=True
            )
            return

        frappe.logger().info(f"Found Attendance Session: {session_name}")

        # Get the Attendance Session document
        session = frappe.get_doc("Attendance Session", session_name)

        # Only update if attendance hasn't been marked yet
        # This prevents overwriting attendance data
        if session.attendance_marked:
            frappe.msgprint(
                f"Attendance has already been marked for session {session_name}. "
                "Changes to Time Table will not update the session.",
                indicator="orange",
                alert=True
            )
            return

        # Calculate duration in hours
        duration_hours = 0
        if self.from_time and self.to_time:
            from_delta = to_timedelta(self.from_time)
            to_delta = to_timedelta(self.to_time)
            duration_seconds = (to_delta - from_delta).total_seconds()
            duration_hours = duration_seconds / 3600

        frappe.logger().info(f"Updating session {session_name}: from {self.from_time} to {self.to_time}, duration={duration_hours}")

        based_on = self.based_on or "Time Table"

        # Update the session fields
        session.session_date = self.schedule_date
        session.session_start_time = self.from_time
        session.session_end_time = self.to_time
        session.duration_hours = round(duration_hours, 2)
        session.instructor = self.instructor
        session.course = self.course
        session.course_offering = self.course_offering
        session.based_on = based_on
        session.course_schedule = self.course_schedule if based_on == "Course Schedule" else None
        session.office_hours_group = self.office_hours_group if based_on == "Office Hours" else None

        # Save the session
        session.save(ignore_permissions=True)

        frappe.msgprint(
            f"Attendance Session {session_name} has been updated successfully.",
            indicator="green",
            alert=True
        )



    def create_recurring_schedules(self):
        """Create recurring class schedules based on repeat frequency"""
        if not self.repeats_till:
            return
        
        # Prevent duplicate creation if this method is called multiple times
        if frappe.db.exists("Time Table", {"parent_schedule": self.name}):
            return

        try:
            current_date = datetime.strptime(str(self.schedule_date), "%Y-%m-%d")
            end_date = datetime.strptime(str(self.repeats_till), "%Y-%m-%d")

            # Determine increment based on frequency
            if self.repeat_frequency == "Daily":
                increment = timedelta(days=1)
            elif self.repeat_frequency == "Weekly":
                increment = timedelta(weeks=1)
            elif self.repeat_frequency == "Monthly":
                increment = relativedelta(months=1)
            else:
                return

            # Create schedules
            current_date += increment  # Skip the first date (already created)
            created_count = 0
            conflict_count = 0
            holiday_skip_count = 0
            schedules_to_create = []

            from frappe.utils import getdate

            from slcm.slcm.doctype.institutional_calendar.institutional_calendar import (
                get_non_teaching_dates_in_range,
            )

            # Batch-fetch non-teaching dates and instructor's existing schedules for the
            # whole range up front instead of querying per iteration — a semester-long
            # Daily repeat would otherwise issue 500+ queries in a single request.
            non_teaching_dates = get_non_teaching_dates_in_range(current_date.date(), end_date.date())

            existing_by_date = {}
            if self.instructor:
                existing = frappe.get_all(
                    "Time Table",
                    filters={
                        "name": ["!=", self.name],
                        "instructor": self.instructor,
                        "schedule_date": ["between", [current_date.date(), end_date.date()]],
                        "docstatus": ["<", 2],
                    },
                    fields=["name", "schedule_date", "from_time", "to_time", "course"],
                )
                for row in existing:
                    existing_by_date.setdefault(getdate(row.schedule_date), []).append(row)

            # Same batch pre-check for venue double-booking as above for the
            # instructor, so a venue clash on one date in the range is skipped
            # up front instead of blowing up mid-loop via check_venue_conflict()
            # inside new_schedule.insert() below.
            venue_conflicts_by_date = {}
            if self.venue:
                venue_existing = frappe.get_all(
                    "Time Table",
                    filters={
                        "name": ["!=", self.name],
                        "venue": self.venue,
                        "schedule_date": ["between", [current_date.date(), end_date.date()]],
                        "docstatus": ["<", 2],
                    },
                    fields=["name", "schedule_date", "from_time", "to_time", "course"],
                )
                for row in venue_existing:
                    venue_conflicts_by_date.setdefault(getdate(row.schedule_date), []).append(row)

            # First, collect all schedules to create and check for conflicts
            while current_date <= end_date:
                date_only = current_date.date()

                # Skip dates marked as a Holiday or Weekly Off (e.g. Sunday) in the Institutional Calendar
                if date_only in non_teaching_dates:
                    holiday_skip_count += 1
                    current_date += increment
                    continue

                # Check for conflicts on this date
                has_conflict = False
                for conflict in existing_by_date.get(date_only, []):
                    if self.times_overlap(
                        self.from_time, self.to_time, conflict.from_time, conflict.to_time
                    ):
                        has_conflict = True
                        conflict_count += 1
                        frappe.logger().warning(
                            f"Skipping schedule on {date_only} due to conflict with {conflict.name}"
                        )
                        break

                if not has_conflict:
                    for conflict in venue_conflicts_by_date.get(date_only, []):
                        if self.times_overlap(
                            self.from_time, self.to_time, conflict.from_time, conflict.to_time
                        ):
                            has_conflict = True
                            conflict_count += 1
                            frappe.logger().warning(
                                f"Skipping schedule on {date_only} due to venue conflict with {conflict.name}"
                            )
                            break

                if not has_conflict:
                    schedules_to_create.append(current_date.strftime("%Y-%m-%d"))

                # Increment based on frequency
                current_date += increment

            # Now create all schedules in a transaction
            for schedule_date in schedules_to_create:
                new_schedule = frappe.copy_doc(self)
                new_schedule.schedule_date = schedule_date
                new_schedule.parent_schedule = self.name
                new_schedule.repeat_frequency = "Never"  # Don't repeat the child schedules
                new_schedule.repeats_till = None
                new_schedule.insert(ignore_permissions=True)
                created_count += 1

            # Provide feedback to user
            if created_count > 0:
                message = f"Created {created_count} recurring class schedule(s)"
                skip_notes = []
                if conflict_count > 0:
                    skip_notes.append(f"{conflict_count} due to conflicts")
                if holiday_skip_count > 0:
                    skip_notes.append(f"{holiday_skip_count} due to holidays")
                if skip_notes:
                    message += f" (Skipped {', '.join(skip_notes)})"
                frappe.msgprint(
                    message,
                    indicator="green" if conflict_count == 0 else "orange",
                    alert=True,
                )
            elif conflict_count > 0 or holiday_skip_count > 0:
                frappe.msgprint(
                    f"Could not create recurring schedules. All dates were skipped "
                    f"({conflict_count} conflicts, {holiday_skip_count} holidays).",
                    indicator="red",
                    alert=True,
                )
        except Exception as e:
            frappe.log_error(message=f"Error creating recurring schedules: {str(e)}", title="Recurring Schedule Creation Error")
            frappe.throw(f"Error creating recurring schedules: {str(e)}")


@frappe.whitelist()
def get_timetable_data(term=None, course=None, start_date=None, end_date=None):
    """Get timetable data for calendar view"""
    filters = {}

    if term:
        filters["term"] = term
    if course:
        filters["course"] = course
    if start_date and end_date:
        filters["schedule_date"] = ["between", [start_date, end_date]]
    
    schedules = frappe.get_all(
        "Time Table",
        filters=filters,
        fields=[
            "name",
            "title",
            "course",
            "instructor",
            "schedule_date",
            "from_time",
            "to_time",
            "venue",
            "color",
            "class_configuration",
        ],
        order_by="schedule_date, from_time",
    )

    # Format for calendar
    events = []
    for schedule in schedules:
        events.append({
            "id": schedule.name,
            "title": schedule.title or schedule.course,
            "start": f"{schedule.schedule_date}T{schedule.from_time}",
            "end": f"{schedule.schedule_date}T{schedule.to_time}",
            "backgroundColor": schedule.color or "#3498db",
            "extendedProps": {
                "course": schedule.course,
                "instructor": schedule.instructor,
                "venue": schedule.venue,
                "class_configuration": schedule.class_configuration,
            }
        })

    return events


@frappe.whitelist()
def create_time_table(data):
    """Create a class schedule from timetable configuration"""
    import json
    
    if isinstance(data, str):
        data = json.loads(data)
    
    # Create the schedule
    doc = frappe.get_doc({
        "doctype": "Time Table",
        "class_configuration": data.get("class_configuration"),
        "course": data.get("course"),
        "instructor": data.get("instructor"),
        "schedule_date": data.get("schedule_date"),
        "from_time": data.get("from_time"),
        "to_time": data.get("to_time"),
        "venue": data.get("venue"),
        "repeat_frequency": data.get("repeat_frequency", "Never"),
        "repeats_till": data.get("repeats_till"),
        "term": data.get("term"),
        "programme": data.get("programme"),
        "course_offering": data.get("course_offering"),
    })
    
    doc.insert(ignore_permissions=True)
    
    # If repeat is enabled, create recurring schedules
    if doc.repeat_frequency and doc.repeat_frequency != "Never":
        doc.create_recurring_schedules()
    
    return doc.name


@frappe.whitelist()
def get_events(start, end, filters=None):
    """
    Custom method to get events for FullCalendar.
    Handles the split date (schedule_date) and time (from_time, to_time) fields.
    """
    if not filters:
        filters = []
        
    import json
    if isinstance(filters, str):
        filters = json.loads(filters)

    # Base Query
    query = """
        SELECT
            name,
            class_configuration,
            course,
            instructor,
            schedule_date,
            from_time,
            to_time,
            duration_hours,
            venue,
            color,
            title,
            course_offering,
            based_on,
            course_schedule,
            office_hours_group
        FROM `tabTime Table`
        WHERE
            schedule_date BETWEEN %(start)s AND %(end)s
            AND docstatus < 2
    """
    
    # Add filters if present
    # This is a basic implementation. For complex standard filters, 
    # we might need frappe.get_list logic or get_event_conditions
    condition_values = {"start": start, "end": end}
    
    # Execute
    data = frappe.db.sql(query, condition_values, as_dict=True)

    # Bulk-resolve display-friendly names for instructor so the click
    # popover doesn't show raw IDs.
    instructor_names = {d.instructor for d in data if d.instructor}
    faculty_name_by_id = {}
    if instructor_names:
        faculty_name_by_id = {
            # Faculty uses numeric autonaming, so `name` comes back as an int here
            # while Time Table's `instructor` Link field stores it as a str — cast
            # to str so the lookup below actually matches instead of silently
            # falling back to the raw ID.
            str(f.name): " ".join(filter(None, [f.first_name, f.last_name]))
            for f in frappe.get_all(
                "Faculty", filters={"name": ["in", list(instructor_names)]}, fields=["name", "first_name", "last_name"]
            )
        }

    result = []
    for d in data:
        # Construct ISO datetime strings for FullCalendar
        start_dt = f"{d.schedule_date} {d.from_time}"
        end_dt = f"{d.schedule_date} {d.to_time}"

        instructor_label = faculty_name_by_id.get(d.instructor) or d.instructor

        title = d.title
        if not title:
            parts = [d.course, instructor_label]
            title = " - ".join([p for p in parts if p])
            if d.venue:
                title += f" ({d.venue})"

        result.append({
            "name": d.name,
            "id": d.name,
            "title": title,
            "start": start_dt,
            "end": end_dt,
            "color": d.color or "#3498db",
            "allDay": 0,
            "extendedProps": {
                "based_on": d.based_on,
                "course": d.course,
                "course_offering": d.course_offering,
                "course_schedule": d.course_schedule,
                "office_hours_group": d.office_hours_group,
                "instructor": instructor_label,
                "venue": d.venue,
                "from_time": str(d.from_time) if d.from_time else None,
                "to_time": str(d.to_time) if d.to_time else None,
                "duration_hours": d.duration_hours,
            }
        })

    result.extend(get_institutional_calendar_events(start, end))

    return result


def get_institutional_calendar_events(start, end):
    """Render Institutional Calendar entries (holidays, exams, events, ...)
    as solid, labeled all-day banners on the Time Table calendar view."""
    entries = frappe.db.sql(
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

    entry_colors = {
        "Holiday": "#e74c3c",
        "Exam": "#9b59b6",
        "Semester Start": "#2ecc71",
        "Semester End": "#2ecc71",
        "Event": "#f39c12",
        "Orientation": "#1abc9c",
        "Other": "#95a5a6",
    }

    events = []
    for entry in entries:
        entry_color = entry_colors.get(entry.entry_type, "#95a5a6")
        events.append({
            "name": f"ic-{entry.name}",
            "id": f"ic-{entry.name}",
            "title": f"{entry.entry_type}: {entry.name1}",
            "start": str(entry.start_date),
            "end": str(entry.end_date + timedelta(days=1)),
            "allDay": 1,
            "editable": False,
            "color": entry_color,
            "backgroundColor": entry_color,
            "borderColor": entry_color,
            "textColor": "#ffffff",
            "extendedProps": {
                "institutional_calendar": entry.name,
                "entry_type": entry.entry_type,
            },
        })
    return events


@frappe.whitelist()
def get_future_occurrences(time_table_name):
    """Return this schedule and its sibling occurrences (same recurring series)
    dated today or later, for the 'apply to future occurrences' confirmation."""
    from frappe.utils import getdate, nowdate

    doc = frappe.get_doc("Time Table", time_table_name)
    series_root = doc.parent_schedule or doc.name

    # Series = the root itself plus every child pointing at it.
    series_names = [series_root] + [
        d.name
        for d in frappe.get_all("Time Table", filters={"parent_schedule": series_root}, fields=["name"])
    ]

    future = frappe.get_all(
        "Time Table",
        filters={
            "name": ["in", series_names],
            "schedule_date": [">=", nowdate()],
            "docstatus": ["<", 2],
        },
        fields=["name", "schedule_date", "venue", "from_time", "to_time"],
        order_by="schedule_date",
    )

    return {
        "count": len(future),
        "occurrences": future,
    }


@frappe.whitelist()
def find_sessions(programme=None, section=None, schedule_date=None):
    """List Time Table sessions, optionally narrowed by Programme, Section
    and/or Date (used by the list-view 'Update Venue / Time' dialog so it can
    be opened without pre-checking any row, and browsed/filtered from there).

    All filters are optional and Section in particular is often blank on real
    records (Time Table only fetches it from course_offering.section, and many
    rows only have class_configuration set, not course_offering) - filtering
    on it unconditionally would silently hide otherwise-matching sessions, so
    it's applied only when the caller actually provided a value.
    """
    filters = {"docstatus": ["<", 2]}
    if programme:
        filters["programme"] = programme
    if section:
        filters["section"] = section
    if schedule_date:
        filters["schedule_date"] = schedule_date

    sessions = frappe.get_all(
        "Time Table",
        filters=filters,
        # Only the columns the dialog's session table actually renders -
        # avoid pulling instructor/course_offering/etc. into the response
        # just because they exist on the doctype.
        fields=["name", "course", "programme", "section", "schedule_date", "from_time", "to_time", "venue"],
        order_by="schedule_date desc, from_time",
        limit_page_length=100,
    )

    # `course` is a plain Data field, not a Link - on rows where it was set
    # from a Course record it holds the Course's hashed `name` (e.g.
    # "dkmt49uui9") rather than a readable title, so resolve it to
    # course_name where possible. Rows where `course` was typed in directly
    # (no matching Course record) keep showing as-is.
    course_ids = {s.course for s in sessions if s.course}
    course_name_by_id = {}
    if course_ids:
        course_name_by_id = {
            c.name: c.course_name
            for c in frappe.get_all(
                "Course", filters={"name": ["in", list(course_ids)]}, fields=["name", "course_name"]
            )
        }
    for s in sessions:
        if s.course in course_name_by_id:
            s.course = course_name_by_id[s.course]

    return {"sessions": sessions}


@frappe.whitelist()
def get_sessions_roster(time_table_names):
    """Combined student roster across one or more Time Table sessions, shown
    for confirmation before applying a venue/time change to all of them.
    Resolved via each session's linked Class Configuration's own `students`
    child table rather than Student Enrollment by section, since Time Table's
    `section` field is frequently blank while `class_configuration` is
    reliably set. Multiple sessions sharing the same class_configuration
    (e.g. several dates of the same recurring class) are de-duplicated."""
    import json

    if isinstance(time_table_names, str):
        time_table_names = json.loads(time_table_names)
    time_table_names = list(dict.fromkeys(time_table_names))  # de-dupe, preserve order

    if not time_table_names:
        return {"students": []}

    class_configurations = {
        row.class_configuration
        for row in frappe.get_all(
            "Time Table",
            filters={"name": ["in", time_table_names]},
            fields=["class_configuration"],
        )
        if row.class_configuration
    }

    if not class_configurations:
        return {"students": []}

    students = frappe.get_all(
        "Class Student",
        filters={"parent": ["in", list(class_configurations)], "parenttype": "Class Configuration"},
        fields=["student", "student_name"],
        order_by="student_name",
    )

    # A student enrolled in more than one of the selected classes would
    # otherwise appear once per class - keep one row per student.
    seen = set()
    unique_students = []
    for s in students:
        if s.student in seen:
            continue
        seen.add(s.student)
        unique_students.append(s)

    return {"students": unique_students}


def _parse_updates(updates):
    import json

    if isinstance(updates, str):
        updates = json.loads(updates)

    allowed_fields = {"venue", "from_time", "to_time", "schedule_date", "instructor", "color"}
    updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not updates:
        frappe.throw(_("No updatable fields were provided."))
    return updates


def _apply_updates_to_rows(names, updates):
    """Validate `updates` against every named Time Table row (without saving),
    then persist only if every row passed. Time Table.validate() already runs
    check_conflicts(), check_holiday_conflict() and validate_time() - reuse it
    instead of duplicating that logic here. Returns the saved docs.

    Raises (via frappe.throw) with the full list of conflicts if any row fails
    validation, so the caller sees every problem at once instead of one at a
    time, and nothing is written to the database in that case.
    """
    if not names:
        frappe.throw(_("No occurrences were found to update."))

    errors = []
    docs_to_save = []
    for name in names:
        row_doc = frappe.get_doc("Time Table", name)
        for field, value in updates.items():
            row_doc.set(field, value)
        try:
            row_doc.run_method("validate")
        except Exception as e:
            errors.append(f"{row_doc.schedule_date} ({row_doc.name}): {e}")
            continue
        docs_to_save.append(row_doc)

    if errors:
        frappe.throw(
            _("Could not apply the change to all occurrences due to conflicts:<br>{0}").format(
                "<br>".join(frappe.utils.escape_html(e) for e in errors)
            ),
            title=_("Update Blocked"),
        )

    # All-or-nothing: if a save unexpectedly fails here (e.g. another user
    # booked the venue in the gap between validation and here), roll back
    # whatever this loop already wrote instead of leaving a half-updated set.
    try:
        for row_doc in docs_to_save:
            row_doc.save(ignore_permissions=True)
    except Exception:
        frappe.db.rollback()
        raise

    frappe.db.commit()
    return docs_to_save


@frappe.whitelist()
def bulk_update_future_occurrences(time_table_name, updates):
    """Apply a set of field changes (e.g. venue, from_time, to_time) to this
    Time Table occurrence and every future occurrence in the same recurring
    series (schedule_date >= today). Past occurrences are never touched, so
    historical attendance/venue records stay accurate.

    `updates` is a dict of {fieldname: value} restricted to a safe allowlist.
    Venue changes are conflict-checked against Venue Booking availability for
    every affected date before anything is written; if any date conflicts,
    nothing is saved and the caller gets back the list of conflicting dates.
    """
    from frappe.utils import nowdate

    updates = _parse_updates(updates)

    doc = frappe.get_doc("Time Table", time_table_name)
    series_root = doc.parent_schedule or doc.name

    series_names = [series_root] + [
        d.name
        for d in frappe.get_all("Time Table", filters={"parent_schedule": series_root}, fields=["name"])
    ]

    future_rows = frappe.get_all(
        "Time Table",
        filters={
            "name": ["in", series_names],
            "schedule_date": [">=", nowdate()],
            "docstatus": ["<", 2],
        },
        fields=["name"],
        order_by="schedule_date",
    )

    if not future_rows:
        frappe.throw(_("No current or future occurrences found to update."))

    docs_to_save = _apply_updates_to_rows([r.name for r in future_rows], updates)

    return {
        "updated_count": len(docs_to_save),
        "updated_names": [d.name for d in docs_to_save],
    }


@frappe.whitelist()
def bulk_update_selected_occurrences(names, updates):
    """List-view bulk action: apply a set of field changes (venue, time, ...)
    to exactly the Time Table rows the user checked - no series/date inference,
    since the checkboxes already say precisely which rows are in scope. Reuses
    the same validate-then-save-all-or-nothing logic as the future-occurrences
    action above.
    """
    import json

    if isinstance(names, str):
        names = json.loads(names)
    names = list(dict.fromkeys(names))  # de-dupe, preserve order

    updates = _parse_updates(updates)

    existing = frappe.get_all(
        "Time Table",
        filters={"name": ["in", names], "docstatus": ["<", 2]},
        fields=["name"],
        order_by="schedule_date",
    )
    valid_names = [r.name for r in existing]

    skipped = len(names) - len(valid_names)
    docs_to_save = _apply_updates_to_rows(valid_names, updates)

    return {
        "updated_count": len(docs_to_save),
        "updated_names": [d.name for d in docs_to_save],
        "skipped_count": skipped,
    }


@frappe.whitelist()
def update_event(args, field_map):
    """
    Custom update method for Time Table calendar drag-and-drop.
    Handles the split date (schedule_date) and time (from_time, to_time) fields.
    """
    import json
    from datetime import datetime
    
    if isinstance(args, str):
        args = json.loads(args)
    if isinstance(field_map, str):
        field_map = json.loads(field_map)
    
    args = frappe._dict(args)
    field_map = frappe._dict(field_map)

    if args.doctype != "Time Table":
        frappe.throw(frappe._("This endpoint can only update Time Table records."), frappe.PermissionError)

    # Get the document
    doc = frappe.get_doc(args.doctype, args.name)
    
    # Parse the start datetime
    if field_map.start and args.get(field_map.start):
        start_dt = args[field_map.start]
        if isinstance(start_dt, str):
            start_dt = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
        
        # Update schedule_date and from_time
        doc.schedule_date = start_dt.date()
        doc.from_time = start_dt.time()
    
    # Parse the end datetime
    if field_map.end and args.get(field_map.end):
        end_dt = args[field_map.end]
        if isinstance(end_dt, str):
            end_dt = datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")
        
        # Update to_time (date should remain the same as schedule_date)
        doc.to_time = end_dt.time()
    
    # Save the document
    doc.save()
    
    return doc.name


@frappe.whitelist()
def update_attendance_session_realtime(time_table_name, from_time, to_time, schedule_date, duration_hours):
	"""
	Update Attendance Session in real-time when Time Table entry times change.
	Called from client-side JavaScript without requiring a full save.
	Also triggers recalculation of Attendance Summary for all affected students.
	"""
	try:
		# Find the Attendance Session linked to this Time Table entry
		session_name = frappe.db.get_value("Attendance Session", {
			"class_schedule": time_table_name
		})

		if not session_name:
			return {"success": False, "message": "No Attendance Session found"}

		# Get the Attendance Session document
		session = frappe.get_doc("Attendance Session", session_name)

		# Only update if attendance hasn't been marked yet
		if session.attendance_marked:
			return {"success": False, "message": "Attendance already marked"}

		# Update the session fields
		session.session_start_time = from_time
		session.session_end_time = to_time
		session.duration_hours = duration_hours
		session.session_date = schedule_date

		# Save the session
		session.save(ignore_permissions=True)
		frappe.db.commit()

		# Trigger attendance recalculation for all students in this course offering
		# This updates total_class_hours in Attendance Summary
		if session.course_offering:
			try:
				from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
				
				# Get all students who have attendance records for this course offering
				students = frappe.db.sql("""
					SELECT DISTINCT student
					FROM `tabStudent Attendance`
					WHERE course_offer = %s
				""", session.course_offering, as_dict=True)
				
				# Recalculate attendance for each student
				for student_row in students:
					calculate_student_attendance(student_row.student, session.course_offering)
				
				frappe.db.commit()
			except Exception as calc_error:
				# Log the error but don't fail the entire operation
				frappe.log_error(
					message=f"Error recalculating attendance: {str(calc_error)}", 
					title="Attendance Recalculation Error"
				)

		return {
			"success": True,
			"message": f"Attendance Session {session_name} updated",
			"session_name": session_name
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Real-time Attendance Session Update Error")
		return {"success": False, "message": str(e)}
