import frappe
from frappe import _
from frappe.model.document import Document

class OfficeHoursGroup(Document):
	pass

@frappe.whitelist()
def get_students(program, course, academic_year=None, academic_term=None, batch=None, section=None):
	if not program:
		return []

	if section:
		# If Section is provided, the source of truth is the Student Group
		# We want all students active in the Student Group(s) for this Section
		
		# Find Student Groups for this Section
		# Filters: Program, Course, Section are mandatory context from the UI
		sg_filters = {
			"program": program,
			"course": course,
			"section": section,
			"docstatus": ["<", 2],
			"status": "Active" # Only active groups
		}
		
		if academic_year:
			sg_filters["academic_year"] = academic_year
		if academic_term:
			sg_filters["academic_term"] = academic_term
		if batch:
			sg_filters["batch"] = batch
			
		student_groups = frappe.get_all("Student Group", filters=sg_filters, pluck="name")
		
		if not student_groups:
			return []
			
		# Fetch students from these groups
		students = frappe.db.sql("""
			SELECT DISTINCT
				sgs.student,
				sgs.student_name,
				sgs.group_roll_number,
				sgs.active
			FROM
				`tabStudent Group Student` sgs
			WHERE
				sgs.parent IN %(groups)s
				AND sgs.active = 1
			ORDER BY
				sgs.group_roll_number, sgs.student_name
		""", {"groups": student_groups}, as_dict=True)
		
		return students

	# Base query on Student Enrollment
	# We want students who are Active and Enrolled in the Program
	
	params = {"program": program}
	conditions = ["se.program = %(program)s", "se.status = 'Enrolled'", "se.docstatus < 2"]
	
	if academic_year:
		conditions.append("se.academic_year = %(academic_year)s")
		params["academic_year"] = academic_year

	if academic_term:
		conditions.append("se.term_name = %(academic_term)s")
		params["academic_term"] = academic_term
		
	if batch:
		# 'data_xgxm' is the fieldname for Batch in 'Student Enrollment'
		conditions.append("se.data_xgxm = %(batch)s")
		params["batch"] = batch
		
	# Join with Course (Program Enrollment child table)
	# The child table fieldname is 'table_hxbo' in Student Enrollment
	join_course = ""
	if course:
		join_course = """
			INNER JOIN `tabProgram Enrollment` pe 
			ON pe.parent = se.name 
			AND pe.course = %(course)s
		"""
		params["course"] = course
		
	# Section filter via Student Group
	if section:
		# We need students who are in a Student Group linked to this section
		conditions.append("""
			EXISTS (
				SELECT 1 FROM `tabStudent Group` sg
				INNER JOIN `tabStudent Group Student` sgs ON sgs.parent = sg.name
				WHERE sg.section = %(section)s
				AND sgs.student = se.student
				AND sg.docstatus < 2
			)
		""")
		params["section"] = section
		
	sql = f"""
		SELECT DISTINCT
			se.student,
			se.student_name
		FROM
			`tabStudent Enrollment` se
		{join_course}
		WHERE
			{" AND ".join(conditions)}
		ORDER BY se.student_name
	"""
	
	students = frappe.db.sql(sql, params, as_dict=True)
	
	# Check Student Master status to be consistent
	for s in students:
		status = frappe.db.get_value("Student Master", s.student, "student_status")
		s.active = 1 if status == "Active" else 0
		
	return students
