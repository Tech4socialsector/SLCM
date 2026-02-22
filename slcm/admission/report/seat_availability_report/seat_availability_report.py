# Copyright (c) 2026, TFSS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "label": _("Campus"),
            "fieldname": "campus",
            "fieldtype": "Link",
            "options": "Campus",
            "width": 150
        },
        {
            "label": _("Program"),
            "fieldname": "program",
            "fieldtype": "Link",
            "options": "Program",
            "width": 200
        },
        {
            "label": _("Category"),
            "fieldname": "category",
            "fieldtype": "Link",
            "options": "Admission Category",
            "width": 150
        },
        {
            "label": _("Total Seats"),
            "fieldname": "total_seats",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Allocated"),
            "fieldname": "allocated",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Waitlisted"),
            "fieldname": "waitlisted",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Vacant Seats"),
            "fieldname": "vacant_seats",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Utilization %"),
            "fieldname": "utilization_percent",
            "fieldtype": "Percent",
            "width": 120
        }
    ]

def get_data(filters):
    # ... (rest of get_data logic remains mostly the same, just adding the field)
    # 1. Resolve Admission Cycles from Admission Year
    relevant_cycles = []
    if filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", 
            filters={"parent": filters.get("admission_year")}, 
            fields=["name"]
        )
        relevant_cycles = [c.name for c in cycles]

    # 2. Fetch capacities (Total Seats)
    po_filters = {}
    if filters.get("campus"):
        po_filters["campus"] = filters.get("campus")
    if filters.get("admission_year"):
        po_filters["admission_year"] = filters.get("admission_year")

    program_offerings = frappe.get_all("Program Offering", filters=po_filters, fields=["name", "campus"])
    po_names = [po.name for po in program_offerings]
    campus_map = {po.name: po.campus for po in program_offerings}

    capacities = {} # (campus, program, category) -> total_seats
    if po_names:
        criteria = frappe.get_all("Program Offering Criteria", 
            filters={"parent": ["in", po_names]}, 
            fields=["parent", "program_of_study", "reservation_rule"]
        )
        
        rule_names = list(set([c.reservation_rule for c in criteria if c.reservation_rule]))
        quota_map = {}
        if rule_names:
            quotas = frappe.get_all("Reservation Quota", 
                filters={"parent": ["in", rule_names]}, 
                fields=["parent", "category", "quota", "seats"]
            )
            for q in quotas:
                cat = q.category or q.quota
                if cat:
                    quota_map.setdefault(q.parent, {}).update({cat: q.seats})

        for c in criteria:
            campus = campus_map.get(c.parent)
            program = c.program_of_study
            rule_quotas = quota_map.get(c.reservation_rule, {})
            for cat, seats in rule_quotas.items():
                key = (campus, program, cat)
                capacities[key] = capacities.get(key, 0) + (seats or 0)

    # 3. Fetch allocations (Allocated/Waitlisted)
    sa_filters = {"docstatus": ["<", 2]}
    if filters.get("campus"):
        sa_filters["campus"] = filters.get("campus")
    
    if filters.get("admission_cycle"):
        sa_filters["admission_cycle"] = filters.get("admission_cycle")
    elif filters.get("admission_year"):
        if not relevant_cycles:
            return [] # No cycles means no allocations for this year
        sa_filters["admission_cycle"] = ["in", relevant_cycles]

    seat_allocations = frappe.get_all("Seat Allocation", filters=sa_filters, fields=["name", "campus"])
    sa_names = [sa.name for sa in seat_allocations]
    sa_campus_map = {sa.name: sa.campus for sa in seat_allocations}

    allocations = {} # (campus, program, category) -> {"allocated": X, "waitlisted": Y}
    if sa_names:
        app_params = {"parent": ["in", sa_names]}
        if filters.get("program"):
            app_params["program"] = filters.get("program")

        applicants = frappe.get_all("Seat Selection Applicant", 
            filters=app_params, 
            fields=["parent", "program", "reservation_category", "selection_status"]
        )
        
        for app in applicants:
            campus = sa_campus_map.get(app.parent)
            program = app.program
            cat_link = app.reservation_category
            
            # Key consistently on Category LINK
            key = (campus, program, cat_link)
            stats = allocations.setdefault(key, {"allocated": 0, "waitlisted": 0})
            if app.selection_status == "Selected":
                stats["allocated"] += 1
            elif app.selection_status == "Waitlisted":
                stats["waitlisted"] += 1

    # 4. Consolidate Data
    all_keys = set(capacities.keys()) | set(allocations.keys())
    final_data = []

    for key in all_keys:
        campus, program, category = key
        
        if filters.get("program") and program != filters.get("program"):
            continue

        total = capacities.get(key, 0)
        stats = allocations.get(key, {"allocated": 0, "waitlisted": 0})
        
        utilization = 0
        if total > 0:
            utilization = (stats["allocated"] / total) * 100

        final_data.append(frappe._dict({
            "campus": campus,
            "program": program,
            "category": category,
            "total_seats": total,
            "allocated": stats["allocated"],
            "waitlisted": stats["waitlisted"],
            "vacant_seats": max(0, total - stats["allocated"]),
            "utilization_percent": utilization
        }))

    final_data.sort(key=lambda x: (x.campus or "", x.program or "", x.category or ""))
    return final_data

def get_chart_data(columns, data, filters):
    if not data:
        return None

    total_seats = sum(d.get("total_seats", 0) for d in data)
    allocated = sum(d.get("allocated", 0) for d in data)
    
    utilization = 0
    if total_seats > 0:
        utilization = (allocated / total_seats) * 100

    return {
        "data": {
            "labels": ["Utilization"],
            "datasets": [{"name": "Utilization %", "values": [round(utilization, 2)]}]
        },
        "type": "percentage", # Display as Percentage/Gauge in Frappe
        "colors": ["#42a5f5"]
    }
