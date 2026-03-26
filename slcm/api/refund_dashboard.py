import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, get_first_day, get_last_day

@frappe.whitelist()
def get_dashboard_data(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    
    filters = filters or {}
    
    # We use table aliases for joins: rr = Refund Request, ac = Admission Cancellation
    refund_conditions = get_conditions(filters, "request_date", "rr")
    cancellation_conditions = get_conditions(filters, "requested_on", "ac")
    
    return {
        "kpis": get_kpis(refund_conditions, cancellation_conditions),
        "charts": {
            "trend": get_refund_trend(refund_conditions),
            "status_dist": get_status_distribution(refund_conditions),
            "reasons": get_cancellation_reasons(cancellation_conditions),
            "program_dist": get_program_distribution(refund_conditions),
            "campus_dist": get_campus_distribution(refund_conditions),
            "processing_time": get_avg_processing_time(refund_conditions)
        },
        "recent_refunds": get_recent_refunds(refund_conditions)
    }

def get_conditions(filters, date_field, table_alias):
    conditions = []
    
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append(f"{table_alias}.{date_field} BETWEEN '{filters['from_date']}' AND '{filters['to_date']} 23:59:59'")
    
    if filters.get("campus"):
        # campus is in Admission Cancellation (ac)
        conditions.append(f"ac.campus = '{filters['campus']}'")
        
    if filters.get("program"):
        # program is in Admission Cancellation (ac)
        conditions.append(f"ac.program = '{filters['program']}'")
        
    if filters.get("status") and table_alias == "rr":
        conditions.append(f"rr.status = '{filters['status']}'")
        
    return " AND ".join(conditions) if conditions else "1=1"

def get_kpis(refund_conditions, cancellation_conditions):
    # Financial KPIs
    total_refunded = frappe.db.sql(f"""
        SELECT SUM(rr.refund_amount) 
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND {refund_conditions}
    """)[0][0] or 0

    today = nowdate()
    refunded_today = frappe.db.sql(f"""
        SELECT SUM(rr.refund_amount) 
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND DATE(rr.refund_date) = '{today}' AND {refund_conditions}
    """)[0][0] or 0

    month_start = get_first_day(today)
    month_end = get_last_day(today)
    refunded_this_month = frappe.db.sql(f"""
        SELECT SUM(rr.refund_amount) 
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND DATE(rr.refund_date) BETWEEN '{month_start}' AND '{month_end}' AND {refund_conditions}
    """)[0][0] or 0

    # Operational Counts
    counts = frappe.db.sql(f"""
        SELECT rr.status, COUNT(rr.name) as count
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {refund_conditions}
        GROUP BY rr.status
    """, as_dict=1)
    
    status_counts = {item.status: item.count for item in counts}

    # Total cancellations count
    total_cancellations = frappe.db.sql(f"""
        SELECT COUNT(ac.name) 
        FROM `tabAdmission Cancellation` ac
        WHERE {cancellation_conditions}
    """)[0][0] or 0

    return {
        "total_refund_amount": total_refunded,
        "refunded_today": refunded_today,
        "refunded_this_month": refunded_this_month,
        "total_requests": sum(status_counts.values()),
        "draft": status_counts.get("Draft", 0),
        "review": status_counts.get("Under Review", 0),
        "approved": status_counts.get("Approved", 0),
        "processed": status_counts.get("Processed", 0),
        "failed": status_counts.get("Failed", 0),
        "total_cancellations": total_cancellations
    }

def get_refund_trend(conditions):
    return frappe.db.sql(f"""
        SELECT DATE(rr.request_date) as date, SUM(rr.refund_amount) as amount
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY DATE(rr.request_date)
        ORDER BY DATE(rr.request_date) ASC
        LIMIT 30
    """, as_dict=1)

def get_status_distribution(conditions):
    return frappe.db.sql(f"""
        SELECT rr.status as label, COUNT(rr.name) as value
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY rr.status
    """, as_dict=1)

def get_cancellation_reasons(conditions):
    data = frappe.db.sql(f"""
        SELECT ac.cancellation_reason_type as label, COUNT(ac.name) as value
        FROM `tabAdmission Cancellation` ac
        WHERE {conditions}
        GROUP BY ac.cancellation_reason_type
    """, as_dict=1)
    
    for d in data:
        if d.label:
            d.label = d.label.title()
    return data

def get_program_distribution(conditions):
    return frappe.db.sql(f"""
        SELECT ac.program as label, SUM(rr.refund_amount) as value
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY ac.program
        ORDER BY value DESC
        LIMIT 10
    """, as_dict=1)

def get_campus_distribution(conditions):
    return frappe.db.sql(f"""
        SELECT ac.campus as label, SUM(rr.refund_amount) as value
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY ac.campus
        ORDER BY value DESC
    """, as_dict=1)

def get_avg_processing_time(conditions):
    res = frappe.db.sql(f"""
        SELECT AVG(TIMESTAMPDIFF(HOUR, rr.approval_date, rr.refund_date))
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND rr.approval_date IS NOT NULL AND rr.refund_date IS NOT NULL
        AND {conditions}
    """)[0][0] or 0
    return round(flt(res), 1)

def get_recent_refunds(conditions):
    # Manual SQL for joins
    return frappe.db.sql(f"""
        SELECT rr.name, rr.applicant, ac.program, rr.amount_paid, rr.refund_amount, rr.status, rr.request_date, rr.refund_date
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        ORDER BY rr.creation DESC
        LIMIT 10
    """, as_dict=1)
