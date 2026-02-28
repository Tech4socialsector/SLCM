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
    # 1. Resolve Admission Cycles from Admission Year
    relevant_cycles = []
    if filters.get("admission_year"):
        cycles = frappe.get_all("Admission Cycle", 
            filters={"admission_year": filters.get("admission_year")}, 
            fields=["name"]
        )
        relevant_cycles = [c.name for c in cycles]

    # 2. Fetch capacities (Total Seats) from Program Offering
    po_filters = {"is_active": 1}
    if filters.get("campus"):
        po_filters["campus"] = filters.get("campus")
    if filters.get("admission_year"):
        po_filters["admission_year"] = filters.get("admission_year")
    if filters.get("program"):
        po_filters["program"] = filters.get("program")

    program_offerings = frappe.get_all("Program Offering", 
        filters=po_filters, 
        fields=["name", "campus", "program", "total_available_seats", "is_reservation_applicable"]
    )

    capacities = {} # (campus, program, category) -> total_seats
    for po_summary in program_offerings:
        campus = po_summary.campus
        program = po_summary.program
        
        if po_summary.is_reservation_applicable:
            po = frappe.get_doc("Program Offering", po_summary.name)
            reserved_total = 0
            for q in po.reservations:
                # Quota can be "General", "Government Quota", etc.
                # If Quota is General, map to "General" category
                cat_key = "General" if q.reservation_quota == "General" else (q.category or "Other")
                
                key = (campus, program, cat_key)
                capacities[key] = capacities.get(key, 0) + (int(q.seats or 0))
                reserved_total += int(q.seats or 0)
            
            # Remaining seats are Open/General
            open_seats = max(0, po_summary.total_available_seats - reserved_total)
            if open_seats > 0:
                gen_key = (campus, program, "General")
                capacities[gen_key] = capacities.get(gen_key, 0) + open_seats
        else:
            # All seats are General if no reservations
            gen_key = (campus, program, "General")
            capacities[gen_key] = capacities.get(gen_key, 0) + (int(po_summary.total_available_seats or 0))

    # 3. Fetch allocations (Allocated/Waitlisted)
    sa_filters = {"docstatus": ["<", 2]}
    if filters.get("campus"):
        sa_filters["campus"] = filters.get("campus")
    
    if filters.get("admission_cycle"):
        sa_filters["admission_cycle"] = filters.get("admission_cycle")
    elif filters.get("admission_year"):
        if not relevant_cycles:
            return []
        sa_filters["admission_cycle"] = ["in", relevant_cycles]

    seat_allocations = frappe.get_all("Seat Allocation", filters=sa_filters, fields=["name", "campus"])
    sa_names = [sa.name for sa in seat_allocations]
    sa_campus_map = {sa.name: sa.campus for sa in seat_allocations}

    allocations = {} # (campus, program, category) -> {"allocated": 0, "waitlisted": 0}
    if sa_names:
        app_params = {"parent": ["in", sa_names]}
        if filters.get("program"):
            app_params["program"] = filters.get("program")

        applicants = frappe.get_all("Seat Selection Applicant", 
            filters=app_params, 
            fields=["parent", "program", "reservation_category", "selection_status", "allocation_type"]
        )
        
        for app in applicants:
            campus = sa_campus_map.get(app.parent)
            program = app.program
            
            # Allocation Type Open -> General
            cat_key = "General" if app.allocation_type == "Open" else (app.reservation_category or "Other")
            
            key = (campus, program, cat_key)
            stats = allocations.setdefault(key, {"allocated": 0, "waitlisted": 0})
            
            # Consider all positive selection statuses as allocated
            allocated_statuses = ["Selected", "Accepted", "Fee Paid", "Offer Issued", "Offer Accepted"]
            if app.selection_status in allocated_statuses:
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
        if filters.get("campus") and campus != filters.get("campus"):
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
