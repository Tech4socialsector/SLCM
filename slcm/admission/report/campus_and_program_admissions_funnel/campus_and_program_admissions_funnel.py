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

    # Define all 9 stages for the report
    report_stages = [
        {"label": _("Submitted"), "statuses": ["Submitted", "Selected", "Waitlisted", "Rejected", "Offer Accepted", "Offer Issued", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted"]},
        {"label": _("Selected"), "statuses": ["Selected", "Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted"], "parent": _("Submitted")},
        {"label": _("Waitlist"), "statuses": ["Waitlisted"], "parent": _("Submitted")},
        {"label": _("Rejected"), "statuses": ["Rejected"], "parent": _("Submitted")},
        {"label": _("Offered"), "statuses": ["Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid"], "parent": _("Selected")},
        {"label": _("Accepted"), "statuses": ["Offer Accepted", "Fee Paid", "Accepted"], "parent": _("Offered")},
        {"label": _("Declined"), "statuses": ["Offer Declined"], "parent": _("Offered")},
        {"label": _("Expired"), "statuses": ["Offer Expired"], "parent": _("Offered")},
        {"label": _("Fee Paid"), "statuses": ["Fee Paid"], "parent": _("Accepted")}
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
        
        conversion = 0.0
        if parent and calculated_counts.get(parent, 0) > 0:
            conversion = round((count / calculated_counts[parent]) * 100, 2)
        elif not parent: # Root stage
             conversion = 100.0
        
        data.append({
            "stage": label,
            "count": count,
            "conversion": conversion
        })

    return data
