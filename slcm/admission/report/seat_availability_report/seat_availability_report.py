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

    # 2. Fetch capacities (Total Seats) from Program Offering
    po_filters = {"is_active": 1}
    if filters.get("campus"):
        po_filters["campus"] = filters.get("campus")
    if filters.get("admission_year"):
        po_filters["admission_year"] = filters.get("admission_year")

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
            for q in po.reservations:
                # Resolve category key consistent with allocation logic
                is_gen = False
                if q.category in ["General", "General Quota", "GEN"]:
                    is_gen = True
                elif not q.category and q.community and ("GEN" in q.community or "General" in q.community):
                    is_gen = True
                
                cat_key = "General" if is_gen else (q.community or q.category or "Other")
                
                key = (campus, program, cat_key)
                capacities[key] = capacities.get(key, 0) + (int(q.seats or 0))
        else:
            # All seats are General if no reservations
            key = (campus, program, "General")
            capacities[key] = capacities.get(key, 0) + (int(po_summary.total_available_seats or 0))

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
            fields=["parent", "program", "reservation_category", "selection_status", "allocation_type"]
        )
        
        for app in applicants:
            campus = sa_campus_map.get(app.parent)
            program = app.program
            
            # If allocation is Open, count against General pool
            # Otherwise count against their reservation category
            cat_key = "General" if app.allocation_type == "Open" else (app.reservation_category or "Other")
            
            # Key consistently on Category mapped key
            key = (campus, program, cat_key)
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
