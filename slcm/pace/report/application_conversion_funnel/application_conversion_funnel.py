import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	# Calculate Overall Conversion (Submitted -> Admitted)
	submitted = next((d["count"] for d in data if d["status"] == "Submitted"), 0)
	enrolled = next((d["count"] for d in data if d["status"] == "Enrolled"), 0)
	
	conversion = (enrolled / submitted * 100) if submitted > 0 else 0
	
	report_summary = [
		{
			"value": conversion,
			"indicator": "Blue",
			"label": _("Overall Conversion Rate"),
			"datatype": "Percent",
		}
	]

	return columns, data, None, chart, report_summary

def get_columns():
	return [
		{
			"label": _("Stage"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Applicant Count"),
			"fieldname": "count",
			"fieldtype": "Int",
			"width": 150
		},
		{
			"label": _("Drop-off from Previous Stage"),
			"fieldname": "drop_off",
			"fieldtype": "Percent",
			"width": 200
		}
	]

def get_data(filters):
	if not filters:
		filters = {}
	conditions = ""
	values = {}

	if filters.get("academic_year"):
		conditions += " AND app.academic_year = %(academic_year)s"
		values["academic_year"] = filters.get("academic_year")

	if filters.get("programme"):
		conditions += " AND app.programme = %(programme)s"
		values["programme"] = filters.get("programme")

	# Define funnel stages in order
	stages = ['Total Applicants', 'Submitted', 'Under Review', 'Verified', 'Fee Paid', 'Enrolled']
	
	raw_counts = frappe.db.sql(f"""
		SELECT status, COUNT(name) as count
		FROM `tabPACE Application` app
		WHERE app.docstatus < 2 {conditions}
		GROUP BY status
	""", values, as_dict=1)

	counts_dict = {r["status"]: r["count"] for r in raw_counts}
	
	status_priority = {
		'Enrolled': 6,
		'Admitted': 6,
		'Converted': 6,
		'Fee Paid': 5,
		'Verified': 4,
		'Under Review': 3,
		'Under Verification': 3,
		'Completed': 3,
		'Returned for Correction': 3,
		'Submitted': 2,
		'Provisionally Submitted': 2,
		'Rejected': 2,
		'Total Applicants': 1
	}

	data = []
	prev_count = 0
	for stage in stages:
		target_priority = status_priority.get(stage, 0)
		
		if stage == 'Total Applicants':
			# Total records created
			count = sum(counts_dict.values())
		else:
			# Standard cumulative count for verified, paid, enrolled, submitted, under review
			count = sum(c for s, c in counts_dict.items() if status_priority.get(s, 0) >= target_priority)

		drop_off = 0
		if prev_count > 0:
			drop_off = ((prev_count - count) / prev_count * 100)
		
		data.append({
			"status": stage,
			"count": count,
			"drop_off": drop_off if (prev_count > 0 and stage != 'Total Applicants') else 0
		})
		prev_count = count

	return data

def get_chart(data):
	if not data:
		return None

	return {
		"data": {
			"labels": [d["status"] for d in data],
			"datasets": [
				{
					"name": _("Applicants"),
					"values": [d["count"] for d in data]
				}
			]
		},
		"type": "bar",
		"colors": ["#7cd6fd"],
		"barOptions": {
			"horizontal": 0
		}
	}
