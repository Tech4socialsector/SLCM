# Copyright (c) 2026
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}

	group_field, label = get_group_field_and_label(filters)

	columns = get_columns(label)
	data = get_data(filters, group_field)
	chart = get_chart_data(data, label)

	return columns, data, None, chart


def get_group_field_and_label(filters):
	country = filters.get("country")
	state = filters.get("state")

	if not country:
		return "country", "Country"
	if country and not state:
		return "state", "State"
	# country + state set (district may or may not be set)
	return "district", "City"


def get_columns(label):
	return [
		{
			"label": label,
			"fieldname": "geography",
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"label": "Applications",
			"fieldname": "applications",
			"fieldtype": "Int",
			"width": 150,
		},
	]


def get_data(filters, group_field):
	conditions, values = get_conditions(filters, group_field)

	country = filters.get("country")
	state = filters.get("state")
	
	select_field = f"`{group_field}`"
	
	# If grouping by a field, verify it actually belongs to the filtered parent.
	# Otherwise, bucket it into 'Unspecified' so we don't drop the row and mess up totals.
	if group_field == "district" and state and state != "Others":
		select_field = f"IF((SELECT COUNT(*) FROM `tabCity` WHERE name = `tabPACE Application`.district AND state = %(state)s) > 0, `tabPACE Application`.district, '')"
	elif group_field == "state" and country and country == "India":
		select_field = f"IF((SELECT COUNT(*) FROM `tabState` WHERE name = `tabPACE Application`.state AND country = %(country)s) > 0, `tabPACE Application`.state, '')"

	query = f"""
		SELECT
			IFNULL(NULLIF({select_field}, ''), 'Unspecified') AS geography,
			COUNT(*) AS applications
		FROM `tabPACE Application`
		WHERE 1=1
			{conditions}
		GROUP BY geography
		ORDER BY applications DESC
	"""

	return frappe.db.sql(query, values, as_dict=True)


def get_conditions(filters, group_field):
	conditions = ""
	values = {}

	country = filters.get("country")
	state = filters.get("state")
	district = filters.get("district")

	if country:
		conditions += " AND `country` = %(country)s"
		values["country"] = country

	if state:
		conditions += " AND `state` = %(state)s"
		values["state"] = state

	if district:
		conditions += " AND `district` = %(district)s"
		values["district"] = district

	return conditions, values


def get_chart_data(data, label):
	if not data:
		return None

	labels = [row["geography"] for row in data]
	values = [row["applications"] for row in data]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": "Applications",
					"values": values,
				}
			],
		},
		"type": "bar",
		"colors": ["#a56bdb"]
	}