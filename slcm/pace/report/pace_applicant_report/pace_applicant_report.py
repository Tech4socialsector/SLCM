import frappe
from frappe import _


def execute(filters: dict | None = None):
	"""Return columns and data for the report."""
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_report_summary(data)

	return columns, data, None, None, report_summary


def get_columns() -> list[dict]:
	"""Return columns for the report."""
	return [
		{
			"label": _("Applicant ID"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "PACE Application",
			"width": 140
		},
		{
			"label": _("Applicant Name"),
			"fieldname": "applicant_name",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("First Name"),
			"fieldname": "first_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Middle Name"),
			"fieldname": "middle_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Last Name"),
			"fieldname": "last_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Email Address"),
			"fieldname": "email_address",
			"fieldtype": "Data",
			"width": 180
		},
		
		{
			"label": _("Mobile Number"),
			"fieldname": "mobile_number",
			"fieldtype": "Data",
			"width": 130
		},
		{
			"label": _("Date of Birth"),
			"fieldname": "date_of_birth",
			"fieldtype": "Date",
			"width": 110
		},
		{
			"label": _("Gender"),
			"fieldname": "gender",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Nationality"),
			"fieldname": "nationality",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label": _("Category"),
			"fieldname": "category",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Father's Name"),
			"fieldname": "father_name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Mother's Name"),
			"fieldname": "mother_name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Address Line 1"),
			"fieldname": "address_line_1",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Address Line 2"),
			"fieldname": "address_line_2",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("City"),
			"fieldname": "city",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label": _("District"),
			"fieldname": "district",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label": _("State"),
			"fieldname": "state",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Country"),
			"fieldname": "country",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label": _("Pincode"),
			"fieldname": "pincode",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("UG University"),
			"fieldname": "ug_university",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("UG Institution"),
			"fieldname": "ug_institution",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("UG Programme Studied"),
			"fieldname": "ug_programme_studied",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("UG Year of Passing"),
			"fieldname": "ug_year_of_passing",
			"fieldtype": "Int",
			"width": 110
		},
		{
			"label": _("UG Result Status"),
			"fieldname": "ug_result_status",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("UG Obtained Percentage/CGPA"),
			"fieldname": "ug_obtained_percentagecgpa",
			"fieldtype": "Percent",
			"width": 140
		},
		{
			"label": _("Programme"),
			"fieldname": "programme",
			"fieldtype": "Link",
			"options": "PACE Programme",
			"width": 180
		},
		{
			"label": _("Academic Year"),
			"fieldname": "academic_year",
			"fieldtype": "Link",
			"options": "Academic Year",
			"width": 120
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": _("Submission Date"),
			"fieldname": "submission_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Assigned Verifier"),
			"fieldname": "assigned_verifier",
			"fieldtype": "Link",
			"options": "User",
			"width": 150
		}
	]


def get_data(filters: dict | None) -> list[dict]:
	"""Return data from PACE Application based on filters."""
	filters = dict(filters or {})
	query_filters = {}

	if filters.get("programme"):
		query_filters["programme"] = filters.get("programme")
	if filters.get("academic_year"):
		query_filters["academic_year"] = filters.get("academic_year")
	if filters.get("status"):
		query_filters["status"] = filters.get("status")

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["submission_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["submission_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["submission_date"] = ["<=", filters.get("to_date")]

	data = frappe.get_all(
		"PACE Application",
		filters=query_filters,
		fields=[
			"name",
			"applicant_name",
			"first_name",
			"middle_name",
			"last_name",
			"father_name",
			"mother_name",
			"email_address",
			"mobile_number",
			"date_of_birth",
			"gender",
			"nationality",
			"category",
			"address_line_1",
			"address_line_2",
			"city",
			"district",
			"state",
			"country",
			"pincode",
			"programme",
			"academic_year",
			"status",
			"submission_date",
			"assigned_verifier"
		],
		order_by="creation desc"
	)

	if data:
		# Fetch degree details for these application records
		degree_details = frappe.get_all(
			"PACE UG Degree Details",
			filters={"parent": ["in", [row.name for row in data]]},
			fields=["parent", "institution_name", "university", "programme_studied", "year_of_passing", "result_status", "obtained_percentagecgpa"]
		)
		
		# Map degrees by parent application
		degree_map = {}
		for deg in degree_details:
			if deg.parent not in degree_map:
				degree_map[deg.parent] = []
			degree_map[deg.parent].append(deg)

		# Enrich applicant records with degree details
		for row in data:
			degrees = degree_map.get(row.name, [])
			if degrees:
				primary_deg = degrees[0]
				row["ug_university"] = primary_deg.university
				row["ug_institution"] = primary_deg.institution_name
				row["ug_programme_studied"] = primary_deg.programme_studied
				row["ug_year_of_passing"] = primary_deg.year_of_passing
				row["ug_result_status"] = primary_deg.result_status
				row["ug_obtained_percentagecgpa"] = primary_deg.obtained_percentagecgpa
			else:
				row["ug_university"] = None
				row["ug_institution"] = None
				row["ug_programme_studied"] = None
				row["ug_year_of_passing"] = None
				row["ug_result_status"] = None
				row["ug_obtained_percentagecgpa"] = None

	return data


def get_report_summary(data: list[dict]) -> list[dict]:
	"""Return report summary cards."""
	if not data:
		return []

	total_count = len(data)
	total_enrolled = sum(1 for row in data if row.get("status") in ["Enrolled", "Admitted"])
	total_verification = sum(1 for row in data if row.get("status") in ["Under Verification", "Completed"])
	total_draft = sum(1 for row in data if row.get("status") == "Draft")

	return [
		{
			"value": total_count,
			"indicator": "Blue",
			"label": _("Total Applicants"),
			"datatype": "Int",
		},
		{
			"value": total_draft,
			"indicator": "Red",
			"label": _("Draft Applications"),
			"datatype": "Int",
		},
		{
			"value": total_verification,
			"indicator": "Orange",
			"label": _("Under Verification"),
			"datatype": "Int",
		},
		{
			"value": total_enrolled,
			"indicator": "Green",
			"label": _("Total Enrolled"),
			"datatype": "Int",
		}
	]
