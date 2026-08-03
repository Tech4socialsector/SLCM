import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, get_first_day, get_last_day

@frappe.whitelist()
def get_dashboard_data(filters=None):
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)

    filters = filters or {}

    # We use table aliases for joins: rr = Refund Request, ac = Admission Cancellation
    refund_conditions, refund_values = get_conditions(filters, "request_date", "rr")
    cancellation_conditions, cancellation_values = get_conditions(filters, "requested_on", "ac")

    limit_start = frappe.utils.cint(filters.get("limit_start", 0))
    limit_page_length = frappe.utils.cint(filters.get("limit_page_length", 10))

    return {
        "kpis": get_kpis(refund_conditions, refund_values, cancellation_conditions, cancellation_values),
        "charts": {
            "trend": get_refund_trend(refund_conditions, refund_values),
            "status_dist": get_status_distribution(refund_conditions, refund_values),
            "reasons": get_cancellation_reasons(cancellation_conditions, cancellation_values),
            "program_dist": get_program_distribution(refund_conditions, refund_values),
            "campus_dist": get_campus_distribution(refund_conditions, refund_values),
            "processing_time": get_avg_processing_time(refund_conditions, refund_values)
        },
        "recent_refunds": get_recent_refunds(refund_conditions, refund_values, limit_start, limit_page_length),
        "total_recent_refunds": get_recent_refunds_count(refund_conditions, refund_values)
    }

def get_conditions(filters, date_field, table_alias):
    conditions = []
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions.append(f"{table_alias}.{date_field} BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters["from_date"]
        values["to_date"] = f"{filters['to_date']} 23:59:59"

    if filters.get("campus"):
        # campus is in Admission Cancellation (ac)
        conditions.append("ac.campus = %(campus)s")
        values["campus"] = filters["campus"]

    if filters.get("program"):
        # program is in Admission Cancellation (ac)
        conditions.append("ac.program = %(program)s")
        values["program"] = filters["program"]

    if filters.get("status") and table_alias == "rr":
        conditions.append("rr.status = %(status)s")
        values["status"] = filters["status"]

    return (" AND ".join(conditions) if conditions else "1=1"), values

def get_kpis(refund_conditions, refund_values, cancellation_conditions, cancellation_values):
    # Financial KPIs
    total_refunded = frappe.db.sql(f"""
        SELECT SUM(rr.refund_amount)
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND {refund_conditions}
    """, refund_values)[0][0] or 0

    today = nowdate()
    today_values = dict(refund_values, today=today)
    refunded_today = frappe.db.sql(f"""
        SELECT SUM(rr.refund_amount)
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND DATE(rr.refund_date) = %(today)s AND {refund_conditions}
    """, today_values)[0][0] or 0

    month_start = get_first_day(today)
    month_end = get_last_day(today)
    month_values = dict(refund_values, month_start=month_start, month_end=month_end)
    refunded_this_month = frappe.db.sql(f"""
        SELECT SUM(rr.refund_amount)
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND DATE(rr.refund_date) BETWEEN %(month_start)s AND %(month_end)s AND {refund_conditions}
    """, month_values)[0][0] or 0

    # Operational Counts
    counts = frappe.db.sql(f"""
        SELECT rr.status, COUNT(rr.name) as count
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {refund_conditions}
        GROUP BY rr.status
    """, refund_values, as_dict=1)

    status_counts = {item.status: item.count for item in counts}

    # Total cancellations count
    total_cancellations = frappe.db.sql(f"""
        SELECT COUNT(ac.name)
        FROM `tabAdmission Cancellation` ac
        WHERE {cancellation_conditions}
    """, cancellation_values)[0][0] or 0

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

def get_refund_trend(conditions, values):
    return frappe.db.sql(f"""
        SELECT DATE(rr.request_date) as date, SUM(rr.refund_amount) as amount
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY DATE(rr.request_date)
        ORDER BY DATE(rr.request_date) ASC
        LIMIT 30
    """, values, as_dict=1)

def get_status_distribution(conditions, values):
    return frappe.db.sql(f"""
        SELECT rr.status as label, COUNT(rr.name) as value
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY rr.status
    """, values, as_dict=1)

def get_cancellation_reasons(conditions, values):
    data = frappe.db.sql(f"""
        SELECT ac.cancellation_reason_type as label, COUNT(ac.name) as value
        FROM `tabAdmission Cancellation` ac
        WHERE {conditions}
        GROUP BY ac.cancellation_reason_type
    """, values, as_dict=1)

    for d in data:
        if d.label:
            d.label = d.label.title()
    return data

def get_program_distribution(conditions, values):
    return frappe.db.sql(f"""
        SELECT ac.program as label, SUM(rr.refund_amount) as value
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY ac.program
        ORDER BY value DESC
        LIMIT 10
    """, values, as_dict=1)

def get_campus_distribution(conditions, values):
    return frappe.db.sql(f"""
        SELECT ac.campus as label, SUM(rr.refund_amount) as value
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        GROUP BY ac.campus
        ORDER BY value DESC
    """, values, as_dict=1)

def get_avg_processing_time(conditions, values):
    res = frappe.db.sql(f"""
        SELECT AVG(TIMESTAMPDIFF(HOUR, rr.approval_date, rr.refund_date))
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE rr.status = 'Processed' AND rr.approval_date IS NOT NULL AND rr.refund_date IS NOT NULL
        AND {conditions}
    """, values)[0][0] or 0
    return round(flt(res), 1)

def get_recent_refunds(conditions, values, limit_start=0, limit_page_length=10):
    limit_start = frappe.utils.cint(limit_start)
    limit_page_length = frappe.utils.cint(limit_page_length)
    # Manual SQL for joins
    return frappe.db.sql(f"""
        SELECT rr.name, rr.applicant, ac.program, rr.amount_paid, rr.refund_amount, rr.status, rr.request_date, rr.refund_date
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
        ORDER BY rr.creation DESC
        LIMIT {limit_page_length} OFFSET {limit_start}
    """, values, as_dict=1)

def get_recent_refunds_count(conditions, values):
    return frappe.db.sql(f"""
        SELECT COUNT(rr.name)
        FROM `tabRefund Request` rr
        JOIN `tabAdmission Cancellation` ac ON rr.admission_cancellation = ac.name
        WHERE {conditions}
    """, values)[0][0] or 0
