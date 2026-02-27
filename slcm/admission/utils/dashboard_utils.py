import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_years

def get_applicant_filters(filters):
    """Common filter processor for Admission Dashboard"""
    query_filters = {"docstatus": ["<", 2]} # Exclude cancelled
    
    if filters.get("admission_year"):
        query_filters["admission_year"] = filters.get("admission_year")
    if filters.get("admission_cycle"):
        query_filters["admission_cycle"] = filters.get("admission_cycle")
    if filters.get("program"):
        query_filters["program"] = filters.get("program")
    
    # Handle Department (Program link)
    if filters.get("department"):
        programs = frappe.get_all("Program", filters={"department": filters.get("department")}, pluck="name")
        if programs:
            query_filters["program"] = ["in", programs]
        else:
            query_filters["program"] = "___NONE___"

    # Handle Degree Type (Program link)
    if filters.get("degree_type"):
        programs = frappe.get_all("Program", filters={"program_level": filters.get("degree_type")}, pluck="name")
        if programs:
            if "program" in query_filters and isinstance(query_filters["program"], list):
                # Intersection if already filtered by dept
                query_filters["program"] = ["in", list(set(query_filters["program"][1]) & set(programs))]
            else:
                query_filters["program"] = ["in", programs]
                
    if filters.get("gender"):
        query_filters["gender"] = filters.get("gender")
    if filters.get("nationality"):
        query_filters["nationality"] = filters.get("nationality")
        
    return query_filters

@frappe.whitelist()
def get_card_value(filters, status_filter=None):
    """Utility for Number Cards"""
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)
        
    query_filters = get_applicant_filters(filters)
    
    if status_filter:
        if isinstance(status_filter, list):
            query_filters["application_status"] = ["in", status_filter]
        else:
            query_filters["application_status"] = status_filter
    elif "application_status" not in query_filters:
        # Default: everything except Draft if not specified
        query_filters["application_status"] = ["!=", "Draft"]
    return {
        "value": frappe.db.count("Applicant", query_filters),
        "fieldtype": "Int"
    }

@frappe.whitelist()
def get_total_applications(filters): return get_card_value(filters)

@frappe.whitelist()
def get_selected_count(filters): return get_card_value(filters, "Selected")

@frappe.whitelist()
def get_waitlisted_count(filters): return get_card_value(filters, "Waitlisted")

@frappe.whitelist()
def get_rejected_count(filters): return get_card_value(filters, "Rejected")

@frappe.whitelist()
def get_offer_accepted_count(filters): return get_card_value(filters, "Offer Accepted")

@frappe.whitelist()
def get_offer_issued_count(filters): return get_card_value(filters, "Offer Issued")

@frappe.whitelist()
def get_offer_declined_count(filters): return get_card_value(filters, "Offer Declined")

@frappe.whitelist()
def get_offer_expired_count(filters): return get_card_value(filters, "Offer Expired")

@frappe.whitelist()
def get_fee_paid_count(filters): return get_card_value(filters, "Fee Paid")

@frappe.whitelist()
def get_enrolled_count(filters): return get_card_value(filters, ["Enrollment Confirmed", "Accepted"])

@frappe.whitelist()
def get_admission_pipeline_data(charts_filters=None):
    """Source for Admission Funnel Chart"""
    filters = charts_filters or {}
    query_filters = get_applicant_filters(filters)
    
    stages = [
        {"label": _("Applied"), "status": ["!=", "Draft"]},
        {"label": _("Selected"), "status": "Selected"},
        {"label": _("Rejected"), "status": "Rejected"},
        {"label": _("Waitlisted"), "status": "Waitlisted"},
        {"label": _("Offer Issued"), "status": "Offer Issued"},
        {"label": _("Offer Accepted"), "status": "Offer Accepted"},
        {"label": _("Offer Declined"), "status": "Offer Declined"},
        {"label": _("Offer Expired"), "status": "Offer Expired"},
        {"label": _("Fee Paid"), "status": "Fee Paid"},
        {"label": _("Enrollment Confirmed"), "status": ["in", ["Enrollment Confirmed", "Accepted"]]}
    ]
    
    labels = []
    values = []
    
    for stage in stages:
        sf = stage["status"]
        temp_filters = query_filters.copy()
        if isinstance(sf, list):
            temp_filters["application_status"] = sf
        else:
            temp_filters["application_status"] = sf
            
        count = frappe.db.count("Applicant", temp_filters)
        labels.append(stage["label"])
        values.append(count)
        
    return {
        "labels": labels,
        "datasets": [{"name": _("Applicants"), "values": values}]
    }

@frappe.whitelist()
def get_application_trend_data(charts_filters=None):
    """Source for Application Trend (Line Chart)"""
    filters = charts_filters or {}
    query_filters = get_applicant_filters(filters)
    
    # Defaults to last 6 months if not specified
    from frappe.utils import add_months, get_first_day, get_last_day
    
    labels = []
    values = []
    
    # Simple month-wise trend for the current year or last 6 months
    for i in range(5, -1, -1):
        date = add_months(nowdate(), -i)
        month_label = getdate(date).strftime("%b %Y")
        
        start_date = get_first_day(date)
        end_date = get_last_day(date)
        
        temp_filters = query_filters.copy()
        temp_filters["creation"] = ["between", [start_date, end_date]]
        
        count = frappe.db.count("Applicant", temp_filters)
        labels.append(month_label)
        values.append(count)
        
    return {
        "labels": labels,
        "datasets": [{"name": _("Applications"), "values": values}]
    }

@frappe.whitelist()
def get_demographics_data(charts_filters=None):
    """Source for Demographics (Gender/Nationality/Age Group)"""
    filters = charts_filters or {}
    query_filters = get_applicant_filters(filters)
    
    field = filters.get("demographic_type") or "gender"
    
    if field == "age_group":
        # Custom logic for age groups
        applicants = frappe.get_all("Applicant", filters=query_filters, fields=["date_of_birth"])
        groups = {"Under 18": 0, "18-22": 0, "23-26": 0, "Over 26": 0, "Unknown": 0}
        
        from frappe.utils import get_datetime
        today_dt = get_datetime()
        
        for a in applicants:
            if not a.date_of_birth:
                groups["Unknown"] += 1
                continue
            
            dob = get_datetime(a.date_of_birth)
            age = today_dt.year - dob.year - ((today_dt.month, today_dt.day) < (dob.month, dob.day))
            
            if age < 18: groups["Under 18"] += 1
            elif 18 <= age <= 22: groups["18-22"] += 1
            elif 23 <= age <= 26: groups["23-26"] += 1
            else: groups["Over 26"] += 1
            
        labels = [k for k, v in groups.items() if v > 0]
        values = [groups[k] for k in labels]
    else:
        data = frappe.db.get_all("Applicant", 
            filters=query_filters,
            fields=[f"IFNULL({field}, 'Not Specified') as label", "count(*) as count"],
            group_by=field,
            order_by="count desc"
        )
        labels = [d.label for d in data]
        values = [d.count for d in data]
    
    return {
        "labels": labels,
        "datasets": [{"values": values}]
    }

@frappe.whitelist()
def get_program_distribution_data(charts_filters=None):
    """Source for Program/Dept Distribution"""
    filters = charts_filters or {}
    query_filters = get_applicant_filters(filters)
    
    data = frappe.db.get_all("Applicant", 
        filters=query_filters,
        fields=["program as label", "count(*) as count"],
        group_by="program",
        order_by="count desc",
        limit=10
    )
    
    return {
        "labels": [d.label for d in data],
        "datasets": [{"name": _("Applicants"), "values": [d.count for d in data]}]
    }

@frappe.whitelist()
def get_fee_status_data(charts_filters=None):
    """Source for Fee Payment Status (Stacked Bar)"""
    filters = charts_filters or {}
    query_filters = get_applicant_filters(filters)
    
    data = frappe.db.get_all("Applicant", 
        filters=query_filters,
        fields=["program", "application_status", "count(*) as count"],
        group_by="program, application_status",
        order_by="count desc"
    )
    
    programs = sorted(list(set([d.program for d in data])))[:8]
    paid_values = []
    pending_values = []
    
    for p in programs:
        paid = sum([d.count for d in data if d.program == p and d.application_status in ["Fee Paid", "Enrollment Confirmed", "Accepted"]])
        pending = sum([d.count for d in data if d.program == p and d.application_status not in ["Fee Paid", "Enrollment Confirmed", "Accepted", "Rejected", "Draft"]])
        paid_values.append(paid)
        pending_values.append(pending)
        
    return {
        "labels": programs,
        "datasets": [
            {"name": _("Paid"), "values": paid_values},
            {"name": _("Pending"), "values": pending_values}
        ]
    }
