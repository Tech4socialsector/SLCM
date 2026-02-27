import frappe
import json
from frappe import _
from frappe.utils import flt, getdate, add_days, today

@frappe.whitelist()
def get_dashboard_data(filters=None):
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    if not filters:
        filters = {}

    query_filters = []
    if filters.get("admission_year"):
        query_filters.append(f"admission_year = {frappe.db.escape(filters.get('admission_year'))}")
    if filters.get("admission_cycle"):
        query_filters.append(f"admission_cycle = {frappe.db.escape(filters.get('admission_cycle'))}")
    if filters.get("campus"):
        query_filters.append(f"campus = {frappe.db.escape(filters.get('campus'))}")
    if filters.get("program"):
        query_filters.append(f"program = {frappe.db.escape(filters.get('program'))}")
    if filters.get("reservation_category"):
        query_filters.append(f"reservation_category = {frappe.db.escape(filters.get('reservation_category'))}")

    where_clause = " WHERE docstatus < 2 " # Exclude cancelled
    if query_filters:
        where_clause += " AND " + " AND ".join(query_filters)

    # 1. Summary Cards
    summary = get_summary_cards(where_clause)

    # 2. Funnel Data
    funnel = get_funnel_data(where_clause)

    # 3. Distribution by Campus
    campus_dist = get_distribution(where_clause, "campus")

    # 4. Distribution by Program
    program_dist = get_distribution(where_clause, "program")

    # 5. Application Trend (Last 30 days)
    trend = get_application_trend(where_clause)
    
    # 6. Category wise
    category_dist = get_distribution(where_clause, "reservation_category")

    return {
        "summary": summary,
        "funnel": funnel,
        "campus_dist": campus_dist,
        "program_dist": program_dist,
        "trend": trend,
        "category_dist": category_dist
    }

def get_summary_cards(where_clause):
    sql = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN application_status NOT IN ('Draft') THEN 1 ELSE 0 END) as submitted,
            SUM(CASE WHEN application_status IN ('Selected', 'Offer Issued', 'Offer Accepted', 'Fee Paid', 'Accepted') THEN 1 ELSE 0 END) as selected,
            SUM(CASE WHEN application_status = 'Waitlisted' THEN 1 ELSE 0 END) as waitlisted,
            SUM(CASE WHEN application_status = 'Rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN application_status = 'Fee Paid' THEN 1 ELSE 0 END) as enrolled
        FROM `tabApplicant`
        {where_clause}
    """
    res = frappe.db.sql(sql, as_dict=1)[0]
    
    # Get Total Offers Issued (cumulative)
    sql_offers = f"""
        SELECT COUNT(*) FROM `tabApplicant` 
        {where_clause} AND application_status IN ('Offer Issued', 'Offer Accepted', 'Offer Declined', 'Offer Expired', 'Fee Paid')
    """
    offers_count = frappe.db.sql(sql_offers)[0][0]
    
    return {
        "total": res.total or 0,
        "submitted": res.submitted or 0,
        "selected": res.selected or 0,
        "waitlisted": res.waitlisted or 0,
        "rejected": res.rejected or 0,
        "enrolled": res.enrolled or 0,
        "offers": offers_count or 0
    }

def get_funnel_data(where_clause):
    # Stages for funnel
    stages = [
        {"label": "Submitted", "statuses": ["Submitted", "Selected", "Waitlisted", "Rejected", "Offer Accepted", "Offer Issued", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted"]},
        {"label": "Selected", "statuses": ["Selected", "Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid", "Accepted"]},
        {"label": "Offer Issued", "statuses": ["Offer Issued", "Offer Accepted", "Offer Declined", "Offer Expired", "Fee Paid"]},
        {"label": "Offer Accepted", "statuses": ["Offer Accepted", "Fee Paid", "Accepted"]},
        {"label": "Fee Paid", "statuses": ["Fee Paid"]}
    ]
    
    data = []
    for stage in stages:
        status_list = ",".join([f"'{s}'" for s in stage["statuses"]])
        count_sql = f"SELECT COUNT(*) FROM `tabApplicant` {where_clause} AND application_status IN ({status_list})"
        count = frappe.db.sql(count_sql)[0][0]
        data.append({"label": stage["label"], "count": count})
    
    return data

def get_distribution(where_clause, field):
    sql = f"""
        SELECT IFNULL({field}, 'Not Specified') as label, COUNT(*) as count
        FROM `tabApplicant`
        {where_clause}
        GROUP BY {field}
        ORDER BY count DESC
        LIMIT 10
    """
    return frappe.db.sql(sql, as_dict=1)

def get_application_trend(where_clause):
    # Last 30 days trend
    date_limit = add_days(today(), -30)
    sql = f"""
        SELECT DATE(creation) as date, COUNT(*) as count
        FROM `tabApplicant`
        {where_clause} AND creation >= '{date_limit}'
        GROUP BY DATE(creation)
        ORDER BY date ASC
    """
    return frappe.db.sql(sql, as_dict=1)
