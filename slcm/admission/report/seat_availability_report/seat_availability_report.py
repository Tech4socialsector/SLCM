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
        }
    ]

def get_data(filters):
    # 1. Fetch capacities (Program Offering -> Reservation Rule -> Reservation Quota)
    po_filters = {}
    if filters.get("campus"):
        po_filters["campus"] = filters.get("campus")
    if filters.get("admission_year"):
        po_filters["admission_year"] = filters.get("admission_year")

    # Get Program Offerings matching filters
    program_offerings = frappe.get_all("Program Offering", 
        filters=po_filters, 
        fields=["name", "campus"]
    )
    po_names = [po.name for po in program_offerings]
    campus_map = {po.name: po.campus for po in program_offerings}

    if not po_names:
        return []

    # Get the criteria for these offerings
    criteria = frappe.get_all("Program Offering Criteria", 
        filters={"parent": ["in", po_names]}, 
        fields=["parent", "program_of_study", "reservation_rule"]
    )

    # Get the Quota rows for relevant rules
    rule_names = list(set([c.reservation_rule for c in criteria if c.reservation_rule]))
    quota_map = {}
    if rule_names:
        # Fetch both 'category' and legacy 'quota' fields
        quotas = frappe.get_all("Reservation Quota", 
            filters={"parent": ["in", rule_names]}, 
            fields=["parent", "category", "quota", "seats"]
        )
        for q in quotas:
            # Prefer 'category', fallback to 'quota'
            q_val = q.category or q.quota
            if q_val:
                quota_map.setdefault(q.parent, []).append({
                    "quota": q_val,
                    "seats": q.seats
                })

    # Build capacities list
    capacities_list = []
    for c in criteria:
        rule_quotas = quota_map.get(c.reservation_rule, [])
        for rq in rule_quotas:
            capacities_list.append(frappe._dict({
                "campus": campus_map.get(c.parent),
                "program": c.program_of_study,
                "category": rq.get("quota"),
                "total_seats": rq.get("seats"),
                "rule": c.reservation_rule
            }))

    # 2. Fetch allocations (Seat Allocation -> Seat Selection Applicant)
    # Get all non-cancelled Seat Allocations
    seat_allocations = frappe.get_all("Seat Allocation", 
        filters={"docstatus": ["<", 2]}, 
        fields=["name", "campus"]
    )
    sa_names = [sa.name for sa in seat_allocations]
    sa_campus_map = {sa.name: sa.campus for sa in seat_allocations}

    allocations_list = []
    if sa_names:
        # Get selection applicants and aggregate in Python
        applicants = frappe.get_all("Seat Selection Applicant", 
            filters={"parent": ["in", sa_names]}, 
            fields=["parent", "program", "reservation_category", "selection_status"]
        )
        
        all_categories = frappe.get_all("Admission Category", 
            fields=["name", "category_code", "category_name"])
        cat_info_map = {c.name: c for c in all_categories}

        allocation_agg = {}
        for app in applicants:
            key = (sa_campus_map.get(app.parent), app.program, app.reservation_category)
            stats = allocation_agg.setdefault(key, {"allocated": 0, "waitlisted": 0})
            if app.selection_status == "Selected":
                stats["allocated"] += 1
            elif app.selection_status == "Waitlisted":
                stats["waitlisted"] += 1
        
        for (campus, program, cat_link), stats in allocation_agg.items():
            cat_info = cat_info_map.get(cat_link)
            allocations_list.append(frappe._dict({
                "campus": campus,
                "program": program,
                "category_link": cat_link,
                "category_code": cat_info.category_code if cat_info else None,
                "category_name": cat_info.category_name if cat_info else None,
                "allocated": stats["allocated"],
                "waitlisted": stats["waitlisted"]
            }))

    # 3. Match allocations to capacities
    refined_capacities = []
    for cap in capacities_list:
        row = frappe._dict(cap)
        row.allocated = 0
        row.waitlisted = 0
        refined_capacities.append(row)

    displayed_alloc_links = set()

    for a in allocations_list:
        best_match = None
        # Link name match
        for row in refined_capacities:
            if row.campus == a.campus and row.program == a.program and row.category == a.category_link:
                best_match = row
                break
        
        # Code match fallback
        if not best_match and a.category_code:
            for row in refined_capacities:
                if row.campus == a.campus and row.program == a.program and row.category == a.category_code:
                    best_match = row
                    break
        
        # Name match fallback
        if not best_match and a.category_name:
            for row in refined_capacities:
                if row.campus == a.campus and row.program == a.program and row.category == a.category_name:
                    best_match = row
                    break
        
        if best_match:
            best_match.allocated += a.allocated
            best_match.waitlisted += a.waitlisted
            displayed_alloc_links.add((a.campus, a.program, a.category_link))

    final_data = []
    for row in refined_capacities:
        row.vacant_seats = max(0, row.total_seats - row.allocated)
        if filters.get("program") and row.program != filters.get("program"):
            continue
        final_data.append(row)
        
    for a in allocations_list:
        alloc_key = (a.campus, a.program, a.category_link)
        if alloc_key not in displayed_alloc_links:
            row = frappe._dict({
                "campus": a.campus,
                "program": a.program,
                "category": a.category_link,
                "total_seats": 0,
                "allocated": a.allocated,
                "waitlisted": a.waitlisted,
                "vacant_seats": 0
            })
            if filters.get("program") and row.program != filters.get("program"):
                continue
            final_data.append(row)
            displayed_alloc_links.add(alloc_key)
            
    return final_data
