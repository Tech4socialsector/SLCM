import frappe
from frappe import _

def execute(filters=None):
	if not filters:
		filters = {}
		
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	
	return columns, data, None, chart

def get_columns():
	return [
		{
			"label": _("Country"),
			"fieldname": "country",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("State"),
			"fieldname": "state",
			"fieldtype": "Link",
			"options": "State",
			"width": 150
		},
		{
			"label": _("City"),
			"fieldname": "city",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Total Applications"),
			"fieldname": "total_applications",
			"fieldtype": "Int",
			"width": 150
		}
	]

def get_data(filters):
	conditions = []
	values = {}
	
	if filters.get("state"):
		conditions.append("state = %(state)s")
		values["state"] = filters.get("state")
		
	if filters.get("country"):
		conditions.append("country = %(country)s")
		values["country"] = filters.get("country")
		
	where_clause = ""
	if conditions:
		where_clause = " AND " + " AND ".join(conditions)
		
	query = f"""
		SELECT 
			IFNULL(country, 'Unknown') as country, 
			IFNULL(state, 'Unknown') as state, 
			IFNULL(city, 'Unknown') as city, 
			COUNT(name) as total_applications
		FROM `tabApplicant`
		WHERE docstatus < 2
		{where_clause}
		GROUP BY country, state, city
		ORDER BY total_applications DESC, country ASC, state ASC, city ASC
	"""
	
	return frappe.db.sql(query, values, as_dict=True)

def get_chart(data):
	if not data:
		return None
		
	labels = []
	values = []
	
	# Show top 15 regions by volume
	for row in data[:15]:
		# Prioritize city, then state, then country for the chart label
		label_parts = []
		if row.city and row.city != 'Unknown':
			label_parts.append(row.city)
		if row.state and row.state != 'Unknown':
			label_parts.append(row.state)
		if row.country and row.country != 'Unknown':
			label_parts.append(row.country)
			
		label = ", ".join(label_parts) if label_parts else _("Unknown")
		labels.append(label)
		values.append(row.total_applications)
		
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Applications"),
					"values": values
				}
			]
		},
		"type": "bar",
		"colors": ["#4f46e5"]
	}
