import frappe
from frappe.utils import nowdate, add_months, getdate, format_date, add_days, get_first_day_of_week
import datetime

@frappe.whitelist()
def get_active_academic_year():
    return frappe.db.get_value("Academic Year", {"status": "Active"}, "name")

@frappe.whitelist()
def get_dashboard_data(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    
    filters = filters or {}
    
    # Default filters (empty)
    db_filters = {}
    
    if filters.get('academic_year'):
        db_filters['academic_year'] = filters.get('academic_year')
    if filters.get('programme'):
        db_filters['programme'] = filters.get('programme')
    from_date = filters.get('from_date')
    to_date = filters.get('to_date')
    if from_date and to_date:
        db_filters['creation'] = ['between', [from_date, to_date]]
    elif from_date:
        db_filters['creation'] = ['>=', from_date]
    elif to_date:
        db_filters['creation'] = ['<=', to_date]

    data = {
        "kpis": get_kpis(db_filters),
        "charts": get_charts(db_filters),
        "fee_summary": get_fee_summary(filters), # Use raw filters as get_fee_summary handles mapping
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
        SELECT 
            SUM(r.amount) as total_revenue,
            SUM(CASE WHEN r.fee_type = 'Application Fee' THEN r.amount ELSE 0 END) as application_revenue,
            SUM(CASE WHEN r.fee_type = 'Course Fee' THEN r.amount ELSE 0 END) as course_revenue
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
        
    revenue_res = frappe.db.sql(revenue_query, tuple(query_filters), as_dict=True)
    rev = revenue_res[0] if revenue_res else {}
    total_revenue = rev.get('total_revenue') or 0
    application_revenue = rev.get('application_revenue') or 0
    course_revenue = rev.get('course_revenue') or 0

    # Status breakdown for KPI Row 2
    submitted_filters = filters.copy()
    submitted_filters['status'] = ['in', ['Submitted', 'Completed']]
    under_verification_filters = filters.copy()
    under_verification_filters['status'] = 'Under Verification'
    pending_filters = filters.copy()
    pending_filters['status'] = ['in', ['Submitted', 'Completed', 'Under Verification']]
    
    fee_paid_filters = filters.copy()
    fee_paid_filters['status'] = 'Fee Paid'
    rejected_filters = filters.copy()
    rejected_filters['status'] = 'Rejected'
    returned_filters = filters.copy()
    returned_filters['status'] = 'Returned for Correction'
    
    # Unassigned Documents (Submitted applications with no verifier)
    unassigned_filters = filters.copy()
    unassigned_filters['status'] = ['in', ['Submitted', 'Completed']]
    unassigned_filters['assigned_verifier'] = ['is', 'not set']

    return {
        "total_applications": total_applications,
        "verified_apps": verified_apps,
        "total_enrolled": total_enrolled,
        "total_revenue": total_revenue,
        "application_revenue": application_revenue,
        "course_revenue": course_revenue,
        "submitted": frappe.db.count('PACE Application', submitted_filters),
        "under_verification": frappe.db.count('PACE Application', under_verification_filters),
        "pending": frappe.db.count('PACE Application', pending_filters),
        "fee_paid": frappe.db.count('PACE Application', fee_paid_filters),
        "rejected": frappe.db.count('PACE Application', rejected_filters),
        "returned": frappe.db.count('PACE Application', returned_filters),
        "unassigned": frappe.db.count('PACE Application', unassigned_filters),
        "draft_apps": frappe.db.count('PACE Application', dict(filters, status='Draft'))
    }

def get_charts(filters):
    # 1. Trend Data (Daily for last 30 days)
    trend_data = []
    for i in range(29, -1, -1):
        d = add_days(nowdate(), -i)
        count = frappe.db.count('PACE Application', dict(filters, creation=['between', [d + " 00:00:00", d + " 23:59:59"]]))
        trend_data.append({"date": format_date(d, "dd MMM"), "value": count})

    # 2. Revenue by Program
    rev_filters = filters.copy()
    rev_where = get_where_clause(rev_filters, prefix='a')
    if filters.get('creation'):
        rev_where = rev_where.replace("a.creation", "r.creation")
    
    revenue_by_program = frappe.db.sql(f"""
        SELECT a.programme as label, SUM(r.amount) as value 
        FROM `tabPACE Receipt` r
        JOIN `tabPACE Application` a ON r.pace_application = a.name
        WHERE 1=1 {rev_where}
        GROUP BY a.programme
        ORDER BY value DESC
        LIMIT 20
    """, rev_filters, as_dict=1)

    # 3. Weekly Revenue Trend (Pad with 0s to ensure line chart visibility)
    trend_filters = filters.copy()
    trend_where = get_where_clause(trend_filters, prefix='a')
    if filters.get('creation'):
        trend_where = trend_where.replace("a.creation", "r.creation")
        
    # Get last 5 Sundays
    weekly_data = []
    today = getdate(nowdate())
    for i in range(4, -1, -1):
        sunday = add_days(today, -(today.weekday() + 1) - (i * 7))
        week_label = format_date(sunday, "dd MMM")
        weekly_data.append({"label": week_label, "value": 0, "date": sunday})

    # Fetch actual data
    res = frappe.db.sql(f"""
        SELECT DATE_FORMAT(DATE_SUB(r.creation, INTERVAL DAYOFWEEK(r.creation) - 1 DAY), '%%d %%b') as label, 
               SUM(r.amount) as value,
               DATE_SUB(r.creation, INTERVAL DAYOFWEEK(r.creation) - 1 DAY) as week_start
        FROM `tabPACE Receipt` r
        JOIN `tabPACE Application` a ON r.pace_application = a.name
        WHERE 1=1 {trend_where}
        GROUP BY YEARWEEK(r.creation, 0)
        ORDER BY MIN(r.creation)
    """, trend_filters, as_dict=1)

    # Merge actual data into weekly_data
    actual_map = {row['label']: row['value'] for row in res}
    for d in weekly_data:
        if d['label'] in actual_map:
            d['value'] = actual_map[d['label']]
    
    revenue_trend = weekly_data

    # 4. Verifier Performance
    perf_filters = filters.copy()
    perf_filters['status'] = 'Verified'
    verifier_perf = frappe.db.sql(f"""
        SELECT assigned_verifier as label, COUNT(*) as value 
        FROM `tabPACE Document Verification` 
        WHERE docstatus < 2 {get_where_clause(perf_filters)}
        AND assigned_verifier IS NOT NULL AND assigned_verifier != ''
        GROUP BY assigned_verifier
        ORDER BY value DESC
        LIMIT 20
    """, perf_filters, as_dict=1)

    # 5. Program Distribution (Applications)
    sql_filters = filters.copy()
    program_dist = frappe.db.sql(f"""
        SELECT programme as label, COUNT(*) as value 
        FROM `tabPACE Application` 
        WHERE 1=1 {get_where_clause(sql_filters)}
        GROUP BY programme 
        ORDER BY value DESC 
        LIMIT 20
    """, sql_filters, as_dict=1)

    return {
        "trend": trend_data,
        "revenue_program": revenue_by_program,
        "revenue_trend": revenue_trend,
        "verifier_perf": verifier_perf,
        "program_dist": program_dist
    }

def get_fee_summary(filters):
    # Mapping for PACE Applicant Fee Assignment which uses 'program' vs 'programme'
    fa_filters = filters.copy()
    if fa_filters.get('programme'):
        fa_filters['program'] = fa_filters.get('programme')
    
    # Construct where clause for Fee Assignment
    where = ""
    if fa_filters.get('academic_year'):
        where += " AND academic_year = %(academic_year)s"
    if fa_filters.get('program'):
        where += " AND program = %(program)s"
    if fa_filters.get('from_date') and fa_filters.get('to_date'):
        where += " AND assignment_date BETWEEN %(from_date)s AND %(to_date)s"
    
    # 1. Total Assignments and Assigned Amount
    res = frappe.db.sql(f"""
        SELECT 
            COUNT(name) as total_assignments,
            SUM(final_payable_amount) as total_assigned
        FROM `tabPACE Applicant Fee Assignment`
        WHERE docstatus != 2 {where}
    """, fa_filters, as_dict=1)[0]
    
    # 2. Total Paid Amount (Ensure each receipt is counted only once)
    paid_res = frappe.db.sql(f"""
        SELECT SUM(amount) as total_paid
        FROM `tabPACE Receipt`
        WHERE pace_application IN (
            SELECT applicant 
            FROM `tabPACE Applicant Fee Assignment`
            WHERE docstatus != 2 {where}
        )
    """, fa_filters, as_dict=1)[0]

    total_assignments = res.get('total_assignments') or 0
    total_assigned = res.get('total_assigned') or 0
    total_paid = paid_res.get('total_paid') or 0
    pending_amount = total_assigned - total_paid

    return {
        "total_assignments": total_assignments,
        "total_assigned": total_assigned,
        "total_paid": total_paid,
        "pending_amount": max(0, pending_amount)
    }

def get_recent_applications(filters):
    return frappe.get_all('PACE Application',
        filters=filters,
        fields=['name', 'applicant_name', 'programme', 'status', 'creation'],
        order_by='creation desc',
        limit=5
    )

def get_pending_work(filters):
    from frappe.utils import date_diff, nowdate
    
    # Use SQL for a cleaner join to get verification record name
    where_clause = "a.status IN ('Submitted', 'Completed', 'Under Verification', 'Returned for Correction')"
    query_filters = {}
    
    if filters.get('academic_year'):
        where_clause += " AND a.academic_year = %(academic_year)s"
        query_filters['academic_year'] = filters.get('academic_year')
    if filters.get('programme'):
        where_clause += " AND a.programme = %(programme)s"
        query_filters['programme'] = filters.get('programme')
    if filters.get('creation'):
        op = filters.get('creation')[0]
        if op == 'between':
            where_clause += " AND a.creation BETWEEN %(_creation_start)s AND %(_creation_end)s"
            query_filters['_creation_start'] = filters.get('creation')[1][0]
            query_filters['_creation_end'] = filters.get('creation')[1][1]
        elif op == '>=':
            where_clause += " AND a.creation >= %(_creation_start)s"
            query_filters['_creation_start'] = filters.get('creation')[1]
        elif op == '<=':
            where_clause += " AND a.creation <= %(_creation_end)s"
            query_filters['_creation_end'] = filters.get('creation')[1]

    apps = frappe.db.sql(f"""
        SELECT 
            a.name, a.applicant_name, a.programme, a.status, a.assigned_verifier, 
            a.modified, a.creation, a.submission_date,
            v.name as verification_name
        FROM 
            `tabPACE Application` a
        LEFT JOIN 
            `tabPACE Document Verification` v ON v.application = a.name
        WHERE 
            {where_clause}
        ORDER BY a.modified DESC
        LIMIT 5
    """, query_filters, as_dict=1)
    
    pending_work = []
    today = nowdate()
    
    for app in apps:
        # Use verification record creation if it exists (task age)
        # Fallback to application creation if no verification record yet
        verification_creation = None
        if app.verification_name:
            verification_creation = frappe.db.get_value("PACE Document Verification", app.verification_name, "creation")
            
        base_date = verification_creation or app.submission_date or app.creation
        
        days_pending = date_diff(today, base_date) + 1
        
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

def get_where_clause(filters, prefix=""):
    p = f"{prefix}." if prefix else ""
    clause = ""
    if filters.get('academic_year'):
        clause += f" AND {p}academic_year = %(academic_year)s"
    if filters.get('programme'):
        clause += f" AND {p}programme = %(programme)s"
    
    status = filters.get('status')
    if status:
        if isinstance(status, list):
            if status[0] == '!=':
                clause += f" AND {p}status != %(status_val)s"
                filters['status_val'] = status[1]
            elif status[0] == 'in':
                placeholders = []
                for i, s in enumerate(status[1]):
                    key = f"status_in_{i}"
                    filters[key] = s
                    placeholders.append(f"%({key})s")
                clause += f" AND {p}status IN ({', '.join(placeholders)})"
        else:
            clause += f" AND {p}status = %(status)s"

    if filters.get('creation') and isinstance(filters.get('creation'), list):
        op = filters.get('creation')[0]
        if op == 'between' and len(filters.get('creation')) > 1:
            filters['_creation_start'] = filters.get('creation')[1][0]
            filters['_creation_end'] = filters.get('creation')[1][1]
            clause += f" AND {p}creation BETWEEN %(_creation_start)s AND %(_creation_end)s"
        elif op == '>=':
            filters['_creation_start'] = filters.get('creation')[1]
            clause += f" AND {p}creation >= %(_creation_start)s"
        elif op == '<=':
            filters['_creation_end'] = filters.get('creation')[1]
            clause += f" AND {p}creation <= %(_creation_end)s"
    return clause

@frappe.whitelist()
def get_document_verifiers():
    # Ignore permissions to allow non-managers to fetch the dropdown list
    roles = ["Document Verifier", "PACE Admission Manager", "PACE Manager"]
    verifiers = frappe.get_all(
        "Has Role",
        filters={"role": ["in", roles]},
        pluck="parent",
        ignore_permissions=True
    )
    return list(set(verifiers))


@frappe.whitelist()
def get_verifier_users_for_link(doctype, txt, searchfield, start, page_len, filters):
    roles = ["Document Verifier", "PACE Admission Manager", "PACE Manager"]
    users = frappe.get_all(
        "Has Role",
        filters={"role": ["in", roles]},
        pluck="parent",
        ignore_permissions=True
    )
    unique_users = list(set(users))
    if not unique_users:
        return []

    query = """
        SELECT name, full_name 
        FROM `tabUser` 
        WHERE name IN %(users)s 
          AND enabled = 1
    """
    params = {"users": unique_users}
    if txt:
        query += " AND (name LIKE %(txt)s OR full_name LIKE %(txt)s)"
        params["txt"] = f"%{txt}%"

    query += f" ORDER BY name LIMIT {int(page_len)} OFFSET {int(start)}"
    return frappe.db.sql(query, params, as_list=True)


