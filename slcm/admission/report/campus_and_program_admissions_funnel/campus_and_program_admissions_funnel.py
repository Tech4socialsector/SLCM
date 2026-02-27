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
        {"label": _("Admission Cycle"), "fieldname": "admission_cycle", "fieldtype": "Link", "options": "Admission Cycle", "width": 150},
        {"label": _("Campus"), "fieldname": "campus", "fieldtype": "Link", "options": "Campus", "width": 150},
        {"label": _("Program"), "fieldname": "program", "fieldtype": "Link", "options": "Program", "width": 150},
        {"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 180},
        {"label": _("Count"), "fieldname": "count", "fieldtype": "Int", "width": 100},
        {"label": _("Conversion Rate"), "fieldname": "conversion", "fieldtype": "Percent", "width": 150}
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
    
    # Get aggregated counts from DB
    sql = f"""
        SELECT 
            admission_cycle,
            campus, 
            program, 
            application_status, 
            COUNT(*) as count 
        FROM `tabApplicant` 
        {where_clause}
        GROUP BY admission_cycle, campus, program, application_status
    """
    results = frappe.db.sql(sql, as_dict=1)

    # Dictionary to store status counts per (campus, program)
    groups = {}
    for res in results:
        key = (res.admission_cycle or "Unknown", res.campus or "Unknown", res.program or "Unknown")
        if key not in groups:
            groups[key] = {}
        
        status = res.application_status
        if status == "Draft":
            continue
        
        groups[key][status] = groups[key].get(status, 0) + res.count

    # Define stages and how they are calculated (Cumulative logic for funnel)
    # Submitted: Any status except Draft
    # Selected: Selected, Offer Issued, Offer Accepted, Offer Declined, Offer Expired, Fee Paid
    # Offer Issued: Offer Issued, Offer Accepted, Offer Declined, Offer Expired, Fee Paid
    # Offer Accepted: Offer Accepted, Fee Paid
    # Fee Paid: Fee Paid
    
    # Stages for the report
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

    data = []
    for key in sorted(groups.keys()):
        admission_cycle, campus, program = key
        status_map = groups[key]
        
        # Calculate counts for each report stage
        calculated_counts = {}
        for stage in report_stages:
            total = 0
            for status in stage["statuses"]:
                total += status_map.get(status, 0)
            calculated_counts[stage["label"]] = total

        # Build data rows
        for stage in report_stages:
            label = stage["label"]
            count = calculated_counts[label]
            parent = stage.get("parent")
            
            conversion = None
            if parent and calculated_counts.get(parent, 0) > 0:
                conversion = round((count / calculated_counts[parent]) * 100, 1)
            elif parent:
                conversion = 0.0
            
            row = {
                "admission_cycle": admission_cycle,
                "campus": campus,
                "program": program,
                "stage": label,
                "count": count,
                "conversion": conversion
            }
            data.append(row)
        
        # Add an empty row between groups
        data.append({})

    return data
