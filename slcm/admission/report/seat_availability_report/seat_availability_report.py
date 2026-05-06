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

    # 2. Map Cycle + Program to Campus (Admission Cycle Program is the link)
    # Broaden to all cycles in year to ensure we find any existing mappings for policies
    acp_filters = {}
    if relevant_cycles:
        acp_filters["parent"] = ["in", relevant_cycles]
    elif filters.get("admission_cycle"):
        acp_filters["parent"] = filters.get("admission_cycle")
    
    if filters.get("campus"):
        acp_filters["campus"] = filters.get("campus")
    if filters.get("program"):
        acp_filters["program"] = filters.get("program")

    acp_records = frappe.get_all("Admission Cycle Program",
        filters=acp_filters,
        fields=["parent", "program", "campus", "seats", "reservation_policy"]
    )

    # Bridge the mapping: policy name -> campuses, and (cycle, program) -> campuses
    policy_to_campuses = {}
    cycle_prog_to_campuses = {}
    
    for r in acp_records:
        if r.reservation_policy:
            policy_to_campuses.setdefault(r.reservation_policy, set()).add(r.campus)
        cycle_prog_to_campuses.setdefault((r.parent, r.program), set()).add(r.campus)

    # 3. Fetch capacities from Program Reservation Policy
    prp_filters = {"status": "Active"}
    if filters.get("admission_cycle"):
        prp_filters["admission_cycle"] = filters.get("admission_cycle")
    elif relevant_cycles:
        prp_filters["admission_cycle"] = ["in", relevant_cycles]
    if filters.get("program"):
        prp_filters["program"] = filters.get("program")

    policies = frappe.get_all("Program Reservation Policy",
        filters=prp_filters,
        fields=["name", "admission_cycle", "program", "total_seats"]
    )

    capacities = {} # (campus, program, category) -> total_seats
    for p_summary in policies:
        # Get campuses: prefer explicit policy link, fallback to cycle+program match
        campuses = list(policy_to_campuses.get(p_summary.name) or 
                       cycle_prog_to_campuses.get((p_summary.admission_cycle, p_summary.program)) or 
                       [])
        
        if not campuses:
            continue

        program = p_summary.program
        policy = frappe.get_doc("Program Reservation Policy", p_summary.name)
        
        for campus in campuses:
            if filters.get("campus") and campus != filters.get("campus"):
                continue

            total_cat_seats = 0
            for cat_row in policy.categories:
                cat_name = cat_row.category_name or cat_row.reservation_quota or "General"
                cat_key = "General" if cat_name == "General" else cat_name
                
                key = (campus, program, cat_key)
                capacities[key] = capacities.get(key, 0) + (int(cat_row.seats or 0))
                total_cat_seats += int(cat_row.seats or 0)
            
            # Remainder is General
            remainder = max(0, int(p_summary.total_seats or 0) - total_cat_seats)
            if remainder > 0:
                gen_key = (campus, program, "General")
                capacities[gen_key] = capacities.get(gen_key, 0) + remainder

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

    raw_allocations = frappe.get_all("Seat Allocation", 
        filters=sa_filters, 
        fields=["name", "campus", "admission_cycle", "program_level", "status", "modified"],
        order_by="modified desc"
    )

    # Dedup: keep only the most relevant (Published > Allocated > Draft) per (campus, cycle, level)
    dedup_map = {}
    status_priority = {"Published": 2, "Allocated": 1, "Draft": 0}
    
    for sa in raw_allocations:
        key = (sa.campus, sa.admission_cycle, sa.program_level)
        existing = dedup_map.get(key)
        
        curr_prio = status_priority.get(sa.status, -1)
        prev_prio = status_priority.get(existing.status, -1) if existing else -1
        
        if not existing or curr_prio > prev_prio:
            dedup_map[key] = sa
        elif curr_prio == prev_prio:
            # Same priority, raw_allocations is already sorted by modified desc
            pass

    sa_names = [sa.name for sa in dedup_map.values()]
    sa_campus_map = {sa.name: sa.campus for sa in dedup_map.values()}

    allocations = {} # (campus, program, category) -> {"allocated": 0, "waitlisted": 0}
    if sa_names:
        app_params = {"parent": ["in", sa_names]}
        if filters.get("program"):
            app_params["program"] = filters.get("program")

        applicants = frappe.get_all("Seat Selection Applicant", 
            filters=app_params, 
            fields=["parent", "program", "allocated_category", "selection_status", "allocation_type"]
        )
        
        for app in applicants:
            campus = sa_campus_map.get(app.parent)
            program = app.program
            
            # Parse base category for quota aggregation (e.g., "SC" from "SC + Women")
            raw_cat = app.allocated_category.split(" + ")[0] if app.allocated_category else ""
            cat_key = "General" if app.allocation_type == "Open" or not raw_cat or raw_cat == "General" else raw_cat
            
            key = (campus, program, cat_key)
            stats = allocations.setdefault(key, {"allocated": 0, "waitlisted": 0})
            
            # Consider all positive selection statuses as allocated
            allocated_statuses = ["Selected", "Offer Issued", "Offer Accepted", "Accepted", "Fee Paid"]
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
