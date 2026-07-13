# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
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
        self.calculate_duration()

    def check_holiday_conflict(self):
        """Block scheduling a class on a date marked as a Holiday in the Institutional Calendar"""
        if not self.schedule_date:
            return

        holidays = frappe.get_all(
            "Institutional Calendar",
            filters={
                "entry_type": "Holiday",
                "start_date": ["<=", self.schedule_date],
                "end_date": [">=", self.schedule_date],
                "status": ["!=", "Inactive"],
                "docstatus": ["<", 2],
            },
            fields=["name1"],
        )

        if holidays:
            frappe.throw(
                f"Cannot schedule a class on {self.schedule_date} — it is marked as a holiday "
                f"({holidays[0].name1}) in the Institutional Calendar.",
                title="Holiday",
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

        # 1. Check for Duplicate Time Table entry (Same Student Group, Same Date, Overlapping Time)
        if self.student_group:
            filters = {
                "name": ["!=", self.name],
                "student_group": self.student_group,
                "schedule_date": self.schedule_date,
                "docstatus": ["<", 2] # Exclude cancelled
            }
            
            # Optional: restrict to same course if 'same class' means exact same course
            # But usually 'same class' means the students are busy. 
            # User said "save the same time same class same day it should not duplicate"
            # implying exact duplicate of the schedule.
            # Let's check for Student Group overlap broadly implies they are busy.
            # But the user specifically said "duplicate... same time same class".
            # "Class" context usually means Course in this system (from previous files).
            # Let's stick to Student Group + Course overlap to be safe against "Duplicate", 
            # OR just Student Group overlap to prevent double booking the students.
            # Given "validations", double booking students is generally bad.
            # I will check for Student Group overlap.
            
            conflicts = frappe.get_all(
                "Time Table",
                filters=filters,
                fields=["name", "from_time", "to_time", "course", "student_group"],
            )

            for conflict in conflicts:
                if self.times_overlap(self.from_time, self.to_time, conflict.from_time, conflict.to_time):
                    frappe.throw(
                        f"Already scheduled same time class {conflict.course} for {self.student_group} ({conflict.from_time} - {conflict.to_time})",
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
            "time_table": self.name,
            "session_date": self.schedule_date,
            "session_start_time": self.from_time
        })

        if exists:
            return

        # Fetch Room from Venue Booking if venue is selected
        room_name = None
        if self.venue:
            room_name = frappe.db.get_value("Venue Booking", self.venue, "room")

        doc = frappe.get_doc({
            "doctype": "Attendance Session",
            "based_on": "Time Table",
            "time_table": self.name,
            "student_group": self.student_group,
            "course_offering": self.course_offering,
            "course": self.course,
            "instructor": self.instructor,
            "room": room_name,
            "session_date": self.schedule_date,
            "session_start_time": self.from_time,
            "session_end_time": self.to_time,
            "session_type": "Lecture",
            "session_status": "Scheduled"
        })
        # Prevent auto-creation of Student Attendance placeholders.
        # Records are only created when the teacher explicitly fetches students
        # or marks attendance via the Student Attendance Tool.
        doc.flags.skip_auto_attendance = True
        doc.insert(ignore_permissions=True)

    def update_attendance_session(self):
        """Update the corresponding Attendance Session when the Time Table entry is updated"""
        frappe.logger().info(f"update_attendance_session called for {self.name}")
        
        if not self.schedule_date or not self.from_time or not self.to_time:
            frappe.logger().info(f"Missing required fields: schedule_date={self.schedule_date}, from_time={self.from_time}, to_time={self.to_time}")
            return

        # Find the Attendance Session linked to this Time Table entry
        session_name = frappe.db.get_value("Attendance Session", {
            "time_table": self.name
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

        # Fetch Room from Venue Booking if venue is selected
        room_name = None
        if self.venue:
            room_name = frappe.db.get_value("Venue Booking", self.venue, "room")

        # Calculate duration in hours
        duration_hours = 0
        if self.from_time and self.to_time:
            from_delta = to_timedelta(self.from_time)
            to_delta = to_timedelta(self.to_time)
            duration_seconds = (to_delta - from_delta).total_seconds()
            duration_hours = duration_seconds / 3600

        frappe.logger().info(f"Updating session {session_name}: from {self.from_time} to {self.to_time}, duration={duration_hours}")

        # Update the session fields
        session.session_date = self.schedule_date
        session.session_start_time = self.from_time
        session.session_end_time = self.to_time
        session.duration_hours = round(duration_hours, 2)
        session.instructor = self.instructor
        session.room = room_name
        session.course = self.course
        session.course_offering = self.course_offering
        session.student_group = self.student_group

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

            # First, collect all schedules to create and check for conflicts
            while current_date <= end_date:
                # Skip dates marked as a Holiday in the Institutional Calendar
                if frappe.get_all(
                    "Institutional Calendar",
                    filters={
                        "entry_type": "Holiday",
                        "start_date": ["<=", current_date.strftime("%Y-%m-%d")],
                        "end_date": [">=", current_date.strftime("%Y-%m-%d")],
                        "status": ["!=", "Inactive"],
                        "docstatus": ["<", 2],
                    },
                    limit=1,
                ):
                    holiday_skip_count += 1
                    current_date += increment
                    continue

                # Check for conflicts on this date
                has_conflict = False
                if self.instructor:
                    conflicts = frappe.get_all(
                        "Time Table",
                        filters={
                            "instructor": self.instructor,
                            "schedule_date": current_date.strftime("%Y-%m-%d"),
                        },
                        fields=["name", "from_time", "to_time", "course"],
                    )
                    
                    for conflict in conflicts:
                        if self.times_overlap(
                            self.from_time, self.to_time, conflict.from_time, conflict.to_time
                        ):
                            has_conflict = True
                            conflict_count += 1
                            frappe.logger().warning(
                                f"Skipping schedule on {current_date.strftime('%Y-%m-%d')} due to conflict with {conflict.name}"
                            )
                            break
                
                if not has_conflict:
                    schedules_to_create.append(current_date.strftime("%Y-%m-%d"))
                
                # Increment based on frequency
                if self.repeat_frequency == "Monthly":
                    current_date += increment
                else:
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
            "student_group",
        ],
        order_by="schedule_date, from_time",
    )

    # Time Table has no "room" field of its own - room lives on the
    # linked Venue Booking, so resolve it in one bulk lookup.
    venue_names = {s.venue for s in schedules if s.venue}
    room_by_venue = {}
    if venue_names:
        room_by_venue = {
            v.name: v.room
            for v in frappe.get_all(
                "Venue Booking", filters={"name": ["in", list(venue_names)]}, fields=["name", "room"]
            )
        }

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
                "room": room_by_venue.get(schedule.venue),
                "venue": schedule.venue,
                "class_configuration": schedule.class_configuration,
                "student_group": schedule.student_group,
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
        "student_group": data.get("student_group"),
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
            venue,
            color,
            title,
            student_group
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

    result = []
    for d in data:
        # Construct ISO datetime strings for FullCalendar
        start_dt = f"{d.schedule_date} {d.from_time}"
        end_dt = f"{d.schedule_date} {d.to_time}"

        title = d.title
        if not title:
            parts = [d.course, d.instructor]
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
                "venue": d.venue,
                "instructor": d.instructor,
                "student_group": d.student_group
            }
        })

    result.extend(get_institutional_calendar_events(start, end))

    return result


def get_institutional_calendar_events(start, end):
    """Render Institutional Calendar entries (holidays, exams, events, ...)
    as background markers on the Time Table calendar view."""
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
        events.append({
            "name": f"ic-{entry.name}",
            "id": f"ic-{entry.name}",
            "title": f"{entry.entry_type}: {entry.name1}",
            "start": str(entry.start_date),
            "end": str(entry.end_date + timedelta(days=1)),
            "allDay": 1,
            "display": "background",
            "editable": False,
            "color": entry_colors.get(entry.entry_type, "#95a5a6"),
            "extendedProps": {
                "institutional_calendar": entry.name,
                "entry_type": entry.entry_type,
            },
        })
    return events


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
			"time_table": time_table_name
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
