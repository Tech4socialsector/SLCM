import frappe
from frappe.model.document import Document

class TermAdministration(Document):
	pass

@frappe.whitelist()
def get_classes_with_faculty():
	"""Get all classes with faculty names instead of IDs"""
	classes = frappe.db.sql("""
		SELECT
			cc.name,
			cc.class_name,
			cc.term,
			cc.programme,
			co.course_title AS course,
			cc.class_configuration_type AS type,
			cc.faculty,
			CONCAT(f.first_name, ' ', COALESCE(f.last_name, '')) as faculty_name
		FROM `tabClass Configuration` cc
		LEFT JOIN `tabFaculty` f ON cc.faculty = f.name
		LEFT JOIN `tabCourse Offering` co ON co.name = cc.course_offering
		ORDER BY cc.creation DESC
		LIMIT 100
	""", as_dict=True)

	return classes

@frappe.whitelist()
def create_class(data):
	if isinstance(data, str):
		data = frappe.parse_json(data)

	# JS input: program, academic_year, academic_term, batch, course, class_type,
	# faculty, max_strength, section, student_group_name

	exists = frappe.db.exists(
		"Class Configuration",
		{
			"class_name": data.get("student_group_name"),
		},
	)

	if exists:
		frappe.throw("A class with this name already exists.")

	course_offering = frappe.db.get_value(
		"Course Offering",
		{
			"course_title": data.get("course"),
			"batch": data.get("batch"),
			"term_name": data.get("academic_term"),
		},
		"name",
	)
	if not course_offering:
		frappe.throw(
			f"No Course Offering found for Course {data.get('course')}, "
			f"Batch {data.get('batch')}, Term {data.get('academic_term')}."
		)

	doc = frappe.new_doc("Class Configuration")
	doc.class_name = data.get("student_group_name")
	doc.class_configuration_type = "Section" if data.get("section") else "Group"
	doc.batch = data.get("batch")
	doc.section = data.get("section")
	doc.course_offering = course_offering
	doc.faculty = data.get("faculty")
	doc.seat_limit = data.get("max_strength")

	doc.insert()
	return doc.name

@frappe.whitelist()
def create_classes_by_section(
	batch, academic_term, course, class_type, faculty, program=None, academic_year=None
):
	# Enqueue this to run in background
	frappe.enqueue(
		"slcm.slcm.doctype.term_administration.term_administration.process_bulk_class_creation",
		queue="long",
		timeout=1500,
		program=program,
		academic_year=academic_year,
		batch=batch,
		academic_term=academic_term,
		course=course,
		class_type=class_type,
		faculty=faculty,
		user=frappe.session.user,
	)
	return "Bulk creation started. You will be notified upon completion."

def process_bulk_class_creation(
	batch, academic_term, course, class_type, faculty, user, program=None, academic_year=None
):
	course_offering = frappe.db.get_value(
		"Course Offering",
		{"course_title": course, "batch": batch, "term_name": academic_term},
		"name",
	)
	if not course_offering:
		frappe.publish_realtime(
			"bulk_class_creation_done",
			{"created": 0, "skipped": 0, "error": f"No Course Offering found for Course {course}, Batch {batch}, Term {academic_term}."},
			user=user,
		)
		return

	sections = frappe.get_all(
		"Section",
		filters={"batch": batch},
		fields=["name", "section_name", "capacity"],
	)

	created_count = 0
	skipped_count = 0

	for section in sections:
		class_name = f"{course}-{section.section_name}-{class_type}"

		if frappe.db.exists("Class Configuration", {
			"class_name": class_name,
			"batch": batch,
			"section": section.name,
			"class_configuration_type": "Section",
		}):
			skipped_count += 1
			continue

		doc = frappe.new_doc("Class Configuration")
		doc.class_name = class_name
		doc.class_configuration_type = "Section"
		doc.batch = batch
		doc.section = section.name
		doc.course_offering = course_offering
		doc.faculty = faculty
		doc.seat_limit = section.capacity

		doc.insert()
		created_count += 1

	frappe.publish_realtime(
		"bulk_class_creation_done", {"created": created_count, "skipped": skipped_count}, user=user
	)
