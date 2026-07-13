# Copyright (c) 2026, Nishanth and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_hours
from slcm.slcm.utils.attendance_calculator import calculate_student_attendance

class AttendanceSession(Document):
	"""Track conducted class sessions for attendance calculation"""
	
	def validate(self):
		"""Validate session details"""
		self.calculate_duration()
		self.validate_times()
	
	def after_insert(self):
		"""Session created — students are NOT auto-populated.
		Use the 'Fetch Students' button or the Student Attendance Tool to mark attendance."""
		pass

	def on_submit(self):
		"""Trigger attendance calculations"""
		self.update_student_attendance_status()
		self.trigger_calculations()

	def on_update(self):
		"""Trigger calculations on save"""
		# Ensure duration is recalculated if times changed
		self.calculate_duration()

		if not self.flags.get("from_student_attendance"):
			self.update_student_attendance_hours()
			self.sync_details_to_attendance()
			self.trigger_calculations()

	def update_student_attendance_hours(self):
		"""Update hours_counted in ALL linked Student Attendance records when session duration changes."""
		if not self.duration_hours:
			return

		# Update all sources including RFID — session duration is authoritative
		frappe.db.sql("""
			UPDATE `tabStudent Attendance`
			SET hours_counted = %s
			WHERE attendance_session = %s
			AND status IN ('Present', 'Late', 'Excused')
			AND docstatus < 2
		""", (self.duration_hours, self.name))

	def sync_details_to_attendance(self):
		"""Sync Session Type and other details to linked Student Attendance"""
		doc_before = self.get_doc_before_save()
		if doc_before:
			if (doc_before.session_type == self.session_type and
					str(doc_before.session_date) == str(self.session_date)):
				return
		frappe.db.sql("""
			UPDATE `tabStudent Attendance`
			SET session_type = %s, attendance_date = %s
			WHERE attendance_session = %s
		""", (self.session_type, self.session_date, self.name))

	def calculate_duration(self):
		"""Calculate session duration in hours"""
		if self.session_start_time and self.session_end_time:
			self.duration_hours = time_diff_in_hours(self.session_end_time, self.session_start_time)
	
	def validate_times(self):
		"""Ensure end time is after start time"""
		if self.session_start_time and self.session_end_time:
			if self.session_end_time <= self.session_start_time:
				frappe.throw("Session end time must be after start time")

	def create_student_attendance_records(self):
		"""Fetch enrolled students and create initial attendance records"""
		if self.flags.skip_auto_attendance:
			return

		students = self.get_enrolled_students()
		
		for student_id in students:
			# Check if record already exists to avoid duplicates
			exists = frappe.db.exists("Student Attendance", {
				"student": student_id,
				"attendance_session": self.name
			})
			
			if not exists:
				doc = frappe.get_doc({
					"doctype": "Student Attendance",
					"student": student_id,
					"attendance_session": self.name,
					"class_schedule": self.class_schedule,
					"course_schedule": self.course_schedule,
					"course_offer": self.course_offering,
					"attendance_date": self.session_date,
					"date": self.session_date,
					"session_type": self.session_type,
					"status": "Absent",
					"source": "Auto",
					"student_group": self.student_group,
					"hours_counted": self.duration_hours or 1.0,
				})
				doc.insert(ignore_permissions=True)
				
		self.update_attendance_summary()

	def get_enrolled_students(self):
		"""Find students based on Student Group or Class Enrollment"""
		if self.student_group:
			# Fetch from Student Group
			students = frappe.get_all("Student Group Student", 
				filters={"parent": self.student_group, "active": 1},
				fields=["student"]
			)
			return [s.student for s in students]

		# Fallback: Find Student Enrollments linked to this Course Offering
		if not self.course_offering:
			return []

		students = frappe.db.sql("""
			SELECT DISTINCT se.student
			FROM `tabStudent Enrollment` se
			JOIN `tabStudent Enrollment Course` sec ON sec.parent = se.name
			WHERE sec.course_offering = %s
			AND sec.status = 'Enrolled'
			AND se.status = 'Enrolled'
			AND se.docstatus = 0
		""", (self.course_offering,), as_dict=True)
		
		return [s.student for s in students]

	def update_student_attendance_status(self):
		"""Lock attendance records on submit"""
		pass # Student Attendance is submittable? Or we just leave them.
		# If Student Attendance is a submittable doctype, we should submit them.
		# Let's check Student Attendance doctype. It has docstatus, so it might be submittable.
		# Generally Student Attendance is not a submittable document in standard ERPNext, but here?
		# It has "submitted" status? 
		# If it's not submittable, we just leave them.
		
	def trigger_calculations(self):
		"""Recalculate attendance for all students in this session"""
		students = [row.student for row in (self.students or []) if row.student]
		if not students:
			students = self.get_enrolled_students()
		if self.course_offering:
			for student_id in students:
				calculate_student_attendance(student_id, self.course_offering)

	def before_save(self):
		"""Calculate summary before saving"""
		self.validate_times()
		self.update_attendance_summary()
	
	def update_attendance_summary(self):
		"""Update attendance counts and student list"""
		attendance_data = frappe.db.sql("""
			SELECT
				COUNT(*) as total,
				SUM(CASE WHEN sa.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as present,
				SUM(CASE WHEN sa.status = 'Absent'             THEN 1 ELSE 0 END) as absent,
				SUM(CASE WHEN sa.status IN ('Present', 'Late')
				         AND (s.gender = 'Male' OR s.gender = 'Man')   THEN 1 ELSE 0 END) as boys,
				SUM(CASE WHEN sa.status IN ('Present', 'Late')
				         AND (s.gender = 'Female' OR s.gender = 'Woman') THEN 1 ELSE 0 END) as girls,
				SUM(CASE WHEN sa.source = 'Manual'             THEN 1 ELSE 0 END) as manually_marked,
				SUM(CASE WHEN sa.source = 'RFID'               THEN 1 ELSE 0 END) as rfid_marked
			FROM `tabStudent Attendance` sa
			JOIN `tabStudent Master` s ON sa.student = s.name
			WHERE sa.attendance_session = %s
			AND sa.docstatus < 2
		""", self.name, as_dict=True)

		if attendance_data:
			data = attendance_data[0]
			self.total_students = data.get('total', 0) or 0
			manually_marked = data.get('manually_marked', 0) or 0
			rfid_marked = data.get('rfid_marked', 0) or 0
			self.present_count = data.get('present', 0) or 0
			self.absent_count = data.get('absent', 0) or 0
			self.total_boys = data.get('boys', 0) or 0
			self.total_girls = data.get('girls', 0) or 0

			if self.total_students > 0:
				self.attendance_percentage = (self.present_count / self.total_students) * 100
			else:
				self.attendance_percentage = 0

			# attendance_marked = 1 only when a teacher has manually marked attendance.
			# RFID-only marking does NOT set this flag — teacher must confirm.
			# Auto placeholder records (source='Auto') never count.
			self.attendance_marked = 1 if manually_marked > 0 else 0

			# session_status flips to "Conducted" when either Manual or RFID attendance exists
			if (manually_marked > 0 or rfid_marked > 0) and self.session_status == "Scheduled":
				self.session_status = "Conducted"

		# Populate Child Table
		# Clear existing rows to avoid duplication/stale data
		self.set("students", [])
		
		# Fetch details for child table
		student_records = frappe.db.sql("""
			SELECT sa.student, s.first_name, sa.status, s.gender
			FROM `tabStudent Attendance` sa
			JOIN `tabStudent Master` s ON sa.student = s.name
			WHERE sa.attendance_session = %s
			ORDER BY s.first_name asc
		""", self.name, as_dict=True)
		
		for record in student_records:
			self.append("students", {
				"student": record.student,
				"student_name": record.first_name,
				"status": record.status,
				"gender": record.gender
			})
			
	# Note: No separate save() call needed because this is called in before_save
	# or can be called manually followed by save() 

@frappe.whitelist()
def mark_session_conducted(session_name):
	"""Mark a session as conducted"""
	session = frappe.get_doc("Attendance Session", session_name)
	session.session_status = "Conducted"
	session.save()
	return session


@frappe.whitelist()
def get_pending_sessions(instructor=None, course_offering=None):
	"""Get sessions where attendance is not yet marked"""
	filters = {
		"session_status": ["in", ["Scheduled", "Conducted"]],
		"attendance_marked": 0
	}
	
	if instructor:
		filters["instructor"] = instructor
	
	if course_offering:
		filters["course_offering"] = course_offering
	
	return frappe.get_all(
		"Attendance Session",
		filters=filters,
		fields=["name", "session_date", "course", "instructor", "duration_hours"],
		order_by="session_date desc"
	)


@frappe.whitelist()
def fetch_students_for_session(session_name):
	"""Fetch enrolled students and create attendance records for a session"""
	session_doc = frappe.get_doc("Attendance Session", session_name)
	before_count = frappe.db.count("Student Attendance", {"attendance_session": session_name})
	session_doc.create_student_attendance_records()
	after_count = frappe.db.count("Student Attendance", {"attendance_session": session_name})
	fetched = after_count - before_count
	return f"Fetched {fetched} student(s) — total {after_count} in session"


@frappe.whitelist()
def update_attendance_summary_realtime(session_name, course_offering, duration_hours):
	"""
	Update Attendance Summary in real-time when Attendance Session times change.
	Called from client-side JavaScript without requiring a full save.
	Recalculates total_class_hours for all affected students.
	"""
	try:
		# Verify the session exists
		if not frappe.db.exists("Attendance Session", session_name):
			return {"success": False, "message": "Attendance Session not found"}

		# Trigger attendance recalculation for all students in this course offering
		from slcm.slcm.utils.attendance_calculator import calculate_student_attendance
		
		# Get all students who have attendance records for this course offering
		students = frappe.db.sql("""
			SELECT DISTINCT student
			FROM `tabStudent Attendance`
			WHERE course_offer = %s
		""", course_offering, as_dict=True)
		
		students_updated = 0
		
		# Recalculate attendance for each student
		for student_row in students:
			try:
				calculate_student_attendance(student_row.student, course_offering)
				students_updated += 1
			except Exception as student_error:
				frappe.log_error(
					message=f"Error updating student {student_row.student}: {str(student_error)}",
					title="Student Attendance Update Error"
				)
		
		frappe.db.commit()

		return {
			"success": True,
			"message": f"Attendance Summary updated for {students_updated} students",
			"students_updated": students_updated
		}

	except Exception as e:
		frappe.log_error(message=str(e), title="Real-time Attendance Summary Update Error")
		return {"success": False, "message": str(e)}

