import frappe
from frappe.utils import nowdate, add_months, getdate, format_date, add_days

@frappe.whitelist()
def get_dashboard_data(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    
    filters = filters or {}
    
    db_filters = {}
    if filters.get('academic_year'):
        db_filters['academic_year'] = filters.get('academic_year')
    if filters.get('programme'):
        db_filters['programme'] = filters.get('programme')
    if filters.get('from_date') and filters.get('to_date'):
        db_filters['creation'] = ['between', [filters.get('from_date'), filters.get('to_date')]]

    data = {
        "kpis": get_kpis(db_filters),
        "charts": get_charts(db_filters),
        "recent_applications": get_recent_applications(db_filters),
        "pending_work": get_pending_work(db_filters)
    }
    
    return data

def get_kpis(filters):
    # Total Metrics
    total_applications = frappe.db.count('PACE Application', filters)
    
    verified_filters = filters.copy()
    verified_filters['status'] = 'Verified'
    verified_apps = frappe.db.count('PACE Application', verified_filters)
    
    admitted_filters = filters.copy()
    admitted_filters['status'] = ['in', ['Admitted', 'Enrolled']]
    total_enrolled = frappe.db.count('PACE Application', admitted_filters)
    
    # Revenue
    revenue_query = """
        SELECT SUM(r.amount) 
        FROM `tabPACE Receipt` r
        JOIN `tabPACE Application` a ON r.pace_application = a.name
        WHERE 1=1
    """
    query_filters = []
    if filters.get('academic_year'):
        revenue_query += " AND a.academic_year = %s"
        query_filters.append(filters.get('academic_year'))
    if filters.get('programme'):
        revenue_query += " AND a.programme = %s"
        query_filters.append(filters.get('programme'))
    if filters.get('creation'):
        revenue_query += " AND a.creation BETWEEN %s AND %s"
        query_filters.append(filters.get('creation')[1][0])
        query_filters.append(filters.get('creation')[1][1])
        
    revenue_res = frappe.db.sql(revenue_query, tuple(query_filters))
    total_revenue = revenue_res[0][0] if revenue_res and revenue_res[0][0] else 0

    # Status breakdown for KPI Row 2
    submitted_filters = filters.copy()
    submitted_filters['status'] = 'Submitted'
    under_verification_filters = filters.copy()
    under_verification_filters['status'] = 'Under Verification'
    pending_filters = filters.copy()
    pending_filters['status'] = ['in', ['Submitted', 'Under Verification']]
    
    fee_paid_filters = filters.copy()
    fee_paid_filters['status'] = 'Fee Paid'
    rejected_filters = filters.copy()
    rejected_filters['status'] = 'Rejected'
    returned_filters = filters.copy()
    returned_filters['status'] = 'Returned for Correction'
    
    # Unassigned Documents (Submitted applications with no verifier)
    unassigned_filters = filters.copy()
    unassigned_filters['status'] = 'Submitted'
    unassigned_filters['assigned_verifier'] = ['is', 'not set']

    return {
        "total_applications": total_applications,
        "verified_apps": verified_apps,
        "total_enrolled": total_enrolled,
        "total_revenue": total_revenue,
        "submitted": frappe.db.count('PACE Application', submitted_filters),
        "under_verification": frappe.db.count('PACE Application', under_verification_filters),
        "pending": frappe.db.count('PACE Application', pending_filters),
        "fee_paid": frappe.db.count('PACE Application', fee_paid_filters),
        "rejected": frappe.db.count('PACE Application', rejected_filters),
        "returned": frappe.db.count('PACE Application', returned_filters),
        "unassigned": frappe.db.count('PACE Application', unassigned_filters)
    }

def get_charts(filters):
    # 1. Funnel Data
    funnel_labels = ['Applications', 'Submitted', 'Verified', 'Fee Paid', 'Students']
    funnel_values = [
        frappe.db.count('PACE Application', filters),
        frappe.db.count('PACE Application', dict(filters, status=['!=', 'Draft'])),
        frappe.db.count('PACE Application', dict(filters, status='Verified')),
        frappe.db.count('PACE Application', dict(filters, status='Fee Paid')),
        frappe.db.count('PACE Application', dict(filters, status=['in', ['Admitted', 'Enrolled']]))
    ]
    
    # 2. Trend Data (Daily for last 30 days)
    trend_data = []
    for i in range(29, -1, -1):
        d = add_days(nowdate(), -i)
        count = frappe.db.count('PACE Application', dict(filters, creation=['between', [d + " 00:00:00", d + " 23:59:59"]]))
        trend_data.append({"date": format_date(d, "dd MMM"), "value": count})

    # 3. Status Distribution
    status_dist = frappe.db.sql(f"""
        SELECT status as label, COUNT(*) as value 
        FROM `tabPACE Application` 
        WHERE 1=1 {get_where_clause(filters)}
        GROUP BY status
    """, filters, as_dict=1)

    # 4. Program Distribution
    program_dist = frappe.db.sql(f"""
        SELECT programme as label, COUNT(*) as value 
        FROM `tabPACE Application` 
        WHERE 1=1 {get_where_clause(filters)}
        GROUP BY programme 
        ORDER BY value DESC 
        LIMIT 10
    """, filters, as_dict=1)

    return {
        "funnel": {"labels": funnel_labels, "values": funnel_values},
        "trend": trend_data,
        "status_dist": status_dist,
        "program_dist": program_dist
    }

def get_recent_applications(filters):
    return frappe.get_all('PACE Application',
        filters=filters,
        fields=['name', 'applicant_name', 'programme', 'status', 'creation'],
        order_by='creation desc',
        limit=10
    )

def get_pending_work(filters):
    from frappe.utils import date_diff, nowdate
    
    # Use SQL for a cleaner join to get verification record name
    where_clause = "a.status IN ('Submitted', 'Under Verification', 'Returned for Correction')"
    query_filters = {}
    
    if filters.get('academic_year'):
        where_clause += " AND a.academic_year = %(academic_year)s"
        query_filters['academic_year'] = filters.get('academic_year')
    if filters.get('programme'):
        where_clause += " AND a.programme = %(programme)s"
        query_filters['programme'] = filters.get('programme')
    if filters.get('creation'):
        where_clause += " AND a.creation BETWEEN %(_creation_start)s AND %(_creation_end)s"
        query_filters['_creation_start'] = filters.get('creation')[1][0]
        query_filters['_creation_end'] = filters.get('creation')[1][1]

    apps = frappe.db.sql(f"""
        SELECT 
            a.name, a.applicant_name, a.programme, a.status, a.assigned_verifier, a.modified,
            v.name as verification_name
        FROM 
            `tabPACE Application` a
        LEFT JOIN 
            `tabPACE Document Verification` v ON v.application = a.name
        WHERE 
            {where_clause}
        ORDER BY a.modified DESC
        LIMIT 50
    """, query_filters, as_dict=1)
    
    pending_work = []
    today = nowdate()
    
    for app in apps:
        days_pending = date_diff(today, app.modified)
        
        # Priority Logic:
        # High: days pending >= 4 OR status = Rejected/Returned
        # Medium: days pending 2-3 OR status = Payment Pending (Mapped to Verified)
        # Low: days pending <= 1
        
        priority = "Low"
        if days_pending >= 4 or app.status in ["Rejected", "Returned for Correction"]:
            priority = "High"
        elif (2 <= days_pending <= 3) or app.status == "Verified":
            priority = "Medium"
            
        pending_work.append({
            "name": app.name,
            "verification_name": app.verification_name,
            "applicant_name": app.applicant_name,
            "programme": app.programme,
            "status": app.status,
            "priority": priority,
            "assigned_to": app.assigned_verifier,
            "days_pending": days_pending,
            "last_action": app.modified
        })
        
    # Sort by priority: High (0), Medium (1), Low (2)
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    pending_work.sort(key=lambda x: priority_order.get(x['priority'], 3))
    
    return pending_work

def get_where_clause(filters):
    clause = ""
    if filters.get('academic_year'):
        clause += " AND academic_year = %(academic_year)s"
    if filters.get('programme'):
        clause += " AND programme = %(programme)s"
    if filters.get('creation') and isinstance(filters.get('creation'), list) and len(filters.get('creation')) > 1:
        # Handle ['between', [start, end]]
        filters['_creation_start'] = filters.get('creation')[1][0]
        filters['_creation_end'] = filters.get('creation')[1][1]
        clause += " AND creation BETWEEN %(_creation_start)s AND %(_creation_end)s"
    return clause
