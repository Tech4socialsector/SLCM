import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 250},
        {"label": _("Count"), "fieldname": "count", "fieldtype": "Int", "width": 120},
        {"label": _("Conversion Rate (to next stage)"), "fieldname": "conversion", "fieldtype": "Percent", "width": 250}
    ]

def get_data(filters):
    query_filters = []
    if filters.get("admission_cycle"):
        query_filters.append(f"admission_cycle = {frappe.db.escape(filters.get('admission_cycle'))}")
    if filters.get("campus"):
        query_filters.append(f"campus = {frappe.db.escape(filters.get('campus'))}")
    if filters.get("program"):
        query_filters.append(f"program = {frappe.db.escape(filters.get('program'))}")

    where_clause = " WHERE " + " AND ".join(query_filters) if query_filters else ""
    
    # Get aggregated counts from DB - Summing everything for a single funnel
    sql = f"""
        SELECT 
            application_status, 
            COUNT(*) as count 
        FROM `tabApplicant` 
        {where_clause}
        GROUP BY application_status
    """
    results = frappe.db.sql(sql, as_dict=1)

    # Simplified status map for the whole filtered scope
    status_map = {}
    for res in results:
        status = res.application_status
        if status == "Draft":
            continue
        status_map[status] = status_map.get(status, 0) + res.count

    # Define stages for the report
    report_stages = [
        {"label": "Submitted", "statuses": ["Submitted", "Selected", "Waitlisted", "Rejected", "Offer Accepted", "Offer Issued", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted"]},
        {"label": "Selected", "statuses": ["Selected", "Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted"], "parent": "Submitted"},
        {"label": "Waitlisted", "statuses": ["Waitlisted"], "parent": "Submitted"},
        {"label": "Rejected", "statuses": ["Rejected"], "parent": "Submitted"},
        {"label": "Offer Issued", "statuses": ["Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid"], "parent": "Selected"},
        {"label": "Offer Accepted", "statuses": ["Offer Accepted", "Fee Paid", "Accepted"], "parent": "Offer Issued"},
        {"label": "Offer Declined", "statuses": ["Offer Declined"], "parent": "Offer Issued"},
        {"label": "Offer Expired", "statuses": ["Offer Expired"], "parent": "Offer Issued"},
        {"label": "Fee Paid", "statuses": ["Fee Paid"], "parent": "Offer Accepted"}
    ]

    # Calculate counts for each report stage
    calculated_counts = {}
    for stage in report_stages:
        total = 0
        for status in stage["statuses"]:
            total += status_map.get(status, 0)
        calculated_counts[stage["label"]] = total

    data = []
    for stage in report_stages:
        label = stage["label"]
        count = calculated_counts[label]
        parent = stage.get("parent")
        
        conversion = None
        if parent and calculated_counts.get(parent, 0) > 0:
            conversion = (count / calculated_counts[parent]) * 100
        elif not parent: # Root stage
             conversion = 100.0
        else:
            conversion = 0.0
        
        data.append({
            "stage": label,
            "count": count,
            "conversion": conversion
        })

    return data
