# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt
import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {
            "label": _("Status"),
            "fieldname": "overall_status",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Count"),
            "fieldname": "count",
            "fieldtype": "Int",
            "width": 120
        }
    ]


def get_conditions(filters):
    conditions = []

    if filters.get("from_date"):
        conditions.append("date(verified_on) >= %(from_date)s")

    if filters.get("to_date"):
        conditions.append("date(verified_on) <= %(to_date)s")

    if filters.get("programme"):
        conditions.append("programme = %(programme)s")

    if filters.get("assigned_verifier"):
        conditions.append("assigned_verifier = %(assigned_verifier)s")

    return " AND ".join(conditions)


def get_data(filters):
    conditions = get_conditions(filters)

    where_clause = f"WHERE {conditions}" if conditions else ""

    data = frappe.db.sql(f"""
        SELECT
            overall_status,
            COUNT(name) as count
        FROM `tabPACE Document Verification`
        {where_clause}
        GROUP BY overall_status
    """, filters, as_dict=1)

    return data


def get_chart_data(data):
    labels = []
    values = []

    for row in data:
        labels.append(row.overall_status or "Unknown")
        values.append(row.count)

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Status Distribution",
                    "values": values
                }
            ]
        },
        "type": "pie"
    }


def get_summary(data):
    total = sum([d.count for d in data])

    return [
        {
            "label": "Total Records",
            "value": total,
            "indicator": "blue"
        }
    ]