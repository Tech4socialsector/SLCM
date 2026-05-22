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

    # Comprehensive groupings for statuses
    all_submitted = list(status_map.keys())
    all_selected = ["Selected", "Merit Selected", "Seat Selected", "Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted", "Enrolled"]
    all_waitlisted = ["Waitlisted", "Merit Waitlisted", "Seat Waitlisted"]
    all_rejected = ["Rejected", "Entrance Test Rejected", "Interview Rejected", "Merit Rejected", "Seat Rejected"]
    all_withdrawn = ["Withdrawn"]
    all_offered = ["Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted", "Enrolled"]
    all_accepted = ["Offer Accepted", "Fee Paid", "Accepted", "Enrolled"]
    all_declined = ["Offer Declined"]
    all_expired = ["Offer Expired"]
    all_fee_paid = ["Fee Paid", "Enrolled"]

    # Define all stages for the report
    report_stages = [
        {"label": _("Submitted"), "statuses": all_submitted},
        {"label": _("Selected"), "statuses": all_selected, "parent": _("Submitted")},
        {"label": _("Waitlist"), "statuses": all_waitlisted, "parent": _("Submitted")},
        {"label": _("Rejected"), "statuses": all_rejected, "parent": _("Submitted")},
        {"label": _("Withdrawn"), "statuses": all_withdrawn, "parent": _("Submitted")},
        {"label": _("Offered"), "statuses": all_offered, "parent": _("Selected")},
        {"label": _("Accepted"), "statuses": all_accepted, "parent": _("Offered")},
        {"label": _("Declined"), "statuses": all_declined, "parent": _("Offered")},
        {"label": _("Expired"), "statuses": all_expired, "parent": _("Offered")},
        {"label": _("Fee Paid"), "statuses": all_fee_paid, "parent": _("Accepted")}
    ]

    # Calculate counts for each report stage
    calculated_counts = {}
    total_submitted = 0
    for stage in report_stages:
        total = 0
        for status in stage["statuses"]:
            total += status_map.get(status, 0)
        calculated_counts[stage["label"]] = total
        if stage["label"] == _("Submitted"):
            total_submitted = total

    data = []
    for stage in report_stages:
        label = stage["label"]
        count = calculated_counts[label]
        
        conversion = 0.0
        if total_submitted > 0:
            conversion = round((count / total_submitted) * 100, 2)
        elif not stage.get("parent"): # Root stage
             conversion = 100.0
        
        data.append({
            "stage": label,
            "count": count,
            "conversion": conversion
        })

    return data
